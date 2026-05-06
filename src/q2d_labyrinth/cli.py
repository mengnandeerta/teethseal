from __future__ import annotations

import argparse
from pathlib import Path

from .case import load_case
from .adaptive import build_adaptive_geometry
from .solver import solve_case, write_outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a quasi-2D labyrinth seal calculation.")
    parser.add_argument("case", help="Path to a JSON case file.")
    parser.add_argument("--out", default="outputs/run", help="Output directory.")
    args = parser.parse_args(argv)

    case = load_case(Path(args.case))
    case = build_adaptive_geometry(case)
    result = solve_case(case)
    write_outputs(result, args.out, case)

    print(f"Case: {result.case_name}")
    print(f"Mass flow: {result.mass_flow:.8g} kg/s")
    print(f"Outlet pressure target: {result.outlet_pressure_target:.3f} Pa")
    print(f"Outlet pressure calculated: {result.outlet_pressure_calculated:.3f} Pa")
    print(f"Max Mach: {result.max_mach:.4f} at tooth {result.max_mach_tooth}")
    print(f"Choked teeth: {', '.join(map(str, result.choked_teeth)) if result.choked_teeth else 'none'}")
    print(f"Output: {Path(args.out).resolve()}")
    print(f"Geometry plot: {Path(args.out).resolve() / 'geometry_pressure.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
