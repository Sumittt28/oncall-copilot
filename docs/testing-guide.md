# OnCall Copilot - Testing Guide

This guide walks you through testing the complete application.

## Prerequisites

1. **Docker Desktop** - Start Docker Desktop app
2. **Ollama** - Install from https://ollama.ai/
3. **Python 3.11** - Already set up in your venv
4. **Node.js 18+** - For frontend

## Step 1: Start Infrastructure

```bash
# Start Docker Desktop first, then:
cd ~/oncall-copilot
docker compose up -d postgres redis

# Verify services are running
docker compose ps
```

## Step 2: Start Ollama

```bash
# In a new terminal, start Ollama (if not running as service)
ollama serve

# Pull the model (in another terminal)
ollama pull llama3.2:latest

# Verify model is available
ollama list
```

## Step 3: Start Backend

```bash
cd ~/oncall-copilot/backend
source venv/bin/activate

# Run migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload
```

Backend will be at: http://localhost:8000

## Step 4: Run E2E Test

In a new terminal:

```bash
cd ~/oncall-copilot/backend
source venv/bin/activate
python ../scripts/e2e_test.py
```

This tests:
- ✓ Health check
- ✓ User signup/login
- ✓ Incident creation
- ✓ Document upload
- ✓ Embedding generation
- ✓ AI investigation (RAG)
- ✓ Incident resolution
- ✓ Postmortem generation
- ✓ Analytics
- ✓ Semantic search

## Step 5: Start Frontend (Optional)

```bash
cd ~/oncall-copilot/frontend
npm install
npm run dev
```

Frontend will be at: http://localhost:3000

## Manual Testing via API

### 1. Health Check
```bash
curl http://localhost:8000/health
```

### 2. Signup
```bash
curl -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123", "name": "Test User"}'
```

### 3. Login
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'
```

Save the `access_token` from the response.

### 4. Create Incident
```bash
TOKEN="your_access_token_here"

curl -X POST http://localhost:8000/api/v1/incidents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Database Connection Timeout",
    "description": "Users experiencing slow queries and connection timeouts",
    "severity": "SEV-2"
  }'
```

### 5. Check Ollama Status
```bash
curl http://localhost:8000/api/v1/ollama/status \
  -H "Authorization: Bearer $TOKEN"
```

### 6. Run Investigation
```bash
curl -X POST http://localhost:8000/api/v1/incidents/1/investigate \
  -H "Authorization: Bearer $TOKEN"
```

### 7. Check Dashboard
```bash
curl http://localhost:8000/api/v1/dashboard \
  -H "Authorization: Bearer $TOKEN"
```

## API Documentation

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI JSON**: http://localhost:8000/api/openapi.json

## Unit Tests

```bash
cd ~/oncall-copilot/backend
source venv/bin/activate
python -m pytest tests/ -v
```

Expected: 177 tests passing

## Troubleshooting

### Docker not starting
- Make sure Docker Desktop is running
- Check: `docker info`

### Ollama not responding
- Check if running: `curl http://localhost:11434/api/tags`
- Start manually: `ollama serve`

### Database connection error
- Check Postgres: `docker compose ps`
- Check logs: `docker compose logs postgres`

### Model not found
- Pull model: `ollama pull llama3.2:latest`
- List models: `ollama list`

### Investigation timeout
- First run takes longer (model loading)
- Wait up to 2 minutes
- Check Ollama logs for errors
