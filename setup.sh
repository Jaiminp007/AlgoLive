#!/bin/bash

# AlgoClash Live - Setup Script
# This script sets up the development environment

echo "=================================="
echo "AlgoClash Live - Setup Script"
echo "=================================="
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version

# Setup backend
echo ""
echo "Setting up backend..."
cd backend

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "✓ Backend setup complete!"

# Setup frontend
echo ""
echo "Setting up frontend..."
cd ../frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing Node dependencies..."
    npm install
else
    echo "Node modules already installed"
fi

echo ""
echo "✓ Frontend setup complete!"

# Check for .env file
cd ..
if [ ! -f "backend/.env" ]; then
    echo ""
    echo "⚠️  WARNING: No .env file found!"
    echo "Copy .env.example to backend/.env and add your API keys:"
    echo "  cp .env.example backend/.env"
    echo ""
    echo "Required keys:"
    echo "  - OPENROUTER_API_KEY (get from https://openrouter.ai)"
    echo "  - E2B_API_KEY (get from https://e2b.dev)"
fi

echo ""
echo "=================================="
echo "Setup Complete!"
echo "=================================="
echo ""
echo "To start the application:"
echo ""
echo "Terminal 1 (Backend):"
echo "  cd backend"
echo "  source venv/bin/activate"
echo "  python app.py"
echo ""
echo "Terminal 2 (Frontend):"
echo "  cd frontend"
echo "  npm run dev"
echo ""
echo "Then open: http://localhost:5173"
echo ""
