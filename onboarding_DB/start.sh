#!/bin/bash

# Text2SQL Onboarding System - Startup Script

echo "🚀 Starting Text2SQL Onboarding System"
echo "======================================"

# Check if PostgreSQL is running
if ! pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo "❌ PostgreSQL is not running on localhost:5432"
    echo "Please start PostgreSQL first"
    exit 1
fi

echo "✅ PostgreSQL is running"

# Note: If you haven't set up the admin database yet, run:
# cd backend && python setup_admin_db.py

# Check if backend .env exists
cd backend
if [ ! -f ".env" ]; then
    echo "⚠️  Backend .env file not found"
    echo "Creating .env from env.example..."
    if [ -f "env.example" ]; then
        cp env.example .env
        echo "✅ Created .env file"
        echo "📝 Please edit backend/.env with your database connection"
        echo ""
        read -p "Press Enter after configuring .env (or Ctrl+C to exit)..."
    else
        echo "❌ env.example not found"
        exit 1
    fi
fi

# Start backend in background
echo ""
echo "🔧 Starting backend API (port 8001)..."
python api_server.py &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait for backend to start (with retries)
echo "⏳ Waiting for backend to be ready..."
for i in {1..10}; do
    if curl -s http://localhost:8001/health > /dev/null 2>&1; then
        echo "✅ Backend is running"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "❌ Backend failed to start after 10 seconds"
        echo "Check logs above for errors"
        kill $BACKEND_PID 2>/dev/null
        exit 1
    fi
    sleep 1
done

# Start frontend
echo ""
echo "🎨 Starting frontend (port 3001)..."
cd ../frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
fi

npm run dev &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

echo ""
echo "======================================"
echo "✅ System is running!"
echo ""
echo "📍 Backend API:  http://localhost:8001"
echo "📍 API Docs:     http://localhost:8001/docs"
echo "📍 Frontend:     http://localhost:3001"
echo ""
echo "Press Ctrl+C to stop all services"
echo "======================================"

# Handle Ctrl+C
trap "echo ''; echo '🛑 Stopping services...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT

# Keep script running
wait

