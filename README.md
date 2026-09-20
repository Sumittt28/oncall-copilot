# OnCall Copilot

AI-powered incident response platform with local RAG — root cause analysis, evidence citations, and auto-generated postmortems.

## What It Does

Engineers create incidents, attach logs and runbooks, connect a GitHub repository, then click **"Investigate with AI."** The system:

1. **Retrieves** relevant evidence (past incidents, runbooks, docs, recent commits)
2. **Reasons** over it with a locally hosted LLM (Ollama)
3. **Returns** a structured, cited root-cause analysis with confidence scores
4. **Generates** a full postmortem automatically on resolution

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, Recharts |
| **Backend** | FastAPI, Python 3.11+, Pydantic v2, SQLAlchemy 2.0 (async), Alembic |
| **Database** | PostgreSQL 16 + pgvector for semantic search |
| **Cache/Queue** | Redis |
| **AI/ML** | Ollama (llama3.1:8b), sentence-transformers (all-MiniLM-L6-v2) |
| **Auth** | JWT (python-jose + passlib) |
| **DevOps** | Docker Compose, GitHub Actions |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 18+
- Python 3.11+
- Ollama installed locally

### Setup

```bash
# Clone the repo
git clone https://github.com/Sumittt28/oncall-copilot.git
cd oncall-copilot

# Copy environment files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local

# Start infrastructure (Postgres, Redis)
docker compose up -d

# Pull the Ollama model
ollama pull llama3.1:8b

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# Frontend setup (new terminal)
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Project Structure

```
oncall-copilot/
├── frontend/                # Next.js app
├── backend/                 # FastAPI app
│   ├── app/
│   │   ├── api/            # Route handlers
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic
│   │   │   ├── rag/        # Retrieval pipeline
│   │   │   └── llm/        # Ollama integration
│   │   ├── workers/        # Background tasks
│   │   └── core/           # Config, security, deps
│   ├── alembic/            # DB migrations
│   └── tests/
├── docker-compose.yml
└── docs/
    ├── architecture.md
    ├── model-choice.md
    └── ideas.md
```

## Development

```bash
# Run backend tests
cd backend && pytest

# Run frontend tests
cd frontend && npm test

# Lint & type-check
cd backend && ruff check . && mypy .
cd frontend && npm run lint && npm run type-check
```

## License

MIT

---

Built by [Sumit Kumar Singh](https://github.com/Sumittt28)
