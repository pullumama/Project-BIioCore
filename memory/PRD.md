# BioCore Studio — PRD

## Original Problem Statement
Extend the published study (Srivastava et al., *Engineering Reports* 2025, DOI 10.1002/eng2.70557) on hemp-reinforced PLA bio-inspired sandwich-beam cellular cores (honeycomb + lotus-root baselines) by generating **new** bio-inspired core morphologies via generative/agentic AI and rapidly predicting their dynamic response (transverse shear modulus, natural frequency, damping ratio) with surrogate models, then comparing against the published baseline to find architectures with better stiffness, damping, or stiffness–damping balance — for pure PLA and hemp-reinforced PLA. Printable 3D models are the immediate deliverable; physical testing is deferred.

## Architecture
- **Frontend**: React 19 + @react-three/fiber/drei (client-side procedural 3D geometry + ASCII STL export), Recharts (trade-off scatter), Tailwind + shadcn, dark "high-contrast technical" dashboard (left controls / center 3D viewport / right analytics).
- **Backend**: FastAPI + MongoDB. Physics surrogate (`surrogate.py`) calibrated to the paper; agentic AI designer via Anthropic `claude-sonnet-4-6` (EMERGENT_LLM_KEY) with a deterministic heuristic fallback.
- **Data**: candidates persisted in MongoDB.

## User Personas
- Research author / mechanical engineer exploring the bio-inspired core design space against a published baseline.

## Core Requirements (static)
- Generate printable 3D models of bio-inspired cores (gyroid, spider-web, honeycomb, lotus-root).
- Predict G (MPa), f (Hz), damping ratio ζ, core density (kg/m³).
- Compare candidates to published honeycomb baseline (126.2 MPa / 1120 Hz / 0.0069 / 172.94 kg/m³) and lotus-root.
- Vary hemp % (0–8 wt%), cell size, wall thickness.
- AI agent proposes designs from an objective + target density + requirements.

## Implemented (2026-06)
- Surrogate calibrated: honeycomb baseline reproduces published values exactly; hemp lowers stiffness / raises damping; gyroid stiffest, spider-web highest damping, lotus balanced.
- **Reference-accurate geometry (rebuilt from user's STL)**: honeycomb = edge-to-edge hexagonal cells with shared walls; lotus-root = same hex lattice with a circular channel inside each cell; both extruded 10 mm over an 80×80 mm developed core. Gyroid = true TPMS iso-surface (marching-tetrahedra); spider-web = tiled orb-web (concentric rings + radial spokes).
- **Full Core / Unit Cell toggle** (mirrors the reference showing both the unit cell and the developed core). URL params `?pattern=&mode=&cell=&wall=&hemp=` set initial state (shareable/deterministic).
- Geometry built off the render path with a "Generating model…" overlay so metrics/UI stay responsive.
- Interactive 3D viewer (orbit/zoom/wireframe/reset) + client-side STL download of core or unit cell.
- AI Design Agent (real LLM, source='ai') with Apply-to-Studio; heuristic fallback.
- Live metric cards, stiffness–damping trade-off scatter vs baselines, candidate library (save/list/delete, MongoDB).
- 100% backend + frontend automated tests passing (iteration_1); geometry rework visually verified for all 4 patterns + both view modes.

## Backlog (prioritized)
- **P1**: Add remaining paper-mentioned morphologies (glass-sponge interpenetrating, beetle-elytra mortise-tenon, star re-entrant/auxetic, bamboo-vascular).
- **P1**: True TPMS gyroid mesh (marching cubes) for print-accurate STL.
- **P2**: Auto-optimizer that sweeps the design space and ranks Pareto-optimal candidates.
- **P2**: Export a comparison report (PDF/CSV) with baseline deltas.
- **P2**: Solid-wall (thickened) geometry for watertight printable STL.

## Next Tasks
- Gather which additional morphologies to prioritize; implement generators + surrogate coefficients.
