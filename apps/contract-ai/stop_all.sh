#!/bin/bash
# ============================================================================
# Contract AI System - Stop All Services
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

WORKTREE_DIR="/Users/andrew/.claude-worktrees/Contract-AI-System-/blissful-hellman"

echo -e "${CYAN}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║           CONTRACT AI SYSTEM - SHUTDOWN SCRIPT                ║
║                                                               ║
║          Stopping all services gracefully...                  ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

cd "$WORKTREE_DIR"

# Function to kill process by PID file
kill_by_pidfile() {
    PIDFILE=$1
    SERVICE=$2

    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo -e "${YELLOW}Stopping $SERVICE (PID: $PID)...${NC}"
            kill $PID 2>/dev/null || kill -9 $PID 2>/dev/null || true
            sleep 1

            if ps -p $PID > /dev/null 2>&1; then
                echo -e "${RED}❌ Failed to stop $SERVICE${NC}"
            else
                echo -e "${GREEN}✅ $SERVICE stopped${NC}"
            fi
        else
            echo -e "${YELLOW}⚠️  $SERVICE not running (stale PID file)${NC}"
        fi
        rm -f "$PIDFILE"
    else
        echo -e "${YELLOW}⚠️  $SERVICE PID file not found${NC}"
    fi
}

# Stop Backend
echo -e "\n${CYAN}[1/3]${NC} Stopping FastAPI Backend..."
kill_by_pidfile ".backend.pid" "Backend"

# Also kill by port
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

# Stop Frontend
echo -e "\n${CYAN}[2/3]${NC} Stopping Next.js Frontend..."
kill_by_pidfile ".frontend.pid" "Frontend"

# Also kill by port
lsof -ti:3000 | xargs kill -9 2>/dev/null || true

# Stop Admin Panel
echo -e "\n${CYAN}[3/3]${NC} Stopping Streamlit Admin Panel..."
kill_by_pidfile ".admin.pid" "Admin Panel"

# Also kill by port
lsof -ti:8501 | xargs kill -9 2>/dev/null || true

# Kill any remaining streamlit processes
pkill -f "streamlit run app_admin.py" 2>/dev/null || true
pkill -f "uvicorn src.main:app" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true

echo -e "\n${GREEN}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║                 🛑 ALL SERVICES STOPPED 🛑                    ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

echo -e "${CYAN}To start services again, run:${NC}"
echo -e "   ${YELLOW}./start_all.sh${NC}\n"
