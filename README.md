# OnCall Copilot

[![Tests](https://github.com/Sumittt28/oncall-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/Sumittt28/oncall-copilot/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**AI-powered incident response platform** with local RAG (Retrieval-Augmented Generation) for root cause analysis.

## 🚀 Features

- **Incident Management** - Create, track, and resolve incidents with severity levels and status transitions
- **Document Management** - Upload runbooks, logs, and documentation with automatic chunking
- **Semantic Search** - Find relevant incidents and documents using vector embeddings
- **AI Investigation** - Local LLM-powered root cause analysis with evidence citations
- **GitHub Integration** - Correlate commits with incidents for change-based analysis
- **Auto Postmortem** - Generate comprehensive postmortem documents on incident resolution
- **Analytics Dashboard** - Track incident trends, severity distribution, and top root causes

## 🛠️ Tech Stack

### Backend
- **FastAPI** - Modern Python web framework
- **PostgreSQL + pgvector** - Database with vector similarity search
- **SQLAlchemy 2.0** - Async ORM
- **Ollama** - Local LLM inference
- **sentence-transformers** - Local embeddings (all-MiniLM-L6-v2)

### Frontend
- **Next.js 14** - React framework with App Router
- **Tailwind CSS** - Utility-first styling
- **shadcn/ui** - UI component library
- **TanStack Query** - Data fetching and caching

## 📋 Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **Docker & Docker Compose**
- **Ollama** - [Install Ollama](https://ollama.ai/)

## 🚀 Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/Sumittt28/oncall-copilot.git
cd oncall-copilot
```

### 2. Start infrastructure services

```bash
docker compose up -d postgres redis
```

### 3. Setup Ollama

```bash
# Install Ollama from https://ollama.ai/
# Pull the model
ollama pull llama3.2:latest
```

### 4. Setup Backend

```bash
cd backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Run database migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

### 5. Setup Frontend

```bash
cd frontend

# Install dependencies
npm install

# Copy environment file
cp .env.example .env.local

# Start development server
npm run dev
```

The frontend will be available at `http://localhost:3000`

## 🐳 Docker Deployment

For full deployment with all services:

```bash
# Set JWT secret
export JWT_SECRET_KEY=$(openssl rand -hex 32)

# Start all services
docker compose up -d

# Run migrations
docker compose exec backend alembic upgrade head
```

## 📚 API Documentation

Once the backend is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/signup` | Register new user |
| POST | `/api/v1/auth/login` | Login and get JWT |
| POST | `/api/v1/incidents` | Create incident |
| GET | `/api/v1/incidents` | List incidents |
| POST | `/api/v1/incidents/{id}/investigate` | Run AI investigation |
| POST | `/api/v1/incidents/{id}/postmortem` | Generate postmortem |
| GET | `/api/v1/analytics` | Get analytics data |
| POST | `/api/v1/repositories` | Connect GitHub repo |

## 🧪 Testing

### Backend Tests

```bash
cd backend
source venv/bin/activate
python -m pytest tests/ -v
```

### Frontend Tests

```bash
cd frontend
npm test
```

## 📁 Project Structure

```
oncall-copilot/
├── backend/
│   ├── app/
│   │   ├── api/           # API routes
│   │   ├── core/          # Config, security, database
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic schemas
│   │   ├── services/      # Business logic
│   │   │   ├── llm/       # Ollama client
│   │   │   ├── rag/       # RAG pipeline
│   │   │   └── github/    # GitHub integration
│   │   └── workers/       # Background tasks
│   ├── alembic/           # Database migrations
│   └── tests/             # Test suite
├── frontend/
│   └── src/
│       ├── app/           # Next.js pages
│       ├── components/    # React components
│       └── lib/           # Utilities
├── docs/
│   ├── architecture.md
│   ├── model-choice.md
│   └── ideas.md
└── docker-compose.yml
```

## 🔧 Configuration

### Backend Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `JWT_SECRET_KEY` | Secret for JWT tokens | (required) |
| `OLLAMA_BASE_URL` | Ollama API URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | LLM model to use | `llama3.2:latest` |

### Frontend Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API URL | `http://localhost:8000` |

## 📈 Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Next.js   │────▶│   FastAPI   │────▶│  PostgreSQL │
│  Frontend   │     │   Backend   │     │  + pgvector │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌─────────┐  ┌─────────┐  ┌─────────┐
        │  Redis  │  │  Ollama │  │ GitHub  │
        │  Queue  │  │   LLM   │  │   API   │
        └─────────┘  └─────────┘  └─────────┘
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👤 Author

**Sumit Kumar Singh**
- GitHub: [@Sumittt28](https://github.com/Sumittt28)
- Email: singhsumit85422@gmail.com

---

Built with ❤️ as a portfolio project demonstrating fullstack development, AI/ML integration, and production-quality engineering practices.
