from __future__ import annotations

from dataclasses import dataclass
import math

from .models import FlowState


@dataclass(frozen=True)
class IdealGas:
    name: str = "air"
    gas_constant: float = 287.05
    gamma: float = 1.4
    cp: float = 1005.0
    viscosity: float = 1.8e-5

    def state_pT(self, p: float, T: float) -> FlowState:
        rho = p / (self.gas_constant * T)
        h = self.cp * T
        a = math.sqrt(self.gamma * self.gas_constant * T)
        return FlowState(p=p, h=h, T=T, rho=rho, s=0.0, a=a, mu=self.viscosity)

    def state_ph(self, p: float, h: float) -> FlowState:
        T = max(h / self.cp, 1.0)
        return self.state_pT(p, T)

    def isentropic_h(self, p_down: float, state_up: FlowState) -> float:
        exponent = (self.gamma - 1.0) / self.gamma
        T_down = state_up.T * (p_down / state_up.p) ** exponent
        return self.cp * T_down

    def critical_pressure_ratio(self) -> float:
        g = self.gamma
        return (2.0 / (g + 1.0)) ** (g / (g - 1.0))

    def critical_pressure_for_state(self, state_up: FlowState) -> float:
        return state_up.p * self.critical_pressure_ratio()

    def orifice_mass_flow(self, p_up: float, T_up: float, p_down: float, area: float, cd: float) -> tuple[float, bool]:
        if p_down >= p_up:
            return 0.0, False
        g = self.gamma
        R = self.gas_constant
        pr = max(p_down / p_up, 1.0e-12)
        pcrit = self.critical_pressure_ratio()
        if pr <= pcrit:
            factor = math.sqrt(g / R) * (2.0 / (g + 1.0)) ** ((g + 1.0) / (2.0 * (g - 1.0)))
            return cd * area * p_up / math.sqrt(T_up) * factor, True
        term = pr ** (2.0 / g) - pr ** ((g + 1.0) / g)
        factor = math.sqrt(2.0 * g / (R * (g - 1.0)) * max(term, 0.0))
        return cd * area * p_up / math.sqrt(T_up) * factor, False

    def max_orifice_mass_flow(self, state_up: FlowState, area: float, cd: float) -> tuple[float, float]:
        pcrit = self.critical_pressure_for_state(state_up)
        mass_flow, _ = self.orifice_mass_flow(state_up.p, state_up.T, pcrit, area, cd)
        return mass_flow, pcrit

    def downstream_pressure_for_mass_flow(self, state_up: FlowState, mass_flow: float, area: float, cd: float) -> tuple[float, bool]:
        if mass_flow <= 0.0:
            return state_up.p, False
        choked_flow, pcrit = self.max_orifice_mass_flow(state_up, area, cd)
        if mass_flow >= choked_flow:
            return pcrit, True
        lo = pcrit
        hi = state_up.p
        for _ in range(50):
            mid = 0.5 * (lo + hi)
            mdot_mid, _ = self.orifice_mass_flow(state_up.p, state_up.T, mid, area, cd)
            if mdot_mid > mass_flow:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi), False


@dataclass(frozen=True)
class CoolPropFluid:
    name: str = "CO2"
    backend: str = "HEOS"
    min_pressure: float = 1.0e5
    throat_samples: int = 80

    @property
    def fluid_key(self) -> str:
        return f"{self.backend}::{self.name}" if self.backend else self.name

    def _props(self, output: str, input1: str, value1: float, input2: str, value2: float) -> float:
        try:
            from CoolProp.CoolProp import PropsSI
        except ImportError as exc:
            raise RuntimeError("CoolProp is required for fluid.type='coolprop'. Install it with: pip install CoolProp") from exc
        return float(PropsSI(output, input1, value1, input2, value2, self.fluid_key))

    def state_pT(self, p: float, T: float) -> FlowState:
        h = self._props("Hmass", "P", p, "T", T)
        return self.state_ph(p, h)

    def state_ph(self, p: float, h: float) -> FlowState:
        T = self._props("T", "P", p, "Hmass", h)
        rho = self._props("Dmass", "P", p, "Hmass", h)
        s = self._props("Smass", "P", p, "Hmass", h)
        mu = self._props("V", "P", p, "Hmass", h)
        quality = self._quality_ph(p, h)
        is_two_phase = quality is not None and 0.0 <= quality <= 1.0
        try:
            a = self._props("A", "P", p, "Hmass", h)
        except ValueError:
            a = math.nan
        return FlowState(p=p, h=h, T=T, rho=rho, s=s, a=a, mu=mu, quality=quality, is_two_phase=is_two_phase)

    def _quality_ph(self, p: float, h: float) -> float | None:
        try:
            q = self._props("Q", "P", p, "Hmass", h)
        except ValueError:
            return None
        return q if 0.0 <= q <= 1.0 else None

    def isentropic_h(self, p_down: float, state_up: FlowState) -> float:
        return self._props("Hmass", "P", p_down, "Smass", state_up.s)

    def _mass_flow_at_pressure(self, state_up: FlowState, p_down: float, area: float, cd: float) -> float:
        if p_down >= state_up.p:
            return 0.0
        try:
            h_s = self.isentropic_h(p_down, state_up)
            dh = state_up.h - h_s
            if dh <= 0.0:
                return 0.0
            rho = self._props("Dmass", "P", p_down, "Hmass", h_s)
        except ValueError:
            return 0.0
        velocity = math.sqrt(2.0 * dh)
        return cd * area * rho * velocity

    def max_orifice_mass_flow(self, state_up: FlowState, area: float, cd: float) -> tuple[float, float]:
        p_low = max(self.min_pressure, state_up.p * 0.02)
        p_high = state_up.p * 0.999
        best_mdot = 0.0
        best_p = p_low
        samples = max(self.throat_samples, 20)
        for i in range(samples):
            ratio = i / (samples - 1)
            p = math.exp(math.log(p_low) * (1.0 - ratio) + math.log(p_high) * ratio)
            mdot = self._mass_flow_at_pressure(state_up, p, area, cd)
            if mdot > best_mdot:
                best_mdot = mdot
                best_p = p
        return best_mdot, best_p

    def critical_pressure_for_state(self, state_up: FlowState) -> float:
        _, pcrit = self.max_orifice_mass_flow(state_up, area=1.0, cd=1.0)
        return pcrit

    def downstream_pressure_for_mass_flow(self, state_up: FlowState, mass_flow: float, area: float, cd: float) -> tuple[float, bool]:
        if mass_flow <= 0.0:
            return state_up.p, False
        choked_flow, pcrit = self.max_orifice_mass_flow(state_up, area, cd)
        if mass_flow >= choked_flow:
            return pcrit, True
        lo = pcrit
        hi = state_up.p
        for _ in range(28):
            mid = 0.5 * (lo + hi)
            mdot_mid = self._mass_flow_at_pressure(state_up, mid, area, cd)
            if mdot_mid > mass_flow:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi), False
