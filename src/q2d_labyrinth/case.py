from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .fluid import CoolPropFluid, IdealGas
from .models import Boundary, Coefficients, SealGeometry, SolverOptions


@dataclass(frozen=True)
class CaseConfig:
    name: str
    fluid: IdealGas | CoolPropFluid
    geometry: SealGeometry
    boundary: Boundary
    coefficients: Coefficients
    solver: SolverOptions


def _require_mapping(data: Any, name: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"{name} must be an object")
    return data


def load_case(path: str | Path) -> CaseConfig:
    path = Path(path)
    with path.open("r", encoding="utf-8") as stream:
        raw = json.load(stream)
    data = _require_mapping(raw, "case file")

    fluid_data = _require_mapping(data.get("fluid", {}), "fluid")
    case_data = _require_mapping(data.get("case", {}), "case")
    geometry = SealGeometry(**_require_mapping(data["geometry"], "geometry"))
    boundary = Boundary(**_require_mapping(data["boundary"], "boundary"))
    coefficients = Coefficients(**_require_mapping(data.get("coefficients", {}), "coefficients"))
    solver = SolverOptions(**_require_mapping(data.get("solver", {}), "solver"))
    fluid_type = fluid_data.get("type", "ideal_gas")
    fluid_kwargs = {k: v for k, v in fluid_data.items() if k != "type"}
    if fluid_type == "ideal_gas":
        fluid = IdealGas(**fluid_kwargs)
    elif fluid_type in {"coolprop", "real_gas"}:
        fluid = CoolPropFluid(**fluid_kwargs)
    else:
        raise ValueError("fluid.type must be 'ideal_gas', 'coolprop', or 'real_gas'")

    geometry.validate()
    boundary.validate()
    coefficients.validate()
    solver.validate()
    return CaseConfig(
        name=str(case_data.get("name", path.stem)),
        fluid=fluid,
        geometry=geometry,
        boundary=boundary,
        coefficients=coefficients,
        solver=solver,
    )
