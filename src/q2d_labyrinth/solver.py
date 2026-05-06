from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import json
import math
from pathlib import Path

from .case import CaseConfig
from .models import DimensionlessGeometry


@dataclass(frozen=True)
class ToothResult:
    tooth: int
    p_up: float
    T_up: float
    h_up: float
    p_down: float
    T_down: float
    h_down: float
    dp: float
    dp_fraction: float
    mach: float
    reynolds: float
    Cd: float
    K_expansion: float
    K_contraction: float
    theta: float
    is_choked: bool
    choking_margin: float
    is_two_phase: bool = False


@dataclass(frozen=True)
class SolveResult:
    case_name: str
    mass_flow: float
    outlet_pressure_target: float
    outlet_pressure_calculated: float
    iterations: int
    max_mach: float
    max_mach_tooth: int
    choked_teeth: list[int]
    warnings: list[str]
    teeth: list[ToothResult]


def _velocity(mass_flow: float, rho: float, area: float) -> float:
    return mass_flow / max(rho * area, 1.0e-30)


def _march(case: CaseConfig, mass_flow: float) -> SolveResult:
    g = case.geometry
    fluid = case.fluid
    c = case.coefficients
    boundary = case.boundary
    state = fluid.state_pT(boundary.inlet_pressure, boundary.inlet_temperature)
    teeth: list[ToothResult] = []
    warnings = g.validate() + c.validate()
    nondim = DimensionlessGeometry.from_geometry(g)

    for idx in range(1, g.tooth_count + 1):
        p_up = state.p
        T_up = state.T
        h_up = state.h
        p_throat, is_choked = fluid.downstream_pressure_for_mass_flow(
            state_up=state,
            mass_flow=mass_flow,
            area=g.flow_area,
            cd=c.Cd_tooth,
        )
        h_throat = fluid.isentropic_h(p_throat, state)
        throat_state = fluid.state_ph(p_throat, h_throat)
        rho_throat = throat_state.rho
        v_tooth = _velocity(mass_flow, rho_throat, g.flow_area)
        mach = v_tooth / throat_state.a if math.isfinite(throat_state.a) and throat_state.a > 0.0 else math.nan
        reynolds = rho_throat * v_tooth * max(2.0 * g.clearance, 1.0e-30) / max(throat_state.mu, 1.0e-30)

        q = 0.5 * rho_throat * v_tooth * v_tooth
        loss = (c.K_expansion + c.K_contraction) * q
        recovery = c.eta_recovery * q
        min_pressure = getattr(fluid, "min_pressure", 1.0)
        static_after_cavity = max(p_throat - loss + recovery, min_pressure)

        carryover_ke = c.theta_carryover * 0.5 * v_tooth * v_tooth
        h_down = max(h_up + carryover_ke, 1.0)
        state = fluid.state_ph(static_after_cavity, h_down)

        choking_margin = 0.0 if is_choked else (p_throat - state.p * 0.02) / max(p_up, 1.0e-30)
        dp = p_up - state.p
        teeth.append(
            ToothResult(
                tooth=idx,
                p_up=p_up,
                T_up=T_up,
                h_up=h_up,
                p_down=state.p,
                T_down=state.T,
                h_down=state.h,
                dp=dp,
                dp_fraction=dp / max(case.boundary.inlet_pressure - case.boundary.outlet_pressure, 1.0e-30),
                mach=mach,
                reynolds=reynolds,
                Cd=c.Cd_tooth,
                K_expansion=c.K_expansion,
                K_contraction=c.K_contraction,
                theta=c.theta_carryover,
                is_choked=is_choked,
                choking_margin=choking_margin,
                is_two_phase=state.is_two_phase or throat_state.is_two_phase,
            )
        )

    if nondim.w_tooth_over_c > 30.0:
        warnings.append("w_tooth/c is outside the suggested range [1, 30].")
    if nondim.l_cavity_over_c > 50.0:
        warnings.append("l_cavity/c is outside the suggested range [2, 50].")

    max_tooth = max(teeth, key=lambda item: item.mach if math.isfinite(item.mach) else -1.0)
    return SolveResult(
        case_name=case.name,
        mass_flow=mass_flow,
        outlet_pressure_target=boundary.outlet_pressure,
        outlet_pressure_calculated=state.p,
        iterations=0,
        max_mach=max_tooth.mach,
        max_mach_tooth=max_tooth.tooth,
        choked_teeth=[item.tooth for item in teeth if item.is_choked],
        warnings=warnings,
        teeth=teeth,
    )


