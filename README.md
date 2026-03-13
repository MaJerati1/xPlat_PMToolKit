# Meeting Toolkit

**All-in-One Meeting Management Solution**

An AI-powered platform that manages the meeting lifecycle before and after meetings. Users bring their own transcripts from any external tool (Otter, Fireflies, Krisp, Zoom, Teams, etc.) and the toolkit processes them into polished, actionable outputs.

## Architecture

- **Frontend**: Next.js 15 + React + shadcn/ui
- **Backend**: Python FastAPI
- **Database**: PostgreSQL + Redis
- **LLM**: Anthropic Claude API (primary) with provider-agnostic abstraction layer
- **Document Generation**: python-docx (Word) + WeasyPrint (PDF)

## Project Structure

```
meeting-toolkit/
├── backend/                 # Python FastAPI backend
│   ├── app/
│   │   ├── api/routes/      # REST API endpoint handlers
│   │   ├── core/            # Config, security, database setup
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── parsers/         # Transcript format parsers (SRT, VTT, CSV, JSON, TXT)
│   │   ├── services/        # Business logic and LLM abstraction layer
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   └── utils/           # Shared utilities
│   ├── tests/               # Backend test suite
│   ├── requirements.txt     # Python dependencies
│   └── Dockerfile           # Backend container
├── frontend/                # Next.js frontend
│   ├── app/                 # Next.js app router pages
│   ├── components/          # React components
│   ├── public/              # Static assets
│   ├── package.json         # Node dependencies
│   └── Dockerfile           # Frontend container
├── docker/                  # Docker Compose and shared config
├── .github/workflows/       # GitHub Actions CI/CD
├── docs/                    # Project documentation
└── docker-compose.yml       # Local development orchestration
```

## Modules

### Before Meeting
- Agenda parsing and ingestion from calendar events
- Document gathering via Google Drive API (metadata-only search)
- Document approval workflow
- Pre-meeting briefing package generation (Word/PDF)

### Transcript Ingestion
- Upload/paste transcripts from any external tool
- Multi-format parser: SRT, VTT, CSV, JSON, plain text
- Format auto-detection and speaker label normalization
- Transcript-to-agenda mapping and coverage analysis

### After Meeting
- LLM-powered meeting summary and key decision extraction
- Action item extraction with structured JSON output
- Formal meeting minutes generation (Word/PDF)
- Action item tracking with follow-up reminders
- Future meeting agenda generation from open items

## Data Privacy

Three-tier LLM data isolation architecture:
- **Tier 1**: Cloud API with zero data retention (default)
- **Tier 2**: Pre-processing redaction layer for sensitive identifiers
- **Tier 3**: Self-hosted LLM (Llama/Mistral via Ollama) for air-gapped environments

## Getting Started

### Prerequisites
- Python 3.12+
- Node.js 20+
- Docker & Docker Compose
- PostgreSQL 16+
- Redis 7+

### Local Development

```bash
# Clone the repository
git clone https://github.com/MaJerati1/xPlat_PMToolKit.git
cd meeting-toolkit

# Start all services
docker-compose up -d

# Backend: http://localhost:8000
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
```

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Required variables:
- `ANTHROPIC_API_KEY` - Claude API key
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` - Google OAuth credentials

## License

Proprietary - All rights reserved.
