#!/bin/bash

# InMemory MCP Tailscale Deployment Startup Script
# This script starts all three servers for Tailscale deployment

set -e

echo "🚀 Starting InMemory MCP Servers for Tailscale Deployment"
echo "=================================================="

# Check if we're in the mcp directory
if [ ! -f "proxy_server.py" ]; then
    echo "❌ Error: Please run this script from the mcp/ directory"
    echo "   Usage: cd mcp && ./start_servers.sh"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python3 is not installed or not in PATH"
    exit 1
fi

# Install proxy dependencies if needed
echo "📦 Installing proxy server dependencies..."
if [ -f "requirements_proxy.txt" ]; then
    uv pip install -r requirements_proxy.txt
else
    echo "⚠️  Warning: requirements_proxy.txt not found"
fi

# Function to start server in background
start_server() {
    local server_name=$1
    local script_name=$2
    local port=$3
    local extra_args=$4
    
    echo "🔄 Starting $server_name on port $port..."
    
    # Kill any existing process on this port
    if lsof -ti:$port >/dev/null 2>&1; then
        echo "   🔧 Killing existing process on port $port"
        kill -9 $(lsof -ti:$port) 2>/dev/null || true
        sleep 2
    fi
    
    # Start the server
    if [ -f "$script_name" ]; then
        nohup python3 $script_name --host 0.0.0.0 --port $port $extra_args > ${server_name}.log 2>&1 &
        local pid=$!
        echo "   ✅ $server_name started (PID: $pid)"
        echo "   📝 Logs: ${server_name}.log"
    else
        echo "   ❌ Error: $script_name not found"
        return 1
    fi
}

# Start all servers
echo ""
echo "🏃 Starting servers..."
echo "----------------------"

# 1. Core API Server (port 8081)
start_server "Core-API-Server" "api_server.py" "8081"

# Wait a moment for Core API to start
sleep 3

# 2. MCP Server (port 8080) 
start_server "MCP-Server" "server.py" "8080"

# Wait a moment for MCP Server to start
sleep 3

# 3. Reverse Proxy (port 8000)
start_server "Reverse-Proxy" "proxy_server.py" "8000"

# Wait for all servers to initialize
echo ""
echo "⏳ Waiting for servers to initialize..."
sleep 5

# Check server health
echo ""
echo "🔍 Checking server health..."
echo "----------------------------"

check_health() {
    local service_name=$1
    local url=$2
    
    if curl -s "$url" > /dev/null 2>&1; then
        echo "✅ $service_name: Healthy"
        return 0
    else
        echo "❌ $service_name: Not responding"
        return 1
    fi
}

# Health checks
check_health "Core API Server" "http://localhost:8081/v1/health"
check_health "MCP Server" "http://localhost:8080/health"  
check_health "Reverse Proxy" "http://localhost:8000/health"

echo ""
echo "🎉 Deployment Complete!"
echo "======================"
echo ""
echo "📋 Server Status:"
echo "  • Core API Server:  http://localhost:8081"
echo "  • MCP Server:       http://localhost:8080" 
echo "  • Reverse Proxy:    http://localhost:8000"
echo ""
echo "🌐 Tailscale Access:"
echo "  • Dashboard API:    https://inmemory.tailb75d54.ts.net/"
echo "  • MCP Tools:        https://inmemory.tailb75d54.ts.net/mcp"
echo ""
echo "📊 Health Check:     https://inmemory.tailb75d54.ts.net/health"
echo ""
echo "📝 Log Files:"
echo "  • Core-API-Server.log"
echo "  • MCP-Server.log"
echo "  • Reverse-Proxy.log"
echo ""
echo "🛑 To stop all servers: ./stop_servers.sh"
echo ""
echo "⚠️  IMPORTANT: Point your Tailscale to port 8000 (Reverse Proxy)"
