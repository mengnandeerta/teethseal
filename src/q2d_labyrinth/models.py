from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class SealGeometry:
    tooth_count: int
    diameter: float
    clearance: float
    tooth_width: float
    tooth_height: float
    cavity_length: float
    cavity_height: float
    inlet_length: float = 0.0
    outlet_length: float = 0.0

    def validate(self) -> list[str]:
        warnings: list[str] = []
        if self.tooth_count < 1:
            raise ValueError("geometry.tooth_count must be >= 1")
        for name, value in self.__dict__.items():
            if name == "tooth_count":
                continue
            if value < 0.0:
                raise ValueError(f"geometry.{name} must be >= 0")
        for name in ("diameter", "clearance", "tooth_width", "tooth_height", "cavity_length", "cavity_height"):
            if getattr(self, name) <= 0.0:
                raise ValueError(f"geometry.{name} must be > 0")
        if self.clearance / self.diameter > 0.02:
            warnings.append("clearance/diameter is high; annular area approximation may be weak.")
        return warnings

    @property
    def flow_area(self) -> float:
        return math.pi * self.diameter * self.clearance

    @property
    def cavity_area(self) -> float:
        return math.pi * self.diameter * self.cavity_height

    @property
    def pitch(self) -> float:
        return self.tooth_width + self.cavity_length

    @property
    def total_length(self) -> float:
        return (
            self.inlet_length
            + self.tooth_count * self.tooth_width
            + max(self.tooth_count - 1, 0) * self.cavity_length
            + self.outlet_length
        )


@dataclass(frozen=True)
class DimensionlessGeometry:
    w_tooth_over_c: float
    l_cavity_over_c: float
    h_cavity_over_c: float
    h_tooth_over_c: float
    c_over_pitch: float
    diameter_over_c: float

    @classmethod
    def from_geometry(cls, geometry: SealGeometry) -> "DimensionlessGeometry":
        c = geometry.clearance
        return cls(
            w_tooth_over_c=geometry.tooth_width / c,
            l_cavity_over_c=geometry.cavity_length / c,
            h_cavity_over_c=geometry.cavity_height / c,
            h_tooth_over_c=geometry.tooth_height / c,
            c_over_pitch=c / geometry.pitch,
            diameter_over_c=geometry.diameter / c,
        )


@dataclass(frozen=True)
class FlowState:
    p: float
    h: float
    T: float
    rho: float
    s: float
    a: float
    mu: float
    quality: float | None = None
    is_two_phase: bool = False


@dataclass(frozen=True)
class Coefficients:
    Cd_tooth: float = 0.72
    K_expansion: float = 0.5
    K_contraction: float = 0.3
    theta_carryover: float = 0.35
    eta_recovery: float = 0.2

    def validate(self) -> list[str]:
        warnings: list[str] = []
        for name, value in self.__dict__.items():
            if value < 0.0:
                raise ValueError(f"coefficients.{name} must be >= 0")
        if not 0.2 <= self.Cd_tooth <= 1.2:
            warnings.append("Cd_tooth is outside the usual engineering range [0.2, 1.2].")
        if not 0.0 <= self.theta_carryover <= 1.0:
            warnings.append("theta_carryover is outside [0, 1]; cavity dissipation may be nonphysical.")
        if not 0.0 <= self.eta_recovery <= 1.0:
            warnings.append("eta_recovery is outside [0, 1]; pressure recovery may be nonphysical.")
        return warnings


@dataclass(frozen=True)
class Boundary:
    inlet_pressure: float
    inlet_temperature: float
    outlet_pressure: float

    def validate(self) -> None:
        if self.inlet_pressure <= 0.0 or self.outlet_pressure <= 0.0:
            raise ValueError("boundary pressures must be > 0")
        if self.inlet_temperature <= 0.0:
            raise ValueError("boundary.inlet_temperature must be > 0")
        if self.outlet_pressure >= self.inlet_pressure:
            raise ValueError("boundary.outlet_pressure must be lower than inlet_pressure")


@dataclass(frozen=True)
class SolverOptions:
    tolerance_pressure: float = 1.0e-5
    max_iterations: int = 100

    def validate(self) -> None:
        if self.tolerance_pressure <= 0.0:
            raise ValueError("solver.tolerance_pressure must be > 0")
        if self.max_iterations < 10:
            raise ValueError("solver.max_iterations must be >= 10")