def solve_case(case: CaseConfig) -> SolveResult:
    inlet = case.boundary.inlet_pressure
    outlet = case.boundary.outlet_pressure
    inlet_state = case.fluid.state_pT(inlet, case.boundary.inlet_temperature)
    first_choked, _ = case.fluid.max_orifice_mass_flow(
        state_up=inlet_state,
        area=case.geometry.flow_area,
        cd=case.coefficients.Cd_tooth,
    )
    lo = 0.0
    hi = max(first_choked * 1.0e-4, 1.0e-9)
    best = _march(case, lo)
    for _ in range(40):
        try:
            trial_result = _march(case, hi)
        except ValueError:
            break
        best = trial_result
        if trial_result.outlet_pressure_calculated <= outlet:
            break
        lo = hi
        hi *= 2.0
    else:
        raise RuntimeError("Could not bracket the target outlet pressure.")
    for iteration in range(1, case.solver.max_iterations + 1):
        trial = 0.5 * (lo + hi)
        try:
            result = _march(case, trial)
        except ValueError:
            hi = trial
            continue
        best = result
        error = (result.outlet_pressure_calculated - outlet) / outlet
        if abs(error) < case.solver.tolerance_pressure:
            return _with_iterations(result, iteration)
        if result.outlet_pressure_calculated > outlet:
            lo = trial
        else:
            hi = trial
    warnings = list(best.warnings)
    warnings.append("mass-flow iteration reached max_iterations before pressure tolerance was met.")
    return _with_iterations(_replace_warnings(best, warnings), case.solver.max_iterations)


def _with_iterations(result: SolveResult, iterations: int) -> SolveResult:
    return SolveResult(**{**asdict(result), "iterations": iterations, "teeth": result.teeth})


def _replace_warnings(result: SolveResult, warnings: list[str]) -> SolveResult:
    return SolveResult(**{**asdict(result), "warnings": warnings, "teeth": result.teeth})


def write_outputs(result: SolveResult, out_dir: str | Path, case: CaseConfig | None = None) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary = asdict(result)
    summary.pop("teeth")
    with (out / "summary.json").open("w", encoding="utf-8") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)

    with (out / "teeth.csv").open("w", encoding="utf-8", newline="") as stream:
        fieldnames = list(asdict(result.teeth[0]).keys())
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in result.teeth:
            writer.writerow(asdict(row))

    lines = [
        f"# {result.case_name}",
        "",
        f"- Mass flow: {result.mass_flow:.8g} kg/s",
        f"- Outlet pressure target: {result.outlet_pressure_target:.3f} Pa",
        f"- Outlet pressure calculated: {result.outlet_pressure_calculated:.3f} Pa",
        f"- Iterations: {result.iterations}",
        f"- Max Mach: {result.max_mach:.4f} at tooth {result.max_mach_tooth}",
        f"- Choked teeth: {', '.join(map(str, result.choked_teeth)) if result.choked_teeth else 'none'}",
        "",
        "## Warnings",
        "",
    ]
    if result.warnings:
        lines.extend(f"- {item}" for item in result.warnings)
    else:
        lines.append("- none")
    if case is not None:
        from .visualization import write_geometry_pressure_png

        png_path = out / "geometry_pressure.png"
        write_geometry_pressure_png(case, result, png_path)
        lines.extend(["", "## Postprocess", "", "- `geometry_pressure.png`: geometry section with pressure labels."])
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
