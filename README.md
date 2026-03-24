# Meeting Toolkit

**All-in-One AI-Powered Meeting Management**

Upload meeting transcripts from any tool — Otter, Fireflies, Zoom, Teams, Krisp — and get instant AI-powered summaries, action items, key decisions, and meeting continuity features. No live transcription needed — bring your own transcripts.

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/your-org/meeting-toolkit.git
cd meeting-toolkit
cp .env.example .env

# 2. Start all services
docker compose up -d

# 3. Open the app
# Frontend:    http://localhost:3000
# Setup:       http://localhost:3000/setup
# API Docs:    http://localhost:8000/docs
```

On first launch, visit **http://localhost:3000/setup** — the Getting Started wizard will walk you through generating a setup token and configuring your API keys. No manual `.env` editing required.

## Features

### Transcript Analysis
- **Multi-format ingestion** — SRT, VTT, CSV, JSON, and plain text with auto-detection
- **AI-powered analysis** — Executive summaries, key decisions, discussion topics, speaker contributions
- **Action item extraction** — Tasks with owners, deadlines, priorities, and transcript traceability
- **Quick Analyze** — Paste a transcript and get results in seconds, no account or setup needed

### Meeting Continuity
- **Agenda coverage mapping** — See which agenda items were discussed, deferred, or missed
- **Action item tracking** — Dashboard with status, overdue detection, completion rates, owner breakdown
- **Future meeting prep** — Auto-generated draft agendas from outstanding items and deferred topics

### Before Meeting
- Agenda parsing and ingestion (numbered, bullet, timestamped formats)
- Document gathering via Google Drive API (metadata-only search)
- Pre-meeting briefing package generation

### Configuration & Setup
- **Getting Started wizard** — Browser-based API key configuration with live connection testing
- **Model selector** — Switch between GPT-4o, GPT-4o-mini, Claude Sonnet/Opus/Haiku from the UI
- **Health diagnostics** — `/health/diagnostics` and `/health/check-keys` endpoints for troubleshooting

## Architecture

```
meeting-toolkit/
├── backend/                    # Python FastAPI (6,430 LOC)
│   ├── app/
│   │   ├── api/routes/         # 47 REST API endpoints across 7 modules
│   │   ├── core/               # Config, database, cross-DB UUID type
│   │   ├── models/             # SQLAlchemy ORM (Meeting, Transcript, Analysis)
│   │   ├── parsers/            # Transcript parsers (SRT, VTT, CSV, JSON, TXT)
│   │   ├── services/           # LLM abstraction, analysis pipeline, continuity engine
│   │   └── schemas/            # Pydantic request/response models
│   └── tests/                  # 129 integration tests across 11 files
├── frontend/                   # Next.js 15 + React 19 + Tailwind CSS (1,283 LOC)
│   ├── app/                    # Pages: landing, analyze, quick, setup
│   ├── components/             # Header, ThemeProvider
│   └── lib/                    # API client
├── docker/                     # PostgreSQL init script
├── docker-compose.yml          # Full stack orchestration
└── .env.example                # Configuration template
```

| Component | Technology |
|-----------|-----------|
| Frontend | Next.js 15, React 19, Tailwind CSS, Lucide Icons |
| Backend | Python 3.12, FastAPI, async SQLAlchemy |
| Database | PostgreSQL 16 (prod), SQLite (tests) |
| Cache/Queue | Redis 7, Celery |
| LLM | OpenAI (GPT-4o/mini), Anthropic (Claude), Ollama (self-hosted) |
| Containerization | Docker Compose |

## LLM Data Privacy

Three-tier data isolation architecture:

| Tier | Method | Data Exposure |
|------|--------|---------------|
| **Tier 1** | Cloud API with zero data retention | Encrypted in transit, never stored or trained on |
| **Tier 2** | Pre-processing redaction layer | Sensitive identifiers masked before reaching any LLM |
| **Tier 3** | Self-hosted via Ollama | No data leaves your network |

## API Overview

**47 endpoints** across 7 route modules:

| Module | Endpoints | Purpose |
|--------|-----------|---------|
| Health & Settings | 8 | Diagnostics, key validation, configuration |
| Quick Analyze | 1 | Single-request transcript analysis |
| Before Meeting | 17 | Meeting/agenda/attendee CRUD |
| Transcript | 7 | Upload, parse, status, coverage |
| After Meeting | 15 | Analysis, action items, tracking, future prep |

Full interactive documentation at **http://localhost:8000/docs** (Swagger UI).

## Environment Configuration

Copy `.env.example` to `.env` before starting. All values can also be configured through the Getting Started page at `localhost:3000/setup`.

### Required
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (auto-configured in Docker) |
| `REDIS_URL` | Redis connection string (auto-configured in Docker) |

### LLM Providers (at least one recommended)
| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key (starts with `sk-`) |
| `ANTHROPIC_API_KEY` | Anthropic API key (starts with `sk-ant-`) |
| `LLM_BUDGET_MODEL` | OpenAI model: `gpt-4o-mini`, `gpt-4o`, `o4-mini` |
| `LLM_PRIMARY_MODEL` | Anthropic model: `claude-sonnet-4-20250514`, etc. |
| `OLLAMA_BASE_URL` | Self-hosted Ollama URL (default: `http://localhost:11434`) |

