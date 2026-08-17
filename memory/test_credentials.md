# Test Credentials

No authentication in this app (single-session, no login).

## App: BioCore Studio
- Bio-inspired sandwich-core generative design + surrogate dynamic-response prediction.
- Backend base: `${REACT_APP_BACKEND_URL}/api`
- Key endpoints: GET /api/patterns, POST /api/predict, POST /api/recommend, GET/POST/DELETE /api/candidates
- LLM: Anthropic claude-sonnet-4-6 via EMERGENT_LLM_KEY (used by /api/recommend; falls back to heuristic if unavailable).
