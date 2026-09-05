#!/usr/bin/env python3
"""Educational HVAC airflow / ΔT helper (stdlib only).

NOT Manual D. Not a substitute for anemometer readings or OEM charts.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

DISCLAIMER = (
    "EDUCATIONAL ONLY — NOT Manual D / NOT a substitute for anemometer "
    "airflow measurement or OEM temperature-rise / CFM charts."
)

SYSTEMS = (
    "res-ac",
    "hp-cool",
    "hp-heat",
    "furnace",
    "commercial-rtu",
)

# Educational target ΔT bands °F (supply − return for heat; return − supply for cool)
# (low, high, notes)
TARGET_DT: dict = {
    "res-ac": (15.0, 22.0, "typical residential cooling split"),
    "hp-cool": (15.0, 22.0, "heat pump cooling mode"),
    "hp-heat": (20.0, 35.0, "heat pump heating (varies with outdoor T)"),
    "furnace": (35.0, 70.0, "check nameplate temperature rise"),
    "commercial-rtu": (15.0, 25.0, "packaged RTU cooling-ish band"),
}

COOLING = {"res-ac", "hp-cool", "commercial-rtu"}


@dataclass
class Result:
    system: str
    supply_f: float
    return_f: float
    measured_dt: float
    target_lo: float
    target_hi: float
    target_note: str
    status: str
    cfm: Optional[float]
    heat_btuh: Optional[float]
    checks: List[str]


def measured_delta_t(system: str, supply_f: float, return_f: float) -> float:
    if system in COOLING:
        return return_f - supply_f  # cooling: positive when supply colder
    return supply_f - return_f  # heating: positive when supply warmer


def rough_cfm(btuh: float, dt: float) -> Optional[float]:
    if abs(dt) < 0.5:
        return None
    # Sensible: BTUh ≈ 1.08 × CFM × ΔT
    return btuh / (1.08 * abs(dt))


def ranked_checks(system: str, status: str, measured_dt: float) -> List[str]:
    """Ranked 'check next' tree — educational, not diagnostic certainty."""
    cool = system in COOLING
    low = status == "low"
    high = status == "high"
    items: List[Tuple[int, str]] = []

    items.append((10, "Confirm probe placement (supply after coil/HX; return before filter if possible)"))
    items.append((20, "Verify blower is on correct speed / ECM profile and filter is clean"))

    if cool:
        if low:
            items += [
                (30, "Low ΔT cool: check low airflow (dirty filter, restrictive duct, blower)"),
                (40, "Then charge / metering (low charge often HIGH ΔT with low CFM — verify airflow first)"),
                (50, "Check evaporator coil cleanliness and TXV/piston"),
                (60, "Verify outdoor unit running and condenser airflow"),
            ]
        elif high:
            items += [
                (30, "High ΔT cool: often low airflow across evaporator"),
                (40, "Check filter, blower wheel, duct static, closed dampers/registers"),
                (50, "If airflow OK, review charge and coil performance"),
            ]
        else:
            items += [
                (30, "ΔT in band: still spot-check static pressure and filter"),
                (40, "Confirm SH/SC if diagnosing capacity complaints"),
            ]
    else:
        if system == "furnace":
            items.append((25, "Compare measured rise to furnace nameplate temperature-rise range"))
        if low:
            items += [
                (30, "Low heating ΔT: verify heat staging / heat strips / gas valve firing"),
                (40, "Check airflow high (oversized blower / wrong speed) diluting rise"),
                (50, "Furnace: flame sense, inducer, heat exchanger path; HP: outdoor ambient limits"),
            ]
        elif high:
            items += [
                (30, "High heating ΔT: often low airflow (filter, blower, duct)"),
                (40, "Risk of limit trips / heat pump high head — restore CFM"),
                (50, "Confirm supply sensor not in radiant plume"),
            ]
        else:
            items += [
                (30, "ΔT in band: confirm comfort complaint isn't distribution / zoning"),
            ]

    items += [
        (70, "Measure external static vs blower table if available"),
        (80, "Document supply/return dry-bulb and equipment mode before leaving"),
    ]
    items.sort(key=lambda x: x[0])
    return [t for _, t in items]


def analyze(
    *,
    system: str,
    supply_f: float,
    return_f: float,
    kw: Optional[float] = None,
    btuh: Optional[float] = None,
) -> Result:
    sys_t = system.strip().lower()
    if sys_t not in SYSTEMS:
        raise ValueError(f"Unknown system: {system!r}. Choose from {', '.join(SYSTEMS)}")
    lo, hi, note = TARGET_DT[sys_t]
    dt = measured_delta_t(sys_t, supply_f, return_f)
    if dt < lo:
        status = "low"
    elif dt > hi:
        status = "high"
    else:
        status = "in-band"

    heat = None
    if btuh is not None:
        heat = float(btuh)
    elif kw is not None:
        heat = float(kw) * 3412.0

    cfm = rough_cfm(heat, dt) if heat is not None else None
    checks = ranked_checks(sys_t, status, dt)
    return Result(
        system=sys_t,
        supply_f=supply_f,
        return_f=return_f,
        measured_dt=dt,
        target_lo=lo,
        target_hi=hi,
        target_note=note,
        status=status,
        cfm=cfm,
        heat_btuh=heat,
        checks=checks,
    )


def format_report(r: Result) -> str:
    mode = "cooling (return − supply)" if r.system in COOLING else "heating (supply − return)"
    lines = [
        DISCLAIMER,
        "",
        f"System: {r.system}",
        f"Supply: {r.supply_f:.1f} °F  |  Return: {r.return_f:.1f} °F",
        f"Measured ΔT ({mode}): {r.measured_dt:.1f} °F",
        f"Typical educational band: {r.target_lo:.0f}–{r.target_hi:.0f} °F ({r.target_note})",
        f"Band status: {r.status}",
    ]
    if r.heat_btuh is not None:
        lines.append(f"Heat input used: {r.heat_btuh:.0f} BTU/h")
    if r.cfm is not None:
        lines.append(f"Rough CFM ≈ {r.cfm:.0f}  (BTUh / (1.08 × |ΔT|) — approximate)")
    elif r.heat_btuh is not None:
        lines.append("Rough CFM: n/a (ΔT too small)")
    lines += ["", "Check next (ranked, educational):"]
    for i, c in enumerate(r.checks, 1):
        lines.append(f"  {i}. {c}")
    lines += ["", DISCLAIMER]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Educational HVAC airflow / ΔT helper.",
        epilog=DISCLAIMER,
    )
    p.add_argument("-i", "--interactive", action="store_true")
    p.add_argument("--system", choices=SYSTEMS)
    p.add_argument("--supply", type=float, help="Supply air °F")
    p.add_argument("--return-temp", type=float, dest="return_temp", help="Return air °F")
    p.add_argument("--kw", type=float, default=None, help="Optional heat input kW (strips/heat)")
    p.add_argument("--btu", type=float, default=None, help="Optional heat input BTU/h")
    return p


def pf(prompt: str, default: Optional[float] = None) -> float:
    while True:
        suf = f" [{default}]" if default is not None else ""
        s = input(f"{prompt}{suf}: ").strip()
        if not s and default is not None:
            return float(default)
        try:
            return float(s)
        except ValueError:
            print("Enter a number.")


def pc(label: str, choices: List[str], default: str) -> str:
    while True:
        s = (input(f"{label} ({'/'.join(choices)}) [{default}]: ").strip() or default)
        if s in choices:
            return s
        print("Invalid choice.")


def interactive() -> Result:
    print(DISCLAIMER)
    print()
    system = pc("System", list(SYSTEMS), "res-ac")
    supply = pf("Supply air °F")
    ret = pf("Return air °F")
    heat_mode = pc("Heat input for rough CFM", ["none", "kw", "btu"], "none")
    kw = btuh = None
    if heat_mode == "kw":
        kw = pf("kW")
    elif heat_mode == "btu":
        btuh = pf("BTU/h")
    return analyze(system=system, supply_f=supply, return_f=ret, kw=kw, btuh=btuh)


def from_args(ns: argparse.Namespace) -> Result:
    if ns.system is None or ns.supply is None or ns.return_temp is None:
        raise SystemExit("Need --system --supply --return-temp (or -i)")
    if ns.kw is not None and ns.btu is not None:
        raise SystemExit("Use only one of --kw or --btu")
    return analyze(
        system=ns.system,
        supply_f=ns.supply,
        return_f=ns.return_temp,
        kw=ns.kw,
        btuh=ns.btu,
    )


def main(argv: Optional[List[str]] = None) -> int:
    ns = build_parser().parse_args(argv)
    try:
        r = interactive() if ns.interactive else from_args(ns)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    print(format_report(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