### Optional
| Variable | Description |
|----------|-------------|
| `GOOGLE_CLIENT_ID` | Google OAuth client ID for Calendar/Drive |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `SETUP_TOKEN` | Token for accessing the settings page (auto-generated on first run) |
| `APP_SECRET_KEY` | Application secret key |

> **Note**: The toolkit works without any API keys using a built-in MockProvider that performs heuristic analysis. Configure a real LLM provider for production-quality results.

## Running Tests

```bash
# Run all 129 tests
docker compose exec backend pytest tests/ -v

# Run a specific test file
docker compose exec backend pytest tests/test_analysis_api.py -v

# Run with output
docker compose exec backend pytest tests/ -v --tb=short
```

Tests use an in-memory SQLite database and automatically force the MockProvider regardless of `.env` configuration, so they never make real API calls.

## Development

### Hot Reload
Both frontend and backend support hot reload via Docker volume mounts:
- Backend: edit files in `backend/` → uvicorn auto-reloads
- Frontend: edit files in `frontend/` → Next.js auto-reloads

### Adding a New API Endpoint
1. Add the route in `backend/app/api/routes/`
2. Create Pydantic schemas in `backend/app/schemas/`
3. Add business logic in `backend/app/services/`
4. Register the router in `backend/app/main.py`
5. Write tests in `backend/tests/`

### Rebuilding After Dependency Changes
```bash
# Backend (requirements.txt changed)
docker compose build backend

# Frontend (package.json changed)
docker compose down
docker volume rm $(docker volume ls -q | grep node_modules) 2>/dev/null
docker compose build --no-cache frontend
docker compose up -d
```

## Troubleshooting

### Check system health
```bash
curl http://localhost:8000/health/diagnostics | python -m json.tool
```

### Validate API keys
```bash
curl http://localhost:8000/health/check-keys | python -m json.tool
```

### Check .env file accessibility
```bash
curl http://localhost:8000/api/settings/debug-env | python -m json.tool
```

### View backend logs
```bash
docker compose logs backend --tail=50
```

### Common Issues
- **"Failed to fetch"** — Frontend can't reach backend. Check `docker compose ps` and ensure both services are running.
- **Analysis returns "failed"** — Check API key configuration at `localhost:3000/setup` or via `/health/check-keys`.
- **Missing topics/action items** — Try switching to `gpt-4o` or Claude Sonnet for longer transcripts. GPT-4o-mini may miss nuance in meetings over 30 minutes.
- **Frontend styles not loading** — Run `docker compose build --no-cache frontend` to clear Tailwind cache.

## License

Proprietary — All rights reserved.
