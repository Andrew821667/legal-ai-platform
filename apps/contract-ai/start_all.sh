#!/bin/bash
# ============================================================================
# Contract AI System - Start All Services
# ============================================================================
# This script starts:
# 1. FastAPI Backend (port 8000)
# 2. Next.js Frontend (port 3000)
# 3. Streamlit Admin Panel (port 8501)
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Project paths
# Project paths
PROJECT_DIR="$(pwd)"
WORKTREE_DIR="$(pwd)"
FRONTEND_DIR="$WORKTREE_DIR/frontend"

# Detect Node.js and npm paths
if [ -f "/opt/homebrew/bin/node" ]; then
    NODE_BIN="/opt/homebrew/bin/node"
    NPM_BIN="/opt/homebrew/bin/npm"
    export PATH="/opt/homebrew/bin:$PATH"
elif [ -f "/usr/local/bin/node" ]; then
    NODE_BIN="/usr/local/bin/node"
    NPM_BIN="/usr/local/bin/npm"
    export PATH="/usr/local/bin:$PATH"
else
    echo -e "${RED}❌ Node.js not found. Please install Node.js first.${NC}"
    exit 1
fi

# Print banner
echo -e "${CYAN}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║           CONTRACT AI SYSTEM - STARTUP SCRIPT                ║
║                                                               ║
║   Starting all services: Backend + Frontend + Admin Panel    ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

cd "$WORKTREE_DIR"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo -e "${BLUE}🔧 Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# ============================================================================
# Step 1: Check .env file
# ============================================================================
echo -e "${BLUE}[1/7]${NC} Checking .env file..."

if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Copying from .env.example...${NC}"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}✅ .env file created${NC}"
        echo -e "${YELLOW}⚠️  Please configure your API keys in .env file!${NC}"
    else
        echo -e "${RED}❌ .env.example not found!${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ .env file exists${NC}"
fi

# ============================================================================
# Step 2: Check and initialize database
# ============================================================================
echo -e "\n${BLUE}[2/7]${NC} Checking database..."

if [ ! -f "contract_ai.db" ]; then
    echo -e "${YELLOW}⚠️  Database not found. Initializing...${NC}"
    python3 database/init_users.py
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Database initialized with users${NC}"
    else
        echo -e "${RED}❌ Failed to initialize database${NC}"
        exit 1
    fi
else
    # Check if database has users
    USER_COUNT=$(sqlite3 contract_ai.db "SELECT COUNT(*) FROM users;" 2>/dev/null || echo "0")
    if [ "$USER_COUNT" -eq "0" ]; then
        echo -e "${YELLOW}⚠️  Database exists but has no users. Initializing users...${NC}"
        python3 database/init_users.py
    else
        echo -e "${GREEN}✅ Database exists with $USER_COUNT users${NC}"
    fi
fi

# ============================================================================
# Step 3: Install frontend dependencies if needed
# ============================================================================
echo -e "\n${BLUE}[3/7]${NC} Checking frontend dependencies..."

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo -e "${YELLOW}⚠️  node_modules not found. Installing dependencies...${NC}"
    cd "$FRONTEND_DIR"
    $NPM_BIN install
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Frontend dependencies installed${NC}"
    else
        echo -e "${RED}❌ Failed to install frontend dependencies${NC}"
        exit 1
    fi
    cd "$WORKTREE_DIR"
else
    echo -e "${GREEN}✅ Frontend dependencies installed${NC}"
fi

# ============================================================================
# Step 4: Check if ports are available
# ============================================================================
echo -e "\n${BLUE}[4/7]${NC} Checking if ports are available..."

check_port() {
    PORT=$1
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo -e "${RED}❌ Port $PORT is already in use${NC}"
        echo -e "${YELLOW}   Run: lsof -ti:$PORT | xargs kill -9${NC}"
        return 1
    else
        echo -e "${GREEN}✅ Port $PORT is available${NC}"
        return 0
    fi
}

PORTS_OK=true
check_port 8000 || PORTS_OK=false
check_port 3000 || PORTS_OK=false
check_port 8501 || PORTS_OK=false

if [ "$PORTS_OK" = false ]; then
    echo -e "\n${YELLOW}Do you want to kill processes on these ports? (y/n)${NC}"
    read -r KILL_PORTS
    if [ "$KILL_PORTS" = "y" ] || [ "$KILL_PORTS" = "Y" ]; then
        echo -e "${YELLOW}Killing processes...${NC}"
        lsof -ti:8000 | xargs kill -9 2>/dev/null || true
        lsof -ti:3000 | xargs kill -9 2>/dev/null || true
        lsof -ti:8501 | xargs kill -9 2>/dev/null || true
        sleep 2
        echo -e "${GREEN}✅ Ports cleared${NC}"
    else
        echo -e "${RED}❌ Cannot start with ports in use${NC}"
        exit 1
    fi
fi

# ============================================================================
# Step 5: Start FastAPI Backend
# ============================================================================
echo -e "\n${BLUE}[5/7]${NC} Starting FastAPI Backend (port 8000)..."

