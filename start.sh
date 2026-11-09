#!/bin/bash
# Kisan Hita Application Runner
# Starts Python FastAPI backend on port 8000 and Vite React frontend on port 5173

set -e

# Resolve project paths from this script, not the caller's current directory.
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "=========================================================="
echo "🌱 Starting Kisan Hita — Multilingual AI Farm Assistant"
echo "=========================================================="

# Trap to kill background jobs on exit
trap 'kill $(jobs -p) 2>/dev/null || true' EXIT

# Start backend
echo "Starting FastAPI backend on http://127.0.0.1:8000..."
PYTHONPATH=. python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait for backend to be ready
sleep 1.5

# Start frontend
echo "Starting Vite frontend on http://localhost:5173..."
cd frontend
npm run dev -- --host &
FRONTEND_PID=$!

echo ""
echo "🚀 Kisan Hita is live!"
echo "👉 Web Application: http://localhost:5173"
echo "👉 Backend API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers."

wait

