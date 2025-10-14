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

# Setup admin database if needed
echo ""
echo "📊 Setting up admin database..."
cd backend
python setup_admin_db.py

if [ $? -ne 0 ]; then
    echo "❌ Failed to setup admin database"
    exit 1
fi

# Start backend in background
echo ""
echo "🔧 Starting backend API (port 8001)..."
python api_server.py &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait for backend to start
sleep 3

# Check if backend is running
if curl -s http://localhost:8001/health > /dev/null; then
    echo "✅ Backend is running"
else
    echo "❌ Backend failed to start"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

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

