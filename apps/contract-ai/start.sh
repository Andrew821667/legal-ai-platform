#!/bin/bash
# Contract AI System - Startup Script

echo "🚀 Starting Contract AI System..."
echo ""

# Check if .env exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "💡 Copy .env.example to .env and configure it"
    exit 1
fi

# Check if database exists
if [ ! -f contract_ai.db ]; then
    echo "📊 Database not found - initializing..."
    python scripts/init_db.py
    echo ""
fi

# Start Streamlit
echo "🎨 Starting Streamlit UI on http://localhost:8501"
echo ""
echo "📝 Press Ctrl+C to stop"
echo ""

streamlit run app.py --server.port 8501 --server.address localhost
