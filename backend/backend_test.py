"""Backend API tests for BioCore Studio.

Covers:
- GET /api/patterns (4 patterns + ranges)
- POST /api/predict (baseline calibration + per-pattern sanity)
- POST /api/recommend (LLM/heuristic, all 3 objectives)
- POST/GET/DELETE /api/candidates CRUD
"""
import os
import pytest
import requests

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/') if os.environ.get(
    'REACT_APP_BACKEND_URL') else "https://dynamiccoreai.preview.emergentagent.com"
API = f"{BASE_URL}/api"


@pytest.fixture(scope="session")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- /api/patterns ----------
class TestPatterns:
    def test_patterns_returns_all_four(self, http):
        r = http.get(f"{API}/patterns", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "patterns" in data and "ranges" in data
        keys = {p["key"] for p in data["patterns"]}
        assert keys == {"honeycomb", "lotus", "gyroid", "spiderweb"}
        for p in data["patterns"]:
            assert p.get("label") and p.get("bio")
        rng = data["ranges"]
        assert rng["cell_size"] == [5.0, 20.0]
        assert rng["wall_thickness"] == [0.3, 2.0]
        assert rng["hemp_pct"] == [0.0, 8.0]


# ---------- /api/predict ----------
class TestPredict:
    def test_honeycomb_baseline_calibration(self, http):
        r = http.post(f"{API}/predict", json={
            "pattern": "honeycomb", "cell_size": 10, "wall_thickness": 0.5, "hemp_pct": 0
        }, timeout=15)
        assert r.status_code == 200
        body = r.json()
        m = body["metrics"]
        assert m["pattern"] == "honeycomb"
        # Calibrated baseline (with generous tolerance)
        assert abs(m["shear_modulus"] - 126.2) < 1.0, m
        assert abs(m["natural_frequency"] - 1120) < 10, m
        assert abs(m["damping_ratio"] - 0.0069) < 0.0005, m
        assert abs(m["core_density"] - 172.9) < 1.0, m
        # baselines contains honeycomb + lotus
        b_keys = {b["pattern"] for b in body["baselines"]}
        assert {"honeycomb", "lotus"}.issubset(b_keys)

    def test_pattern_ordering_stiffness_and_damping(self, http):
        """gyroid should have highest stiffness, spiderweb highest damping at same params."""
        params = {"cell_size": 10, "wall_thickness": 0.5, "hemp_pct": 0}
        results = {}
        for p in ["honeycomb", "lotus", "gyroid", "spiderweb"]:
            r = http.post(f"{API}/predict", json={**params, "pattern": p}, timeout=15)
            assert r.status_code == 200, p
            results[p] = r.json()["metrics"]
        stiffness = {k: v["shear_modulus"] for k, v in results.items()}
        damping = {k: v["damping_ratio"] for k, v in results.items()}
        assert max(stiffness, key=stiffness.get) == "gyroid", stiffness
        assert max(damping, key=damping.get) == "spiderweb", damping

    def test_hemp_increases_damping_and_lowers_stiffness(self, http):
        base = http.post(f"{API}/predict", json={
            "pattern": "lotus", "cell_size": 10, "wall_thickness": 0.5, "hemp_pct": 0
        }, timeout=15).json()["metrics"]
        hemp = http.post(f"{API}/predict", json={
            "pattern": "lotus", "cell_size": 10, "wall_thickness": 0.5, "hemp_pct": 6
        }, timeout=15).json()["metrics"]
        assert hemp["damping_ratio"] > base["damping_ratio"]
        assert hemp["shear_modulus"] < base["shear_modulus"]

    def test_predict_clamps_out_of_range(self, http):
        r = http.post(f"{API}/predict", json={
            "pattern": "honeycomb", "cell_size": 1000, "wall_thickness": 10, "hemp_pct": 999
        }, timeout=15)
        assert r.status_code == 200
        m = r.json()["metrics"]
        assert m["inputs"]["cell_size"] <= 20.0
        assert m["inputs"]["wall_thickness"] <= 2.0
        assert m["inputs"]["hemp_pct"] <= 8.0


# ---------- /api/recommend ----------
class TestRecommend:
    @pytest.mark.parametrize("obj", ["max_stiffness", "max_damping", "balanced"])
    def test_recommend_returns_valid_shape(self, http, obj):
        r = http.post(f"{API}/recommend", json={
            "objective": obj, "description": "lightweight aerospace panel"
        }, timeout=90)  # LLM may take a while
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["source"] in ("ai", "heuristic")
        assert isinstance(data["rationale"], str) and len(data["rationale"]) > 0
        rec = data["recommendation"]
        assert rec["pattern"] in {"honeycomb", "lotus", "gyroid", "spiderweb"}
        assert 5.0 <= rec["cell_size"] <= 20.0
        assert 0.3 <= rec["wall_thickness"] <= 2.0
        assert 0.0 <= rec["hemp_pct"] <= 8.0
        assert data["metrics"]["shear_modulus"] > 0
        assert data["metrics"]["natural_frequency"] > 0

    def test_recommend_max_damping_prefers_high_damping(self, http):
        r = http.post(f"{API}/recommend", json={"objective": "max_damping"}, timeout=90)
        assert r.status_code == 200
        data = r.json()
        # Damping ratio should be materially higher than pure-PLA honeycomb baseline (0.0069)
        assert data["metrics"]["damping_ratio"] > 0.0069, data


# ---------- /api/candidates CRUD ----------
class TestCandidates:
    def test_full_crud_flow(self, http):
        # Create
        payload = {
            "name": "TEST_lotus_candidate",
            "pattern": "lotus",
            "cell_size": 10.0,
            "wall_thickness": 0.5,
            "hemp_pct": 4.0,
            "metrics": {"shear_modulus": 100.0, "damping_ratio": 0.01,
                        "natural_frequency": 950.0, "core_density": 160.0,
                        "label": "Lotus-root-inspired"},
        }
        cr = http.post(f"{API}/candidates", json=payload, timeout=15)
        assert cr.status_code == 200, cr.text
        cand = cr.json()
        assert cand["name"] == payload["name"]
        assert cand["pattern"] == "lotus"
        assert "id" in cand and len(cand["id"]) > 10
        cid = cand["id"]

        # List
        lr = http.get(f"{API}/candidates", timeout=15)
        assert lr.status_code == 200
        assert any(c["id"] == cid for c in lr.json())

        # Delete
        dr = http.delete(f"{API}/candidates/{cid}", timeout=15)
        assert dr.status_code == 200
        assert dr.json()["deleted"] == cid

        # Deleting again -> 404
        dr2 = http.delete(f"{API}/candidates/{cid}", timeout=15)
        assert dr2.status_code == 404
