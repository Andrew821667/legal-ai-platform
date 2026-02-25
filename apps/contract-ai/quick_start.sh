#!/bin/bash

# Contract AI System - Quick Start Script
# This script starts only the frontend for development

cd "$(dirname "$0")"

echo "🚀 Starting Contract AI Frontend..."
echo ""

# Navigate to frontend directory
cd frontend

# Start Next.js development server
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:$PATH"
npm run dev

# Keep terminal open
read -p "Press Enter to exit..."
