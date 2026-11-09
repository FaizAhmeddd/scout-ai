# ScoutAI — football video analysis

Upload a match video, pick a team or one player, get an annotated video, graphs, FC-style ratings and a scouting
report. Two apps: `backend/` (Python, FastAPI, MongoDB, computer-vision engine) and `frontend/` (React + Vite).

Deeper docs: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (pipeline and code map), [docs/METRICS.md](docs/METRICS.md)
(how every metric and rating is computed), [backend/README.md](backend/README.md), [frontend/README.md](frontend/README.md).

## Commands

Backend (run from `backend/`, package manager is **uv**):

```
uv run pytest -q                                   # unit tests (pure logic, no GPU/DB needed)
uv run uvicorn app.main:app --reload --port 8000   # API (needs Mongo reachable - VPN)
uv run python main.py --video path.mp4             # CLI: same engine, interactive team/player picker
uv run python scripts/download_models.py           # football models (detector ~1.5 GB, ball, pitch)
```

Frontend (run from `frontend/`): `npm install`, `npm run dev` (port 5173, proxies `/api` and `/outputs` to :8000),
`npm run build`.

The user runs their own servers on 8000 and 5173. Do not start servers on those ports or kill their processes;
the backend must be restarted by the user to pick up backend changes.

## Behavioral guidelines

Guidelines to reduce common LLM coding mistakes. They bias toward caution over speed; for trivial tasks, use judgment.

### 1. Think before coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity first

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: every changed line should trace directly to the user's request.

### 4. Goal-driven execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

These guidelines are working if: fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and
clarifying questions come before implementation rather than after mistakes.

## Rules that matter

- **MVP scope.** No Celery/Redis/queues/deploy infrastructure. Jobs run in-process (`app/services/jobs.py`,
  single worker). Result quality matters more than infrastructure.
- **Secrets.** `backend/.env` holds the Gemini key, Mongo URL, JWT secret and demo credentials. Never print, log,
  commit or read it back into chat.
- **UI copy.** The product is "ScoutAI". Never show model/vendor names (YOLO, RF-DETR, Gemini, Ultralytics, ...)
  or hardware (GPU, laptop, VRAM) in anything user-facing. API field names like `use_gemini` are fine.
- **Config over constants.** Tunables live in `backend/config/config.yaml`, typed by `app/core/app_config.py`.
  Adding a setting means updating both.
- **Cache keys.** Anything that changes tracking output must go into `_tracking_parts()` in
  `match_analysis_pipeline.py`, and a behaviour change needs a `_TRACKING_CACHE_VERSION` bump. That also changes the
  tracking signature, which marks existing videos "outdated" until re-detected.
- **Mongo needs the user's VPN.** Don't set up local Docker/Mongo. Only delete analyses/videos by explicit ID that
  you created yourself.
- **Honest numbers.** Reports state their geometry mode and caveats; never invent values when evidence is thin
  (small samples are shrunk toward priors and flagged as estimates).

## Platform notes (Windows)

- Git Bash needs `MSYS_NO_PATHCONV=1` when passing `/`-prefixed args to Windows programs.
- PyPI is extremely slow here: install via the Aliyun mirror (see the reference memory), keep
  `onnxruntime-gpu` pinned to `>=1.23,<1.24` (CUDA 12 matches torch cu128).
- GPU is a 4 GB card: one heavy job at a time. `detector.type: pose` is the lighter fallback.

## Code conventions

- Python: typed, small classes per pipeline stage, dataclasses for domain objects (`app/engine/domain/models.py`),
  Pydantic for config and API schemas. Match the surrounding comment density (sparse, explain *why*).
- Tests live in `backend/tests` and cover pure logic with synthetic data (`tests/factories.py`).
- Frontend: function components, custom CSS design system in `src/index.css` + `src/fx.css` (no UI library),
  motion helpers in `components/fx/Motion.jsx`, shared states in `components/ui/States.jsx`, display font
  Space Grotesk via `--display`. Every API field is treated as possibly missing — guard it.

## Knowledge graph (graphify)

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- When graphify-out/graph.json exists, run `graphify query "<question>"` before your first grep, search or source-file read for a codebase question, and put this rule in every subagent prompt that explores code. Read raw files only for lines the graph or an earlier read already located. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- A committed graphify-out/graph.json is rewritten whole on every build, so a large diff to it in a pull request is expected. Do not flag it as churn or suggest skipping the graph rebuild or its hooks.
