from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import re
import json
import logging
import uuid
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone

import surrogate

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------- Models ----------
class PredictRequest(BaseModel):
    pattern: str
    cell_size: float
    wall_thickness: float
    hemp_pct: float


class RecommendRequest(BaseModel):
    description: str = ""
    objective: str = "balanced"      # max_stiffness | max_damping | balanced
    target_density: Optional[float] = None   # kg/m^3


class Candidate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    pattern: str
    cell_size: float
    wall_thickness: float
    hemp_pct: float
    metrics: dict
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CandidateCreate(BaseModel):
    name: str
    pattern: str
    cell_size: float
    wall_thickness: float
    hemp_pct: float
    metrics: dict


# ---------- Routes ----------
@api_router.get("/")
async def root():
    return {"message": "Bio-Inspired Core Studio API"}


@api_router.get("/patterns")
async def get_patterns():
    return {
        "patterns": [
            {"key": k, "label": v["label"], "bio": v["bio"]}
            for k, v in surrogate.PATTERNS.items()
        ],
        "ranges": {
            "cell_size": [surrogate.CELL_MIN, surrogate.CELL_MAX],
            "wall_thickness": [surrogate.WALL_MIN, surrogate.WALL_MAX],
            "hemp_pct": [surrogate.HEMP_MIN, surrogate.HEMP_MAX],
        },
    }


@api_router.post("/predict")
async def predict(req: PredictRequest):
    metrics = surrogate.predict(req.pattern, req.cell_size, req.wall_thickness, req.hemp_pct)
    return {"metrics": metrics, "baselines": surrogate.baselines()}


@api_router.get("/baselines")
async def get_baselines():
    return {"baselines": surrogate.baselines()}


def _ai_fallback(req: RecommendRequest):
    """Deterministic heuristic used if the LLM is unavailable."""
    obj = req.objective
    if obj == "max_stiffness":
        pattern, cell, wall = "gyroid", 8.0, 1.2
    elif obj == "max_damping":
        pattern, cell, wall = "spiderweb", 14.0, 0.6
    else:
        pattern, cell, wall = "lotus", 10.0, 0.8
    hemp = 5.0 if obj != "max_stiffness" else 0.0
    if req.target_density:
        # tune wall thickness to approach target density
        wall = max(surrogate.WALL_MIN, min(surrogate.WALL_MAX,
                   (req.target_density / (surrogate.PATTERNS[pattern]["C_rho"] * surrogate.RHO_SOLID)) * cell))
    return pattern, round(cell, 2), round(wall, 2), hemp


async def _llm_recommend(req: RecommendRequest):
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    sys = (
        "You are an expert mechanical design agent for bio-inspired sandwich-beam cellular cores "
        "made of PLA / hemp-reinforced PLA, evaluated for transverse shear modulus, natural frequency "
        "and damping ratio. Available core patterns: honeycomb, lotus, gyroid, spiderweb. "
        "Design intuition: gyroid = highest stiffness; honeycomb = stiff, low damping; "
        "lotus = balanced, higher stable damping; spiderweb = highest damping, lower stiffness. "
        "Higher hemp %% lowers stiffness but increases damping. Thicker walls / smaller cells raise "
        "relative density and stiffness. Respond with ONLY a JSON object, no prose, with keys: "
        "pattern (one of honeycomb|lotus|gyroid|spiderweb), cell_size (mm, 5-20), "
        "wall_thickness (mm, 0.3-2.0), hemp_pct (0-8), rationale (<=60 words)."
    )
    prompt = (
        f"Objective: {req.objective}. "
        f"Target core density: {req.target_density if req.target_density else 'not specified'} kg/m3. "
        f"User requirements: {req.description or 'none provided'}. "
        "Recommend the best core design."
    )
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=str(uuid.uuid4()),
                   system_message=sys).with_model("anthropic", "claude-sonnet-4-6")
    resp = await chat.send_message(UserMessage(text=prompt))
    text = resp if isinstance(resp, str) else str(resp)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no json")
    data = json.loads(match.group(0))
    pattern = data.get("pattern", "lotus")
    if pattern not in surrogate.PATTERNS:
        pattern = "lotus"
    return (
        pattern,
        float(data.get("cell_size", 10.0)),
        float(data.get("wall_thickness", 0.8)),
        float(data.get("hemp_pct", 5.0)),
        data.get("rationale", ""),
    )


@api_router.post("/recommend")
async def recommend(req: RecommendRequest):
    rationale = ""
    source = "ai"
    try:
        if not EMERGENT_LLM_KEY:
            raise ValueError("no key")
        pattern, cell, wall, hemp, rationale = await _llm_recommend(req)
    except Exception as e:
        logger.warning(f"LLM recommend fell back: {e}")
        pattern, cell, wall, hemp = _ai_fallback(req)
        source = "heuristic"
        rationale = (
            f"Heuristic pick for '{req.objective}': {surrogate.PATTERNS[pattern]['label']} "
            "balances relative density and topology for the requested target."
        )
    metrics = surrogate.predict(pattern, cell, wall, hemp)
    return {
        "source": source,
        "rationale": rationale,
        "recommendation": {
            "pattern": pattern, "cell_size": round(cell, 2),
            "wall_thickness": round(wall, 2), "hemp_pct": round(hemp, 2),
        },
        "metrics": metrics,
        "baselines": surrogate.baselines(),
    }


@api_router.post("/candidates", response_model=Candidate)
async def create_candidate(req: CandidateCreate):
    cand = Candidate(**req.model_dump())
    await db.candidates.insert_one(cand.model_dump())
    return cand


@api_router.get("/candidates", response_model=List[Candidate])
async def list_candidates():
    docs = await db.candidates.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return docs


@api_router.delete("/candidates/{cid}")
async def delete_candidate(cid: str):
    res = await db.candidates.delete_one({"id": cid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"deleted": cid}


app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
