#!/usr/bin/env bash
# Start the Vocal Outreach Pipeline backend
# Usage: ./start.sh

cd "$(dirname "$0")"

echo "🚀 Starting Vocal Outreach Pipeline server..."
echo ""
echo "  Backend API: http://localhost:8000"
echo "  Open the frontend HTML file in your browser."
echo ""
echo "  Press Ctrl+C to stop."
echo ""

# Install requirements if needed
pip install fastapi uvicorn sse-starlette python-dotenv requests --quiet 2>/dev/null || true

uvicorn server:app --reload --port 8000 --host 0.0.0.0
