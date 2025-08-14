#!/bin/bash

# InMemory MCP Tailscale Deployment Stop Script
# This script stops all running servers

echo "🛑 Stopping InMemory MCP Servers"
echo "================================="

# Function to stop server by port
stop_server_by_port() {
    local port=$1
    local server_name=$2
    
    if lsof -ti:$port >/dev/null 2>&1; then
        echo "🔧 Stopping $server_name (port $port)..."
        kill -15 $(lsof -ti:$port) 2>/dev/null || true
        sleep 2
        
        # Force kill if still running
        if lsof -ti:$port >/dev/null 2>&1; then
            echo "   🔨 Force killing $server_name..."
            kill -9 $(lsof -ti:$port) 2>/dev/null || true
            sleep 1
        fi
        
        echo "   ✅ $server_name stopped"
    else
        echo "ℹ️  $server_name not running (port $port)"
    fi
}

# Stop all servers
stop_server_by_port "8000" "Reverse Proxy"
stop_server_by_port "8080" "MCP Server" 
stop_server_by_port "8081" "Core API Server"

echo ""
echo "✅ All servers stopped!"
echo ""
echo "📝 Log files preserved:"
echo "  • Core-API-Server.log"
echo "  • MCP-Server.log" 
echo "  • Reverse-Proxy.log"
echo ""
echo "🚀 To start servers again: ./start_servers.sh"
