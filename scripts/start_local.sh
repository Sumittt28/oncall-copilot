#!/bin/bash
# Start OnCall Copilot locally for testing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================"
echo "  OnCall Copilot - Local Startup"
echo "========================================"

# Check Docker
echo ""
echo "1. Starting Docker services (Postgres + Redis)..."
cd "$PROJECT_DIR"
docker compose up -d postgres redis
sleep 3

# Check Ollama
echo ""
echo "2. Checking Ollama..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "   ✓ Ollama is running"
else
    echo "   ✗ Ollama not running. Please start Ollama first."
    echo "   Run: ollama serve"
    exit 1
fi

# Check model
echo ""
echo "3. Checking Ollama model..."
if curl -s http://localhost:11434/api/tags | grep -q "llama3.2"; then
    echo "   ✓ llama3.2 model available"
else
    echo "   → Pulling llama3.2:latest..."
    ollama pull llama3.2:latest
fi

# Start backend
echo ""
echo "4. Starting backend..."
cd "$PROJECT_DIR/backend"

# Create venv if not exists
if [ ! -d "venv" ]; then
    echo "   Creating virtual environment..."
    python3.11 -m venv venv
fi

source venv/bin/activate

# Install deps if needed
pip install -r requirements.txt -q

# Run migrations
echo "   Running database migrations..."
alembic upgrade head 2>/dev/null || echo "   (migrations may already be applied)"

# Start server in background
echo "   Starting uvicorn..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "   Backend PID: $BACKEND_PID"

# Wait for backend
echo "   Waiting for backend to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "   ✓ Backend is ready"
        break
    fi
    sleep 1
done

echo ""
echo "========================================"
echo "  OnCall Copilot is running!"
echo "========================================"
echo ""
echo "Services:"
echo "  • Backend API: http://localhost:8000"
echo "  • API Docs:    http://localhost:8000/api/docs"
echo "  • Postgres:    localhost:5432"
echo "  • Redis:       localhost:6379"
echo ""
echo "To run E2E test:"
echo "  cd $PROJECT_DIR/backend"
echo "  source venv/bin/activate"
echo "  python ../scripts/e2e_test.py"
echo ""
echo "To stop:"
echo "  kill $BACKEND_PID"
echo "  docker compose down"
echo ""
