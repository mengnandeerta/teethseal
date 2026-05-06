from __future__ import annotations

from dataclasses import replace

from .case import CaseConfig
from .models import SealGeometry, ToothGeometry
from .solver import solve_case


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def build_adaptive_geometry(case: CaseConfig) -> CaseConfig:
    """Generate per-tooth geometry from a baseline case and local fluid states."""
    options = case.adaptive_geometry
    if not options.enabled:
        return case

    current = case
    for _ in range(max(options.iterations, 1)):
        result = solve_case(current)
        inlet_state = current.fluid.state_pT(current.boundary.inlet_pressure, current.boundary.inlet_temperature)
        rho_in = max(inlet_state.rho, 1.0e-12)
        base = current.geometry
        min_clearance = options.min_clearance or base.clearance * 0.65
        max_clearance = options.max_clearance or base.clearance * 1.10
        min_cavity_length = options.min_cavity_length or base.cavity_length * 0.75
        max_cavity_length = options.max_cavity_length or base.cavity_length * 1.60

        teeth: list[ToothGeometry] = []
        for item in result.teeth:
            try:
                local_state = current.fluid.state_pT(item.p_down, item.T_down)
                density_ratio = _clamp(local_state.rho / rho_in, 0.03, 1.0)
            except ValueError:
                density_ratio = 0.03

            clearance = base.clearance * density_ratio ** options.density_exponent
            if item.is_two_phase:
                clearance *= options.two_phase_clearance_factor
            cavity_length = base.cavity_length * (1.0 / density_ratio) ** options.cavity_exponent
            teeth.append(
                ToothGeometry(
                    clearance=_clamp(clearance, min_clearance, max_clearance),
                    tooth_width=base.tooth_width,
                    tooth_height=base.tooth_height,
                    cavity_length=_clamp(cavity_length, min_cavity_length, max_cavity_length),
                    cavity_height=base.cavity_height,
                )
            )

        geometry = SealGeometry(
            tooth_count=base.tooth_count,
            diameter=base.diameter,
            clearance=base.clearance,
            tooth_width=base.tooth_width,
            tooth_height=base.tooth_height,
            cavity_length=base.cavity_length,
            cavity_height=base.cavity_height,
            inlet_length=base.inlet_length,
            outlet_length=base.outlet_length,
            teeth=tuple(teeth),
        )
        current = replace(current, geometry=geometry)
    return current
