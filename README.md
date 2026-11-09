# ScoutAI

Upload a match video, pick a team or one player, and get an annotated video, graphs, FC-style ratings and a
scouting report.

```
football_analysis/
├── backend/    # Python: analysis engine (main.py CLI), FastAPI, MongoDB
├── frontend/   # React + Vite web app (landing, auth, library, upload, analysis reports)
└── docs/       # ARCHITECTURE.md (pipeline and code map), METRICS.md (how every metric is computed)
```

## What you need

| Requirement | Notes |
|---|---|
| Git | to clone the repo |
| Python 3.11 or 3.12 | uv installs it for you if missing |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | Python package manager used by the backend |
| Node.js 18+ and npm | frontend |
| MongoDB | any reachable instance (local, Atlas, or your team's dev server). Put its URL in `backend/.env` |
| Gemini API key | free key from [Google AI Studio](https://aistudio.google.com/apikey); used for event analysis |
| NVIDIA GPU with 4 GB+ VRAM (recommended) | CUDA 12 builds of PyTorch are installed on Windows and Linux. Without a GPU it runs on CPU, much slower. macOS gets the CPU build |
| ~4 GB free disk | models (~1.8 GB), dependencies, sample clips |

## Setup on a new machine

### 1. Clone

```bash
git clone https://github.com/FaizAhmeddd/soccer-analysis.git
cd soccer-analysis
```

### 2. Backend

```bash
cd backend
uv sync                              # creates .venv and installs everything (PyTorch is large: first run takes a while)
cp .env.example .env                 # Windows PowerShell: Copy-Item .env.example .env
```

Edit `backend/.env` and set at least:

| Variable | What to put |
|---|---|
| `GEMINI_API_KEY` | your Google AI Studio key |
| `MONGODB_URL` / `MONGODB_DB_NAME` | your MongoDB connection string and database name |
| `JWT_SECRET_KEY` | a random secret: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DEMO_USER_EMAIL` / `DEMO_USER_PASSWORD` | optional demo login, created on API startup (leave empty to disable) |

`.env` is git-ignored. Never commit it or share it.

Download the models and sample clips (the weights are not stored in git):

```bash
uv run python scripts/download_models.py
```

This fetches the ball and pitch models, the player detector (~1.5 GB) and five short sample clips into
`backend/data/`. The pose model and tracker ReID weights are downloaded automatically on first use.

Check the install:

```bash
uv run pytest -q                     # pure-logic tests, no GPU or database needed
```

### 3. Frontend

```bash
cd ../frontend
npm install
```

`frontend/.env` is not needed in development: Vite proxies `/api` and `/outputs` to the backend on port 8000.

## Run the web app

Two terminals (MongoDB must be reachable first, e.g. connect to the VPN if your database sits behind one):

```bash
# terminal 1
cd backend
uv run uvicorn app.main:app --port 8000

# terminal 2
cd frontend
npm run dev                          # http://localhost:5173
```

Sign up, or log in with the demo account from `backend/.env`. Upload a video (or one of the sample clips from
`backend/data/samples/`), choose a team or click a player, and the analysis builds live.

The backend runs one analysis at a time, in-process, so no queue or worker is needed. Restart it after changing
backend code.

## Run from the command line (no web app, no MongoDB)

```bash
cd backend
uv run python main.py --video data/samples/0bfacc_0.mp4
```

It asks which team and which player (or the whole team) and writes the annotated video, charts and report to
`backend/outputs/`.

## Configuration

All analysis tunables are in `backend/config/config.yaml`; `.env` holds only secrets and deployment wiring.
If the GPU runs out of memory, lower `detector.resolution` (560 is the safest) or set `detector.type: pose`
for the lighter detector.

## Troubleshooting

- **`uv sync` or downloads are very slow:** use a PyPI mirror, e.g. `UV_DEFAULT_INDEX=https://mirrors.aliyun.com/pypi/simple/ uv sync`.
  PyTorch itself comes from `download.pytorch.org`.
- **CUDA not used:** check `uv run python -c "import torch; print(torch.cuda.is_available())"`. It needs an up-to-date
  NVIDIA driver (CUDA 12.8 compatible).
- **Login or upload fails with a database error:** the backend cannot reach MongoDB. Check `MONGODB_URL` and the VPN.
- **Analysis shows "outdated":** the tracking settings changed since that video was processed; use *Retry detection*.
- **Windows Git Bash:** prefix commands that take `/`-style arguments with `MSYS_NO_PATHCONV=1`.

## More documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): pipeline stages and code map
- [docs/METRICS.md](docs/METRICS.md): how every metric and rating is computed
- [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md)