# Debug: Show environment
echo "DEBUG: python3 path: $(which python3)"
echo "DEBUG: Current directory: $(pwd)"

python3 -c "import uvicorn" >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ uvicorn not installed. Installing...${NC}"
    pip3 install uvicorn
fi

# Start backend with better error logging
echo "DEBUG: Starting backend with: python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000"
nohup python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000 > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "DEBUG: Backend PID: $BACKEND_PID"
echo $BACKEND_PID > .backend.pid

# Check if process is actually running
sleep 1
if ps -p $BACKEND_PID > /dev/null 2>&1; then
    echo "DEBUG: Backend process is running (PID: $BACKEND_PID)"
else
    echo -e "${RED}❌ Backend process died immediately after start${NC}"
    echo "Last 20 lines of backend.log:"
    tail -20 logs/backend.log
    exit 1
fi

# Wait longer for backend to initialize
echo "DEBUG: Waiting 5 seconds for backend to initialize..."
sleep 5

# Check if backend started
echo "DEBUG: Testing health endpoint with curl..."
if curl -s --max-time 5 http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend started (PID: $BACKEND_PID)${NC}"
    echo -e "${CYAN}   📡 API: http://localhost:8000${NC}"
    echo -e "${CYAN}   📚 Docs: http://localhost:8000/api/docs${NC}"
else
    echo -e "${RED}❌ Backend health check failed${NC}"
    echo "Backend process status:"
    ps -p $BACKEND_PID || echo "Process not found"
    echo "Last 30 lines of backend.log:"
    tail -30 logs/backend.log
    exit 1
fi

# ============================================================================
# Step 6: Start Next.js Frontend
# ============================================================================
echo -e "\n${BLUE}[6/7]${NC} Starting Next.js Frontend (port 3000)..."

cd "$FRONTEND_DIR"
nohup $NPM_BIN run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > ../.frontend.pid
cd "$WORKTREE_DIR"

sleep 5

# Check if frontend started
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Frontend started (PID: $FRONTEND_PID)${NC}"
    echo -e "${CYAN}   🌐 App: http://localhost:3000${NC}"
else
    echo -e "${YELLOW}⚠️  Frontend is starting... (may take a minute)${NC}"
fi

# ============================================================================
# Step 7: Start Streamlit Admin Panel
# ============================================================================
echo -e "\n${BLUE}[7/7]${NC} Starting Streamlit Admin Panel (port 8501)..."

streamlit --version >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ streamlit not installed${NC}"
    exit 1
fi

nohup streamlit run app_admin.py --server.port 8501 --server.headless true > logs/admin.log 2>&1 &
ADMIN_PID=$!
echo $ADMIN_PID > .admin.pid

sleep 3

# Check if admin panel started
if curl -s http://localhost:8501 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Admin Panel started (PID: $ADMIN_PID)${NC}"
    echo -e "${CYAN}   🔐 Admin: http://localhost:8501${NC}"
else
    echo -e "${YELLOW}⚠️  Admin panel is starting...${NC}"
fi

# ============================================================================
# Success!
# ============================================================================
echo -e "\n${GREEN}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║                    🎉 ALL SERVICES STARTED! 🎉                ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

echo -e "${CYAN}📍 ACCESS POINTS:${NC}"
echo -e "   ${GREEN}•${NC} Main Interface (Users):   ${BLUE}http://localhost:3000${NC}"
echo -e "   ${GREEN}•${NC} Admin Panel (Admins):     ${BLUE}http://localhost:8501${NC}"
echo -e "   ${GREEN}•${NC} API Documentation:        ${BLUE}http://localhost:8000/api/docs${NC}"

echo -e "\n${CYAN}👥 DEFAULT CREDENTIALS:${NC}"
echo -e "   ${GREEN}•${NC} Admin:  ${YELLOW}admin@contractai.local${NC} / ${YELLOW}Admin123!${NC}"
echo -e "   ${GREEN}•${NC} Check CREDENTIALS.txt for all users"

echo -e "\n${CYAN}📋 PROCESS IDs:${NC}"
echo -e "   ${GREEN}•${NC} Backend:  ${YELLOW}$BACKEND_PID${NC}"
echo -e "   ${GREEN}•${NC} Frontend: ${YELLOW}$FRONTEND_PID${NC}"
echo -e "   ${GREEN}•${NC} Admin:    ${YELLOW}$ADMIN_PID${NC}"

echo -e "\n${CYAN}🛑 TO STOP ALL SERVICES:${NC}"
echo -e "   ${YELLOW}./stop_all.sh${NC}"

echo -e "\n${CYAN}📝 LOGS:${NC}"
echo -e "   ${GREEN}•${NC} Backend:  logs/backend.log"
echo -e "   ${GREEN}•${NC} Frontend: logs/frontend.log"
echo -e "   ${GREEN}•${NC} Admin:    logs/admin.log"

echo -e "\n${GREEN}✨ Happy contracting! ✨${NC}\n"
