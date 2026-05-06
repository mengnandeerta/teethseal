from __future__ import annotations

from pathlib import Path

from q2d_labyrinth.case import load_case
from q2d_labyrinth.solver import solve_case


def test_air_example_converges() -> None:
    case = load_case(Path(__file__).parents[1] / "examples" / "air_5teeth.json")
    result = solve_case(case)
    rel_error = abs(result.outlet_pressure_calculated - case.boundary.outlet_pressure) / case.boundary.outlet_pressure
    assert result.mass_flow > 0.0
    assert rel_error < 2.0e-5
    assert len(result.teeth) == case.geometry.tooth_count


def test_leakage_increases_with_clearance() -> None:
    case = load_case(Path(__file__).parents[1] / "examples" / "air_5teeth.json")
    base = solve_case(case)
    wide_geometry = type(case.geometry)(**{**case.geometry.__dict__, "clearance": case.geometry.clearance * 1.5})
    wide_case = type(case)(
        name=case.name,
        fluid=case.fluid,
        geometry=wide_geometry,
        boundary=case.boundary,
        coefficients=case.coefficients,
        solver=case.solver,
    )
    wide = solve_case(wide_case)
    assert wide.mass_flow > base.mass_flow
