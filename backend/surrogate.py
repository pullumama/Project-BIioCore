"""Physics-based surrogate models for bio-inspired sandwich cores.

Calibrated to the published baseline (Srivastava et al., Eng. Reports 2025):
  Honeycomb / pure PLA @ t=0.5mm, cell=10mm ->
      transverse shear modulus G = 126.2 MPa
      natural frequency        f = 1120 Hz
      damping ratio            zeta = 0.0069
      core density             rho  = 172.94 kg/m^3
Hemp reduces stiffness (softening + lower density) and raises damping.
Lotus-root gives lower stiffness but higher, more stable damping.
"""
import math

E_PLA = 3500.0        # MPa, solid PLA modulus
RHO_SOLID = 1240.0    # kg/m^3, solid PLA density
REF_RHO_REL = 0.1395  # honeycomb baseline relative density

# Per-pattern calibrated coefficients
PATTERNS = {
    "honeycomb": {
        "label": "Honeycomb-inspired", "bio": "Bee hive hexagonal cells",
        "C_rho": 2.79, "Cg": 0.2585, "m": 1.00, "soft": 0.098,
        "Cf": 1.311, "zeta0": 0.0069, "ah": 0.11, "p": 0.50,
    },
    "lotus": {
        "label": "Lotus-root-inspired", "bio": "Lotus stem porous channels",
        "C_rho": 2.45, "Cg": 0.235, "m": 1.05, "soft": 0.054,
        "Cf": 1.280, "zeta0": 0.0115, "ah": 0.14, "p": 0.50,
    },
    "gyroid": {
        "label": "Gyroid (TPMS)", "bio": "Triply-periodic minimal surface",
        "C_rho": 3.15, "Cg": 0.300, "m": 0.95, "soft": 0.060,
        "Cf": 1.330, "zeta0": 0.0135, "ah": 0.12, "p": 0.45,
    },
    "spiderweb": {
        "label": "Spider-web hierarchical", "bio": "Orb-web radial + spiral hierarchy",
        "C_rho": 1.85, "Cg": 0.175, "m": 1.15, "soft": 0.082,
        "Cf": 1.260, "zeta0": 0.0165, "ah": 0.16, "p": 0.55,
    },
}

CELL_MIN, CELL_MAX = 5.0, 20.0      # mm
WALL_MIN, WALL_MAX = 0.3, 2.0       # mm
HEMP_MIN, HEMP_MAX = 0.0, 8.0       # wt %


def _clamp(v, lo, hi):
    return max(lo, min(hi, float(v)))


def predict(pattern, cell_size, wall_thickness, hemp_pct):
    p = PATTERNS.get(pattern, PATTERNS["honeycomb"])
    cell = _clamp(cell_size, CELL_MIN, CELL_MAX)
    t = _clamp(wall_thickness, WALL_MIN, WALL_MAX)
    hemp = _clamp(hemp_pct, HEMP_MIN, HEMP_MAX)

    rho_rel = min(0.95, p["C_rho"] * (t / cell))
    rho_solid_eff = RHO_SOLID * (1.0 - 0.02 * hemp)
    density = rho_rel * rho_solid_eff                       # kg/m^3

    E_eff = E_PLA * (1.0 - p["soft"] * hemp)                # MPa
    G = p["Cg"] * E_eff * (rho_rel ** p["m"])               # MPa
    f = p["Cf"] * math.sqrt((G * 1.0e6) / density)          # Hz
    zeta = p["zeta0"] * (1.0 + p["ah"] * hemp) * ((REF_RHO_REL / rho_rel) ** p["p"])

    # stiffness-damping balance index (higher = better joint performance)
    balance = G * zeta * 100.0

    return {
        "pattern": pattern,
        "label": p["label"],
        "bio": p["bio"],
        "inputs": {"cell_size": round(cell, 3), "wall_thickness": round(t, 3), "hemp_pct": round(hemp, 3)},
        "relative_density": round(rho_rel, 4),
        "shear_modulus": round(G, 2),        # MPa
        "natural_frequency": round(f, 1),    # Hz
        "damping_ratio": round(zeta, 5),
        "core_density": round(density, 2),   # kg/m^3
        "balance_index": round(balance, 3),
    }


def baselines():
    """Published reference cores at standard geometry (t=0.5, cell=10, pure PLA)."""
    return [
        predict("honeycomb", 10.0, 0.5, 0.0),
        predict("lotus", 10.0, 0.5, 0.0),
    ]
