#!/bin/bash

# Wrapper script for starting services in truly detached mode
# This script is designed to work from macOS .command shortcuts

# Set PATH to ensure correct python3 and npm (prioritize /usr/bin for system Python 3.9)
export PATH="/usr/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"

cd "$(dirname "$0")"

# Redirect all output to a log file
exec > logs/startup.log 2>&1

echo "=========================================="
echo "Contract AI System - Detached Startup"
echo "Time: $(date)"
echo "=========================================="

# Show environment for debugging
echo "PATH: $PATH"
echo "Python: $(which python3) ($(python3 --version 2>&1))"
echo "NPM: $(which npm) ($(npm --version 2>&1))"
echo "=========================================="

# Start backend (use absolute path to system python3)
echo "Starting backend..."
/usr/bin/python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000 </dev/null >logs/backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > .backend.pid
echo "Backend PID: $BACKEND_PID"

# Wait and check backend
sleep 3
if ps -p $BACKEND_PID > /dev/null; then
    echo "Backend is running"
else
    echo "Backend failed to start"
    exit 1
fi

# Start frontend
echo "Starting frontend..."
cd frontend
npm run dev </dev/null >../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
echo $FRONTEND_PID > .frontend.pid
echo "Frontend PID: $FRONTEND_PID"

# Wait and check frontend
sleep 3
if ps -p $FRONTEND_PID > /dev/null; then
    echo "Frontend is running"
else
    echo "Frontend failed to start"
    exit 1
fi

# Start admin panel (Streamlit) - check if app.py exists
if [ -f "app.py" ]; then
    echo "Starting admin panel..."
    streamlit run app.py --server.port 8501 --server.headless true </dev/null >logs/streamlit.log 2>&1 &
    ADMIN_PID=$!
    echo $ADMIN_PID > .admin.pid
    echo "Admin PID: $ADMIN_PID"

    # Wait and check admin panel
    sleep 3
    if ps -p $ADMIN_PID > /dev/null; then
        echo "Admin panel is running"
    else
        echo "Admin panel failed to start (check logs/streamlit.log)"
    fi
else
    echo "Admin panel (app.py) not found in current directory - skipping"
fi

echo "=========================================="
echo "All services started successfully!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo "Admin: http://localhost:8501"
echo "=========================================="

# Open browser
sleep 2
open http://localhost:3000

exit 0
