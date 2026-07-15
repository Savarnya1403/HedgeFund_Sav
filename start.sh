#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

echo "=== Indian Hedge Fund Intelligence System ==="
echo ""

# Kill anything on our ports
lsof -ti:8001 | xargs kill -9 2>/dev/null || true
lsof -ti:3002 | xargs kill -9 2>/dev/null || true

# Install backend deps
echo "[1/3] Checking Python backend dependencies..."
pip3 install fastapi "uvicorn[standard]" pandas numpy aiohttp websockets ta python-multipart requests --quiet 2>/dev/null

# Start backend
echo "[2/3] Starting FastAPI backend on :8001..."
cd "$BACKEND"
python3 -m uvicorn main:app --port 8001 --log-level warning &
BACKEND_PID=$!

# Wait for backend to be ready
echo "    Waiting for backend..."
for i in $(seq 1 25); do
  if curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo "    Backend ready ✓"
    break
  fi
  sleep 1
done

# Start frontend on port 3002
echo "[3/3] Starting Next.js frontend on :3002..."
cd "$FRONTEND"
PORT=3002 npm run dev &
FRONTEND_PID=$!

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Frontend:  http://localhost:3002"
echo "  Backend:   http://localhost:8001"
echo "  API Docs:  http://localhost:8001/docs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Press Ctrl+C to stop all services"

cleanup() {
  echo ""
  echo "Stopping services..."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
  lsof -ti:8001 | xargs kill -9 2>/dev/null || true
  lsof -ti:3002 | xargs kill -9 2>/dev/null || true
  exit 0
}

trap cleanup INT TERM
wait
