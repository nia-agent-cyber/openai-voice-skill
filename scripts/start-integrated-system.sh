#!/bin/bash
"""
OpenClaw Voice Channel Integration Startup Script

This script starts the complete integrated voice system:
1. Python webhook server (existing)
2. OpenClaw integration bridge (new)
3. TypeScript channel plugin (new)

Prerequisites:
- Python environment with dependencies installed
- Node.js environment with TypeScript compiled
- Environment variables configured
"""

set -e

# Configuration
PYTHON_SERVER_PORT=8080
BRIDGE_SERVER_PORT=8082
TYPESCRIPT_SERVER_PORT=8081

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🎙️ Starting OpenClaw Voice Channel Integration System${NC}"
echo "=================================================="

# Check environment variables
check_env_vars() {
    local required_vars=("OPENAI_API_KEY" "OPENAI_PROJECT_ID")
    local missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing_vars+=("$var")
        fi
    done
    
    if [ ${#missing_vars[@]} -ne 0 ]; then
        echo -e "${RED}❌ Missing required environment variables:${NC}"
        printf '   %s\n' "${missing_vars[@]}"
        echo ""
        echo "Please set these variables and try again."
        exit 1
    fi
    
    echo -e "${GREEN}✅ Required environment variables found${NC}"
}

# Check if ports are available
check_ports() {
    local ports=($PYTHON_SERVER_PORT $BRIDGE_SERVER_PORT $TYPESCRIPT_SERVER_PORT)
    
    for port in "${ports[@]}"; do
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
            echo -e "${RED}❌ Port $port is already in use${NC}"
            echo "Please stop the service using port $port and try again."
            exit 1
        fi
    done
    
    echo -e "${GREEN}✅ All required ports are available${NC}"
}

# Build TypeScript if needed
build_typescript() {
    if [ ! -f "src/channel/voice/index.js" ] || [ "src/channel/voice/index.ts" -nt "src/channel/voice/index.js" ]; then
        echo -e "${YELLOW}🔨 Building TypeScript components...${NC}"
        cd src
        npm run build
        cd ..
        echo -e "${GREEN}✅ TypeScript build completed${NC}"
    else
        echo -e "${GREEN}✅ TypeScript components up to date${NC}"
    fi
}

# Start Python webhook server
start_python_server() {
    echo -e "${YELLOW}🐍 Starting Python webhook server...${NC}"
    
    # Start in background
    python3 scripts/webhook-server.py &
    PYTHON_PID=$!
    
    # Wait for server to be ready
    local max_attempts=10
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:$PYTHON_SERVER_PORT/health > /dev/null; then
            echo -e "${GREEN}✅ Python webhook server ready on port $PYTHON_SERVER_PORT${NC}"
            break
        fi
        
        if [ $attempt -eq $max_attempts ]; then
            echo -e "${RED}❌ Python webhook server failed to start${NC}"
            kill $PYTHON_PID 2>/dev/null || true
            exit 1
        fi
        
        echo "   Waiting for Python server... ($attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done
}

# Start OpenClaw integration bridge
start_bridge_server() {
    echo -e "${YELLOW}🌉 Starting OpenClaw integration bridge...${NC}"
    
    # Set environment variables for bridge
    export TYPESCRIPT_WEBHOOK_URL="http://localhost:$TYPESCRIPT_SERVER_PORT/python-webhook"
    export TYPESCRIPT_HEALTH_URL="http://localhost:$TYPESCRIPT_SERVER_PORT/health"
    export BRIDGE_PORT=$BRIDGE_SERVER_PORT
    
    # Start in background
    python3 scripts/openclaw-webhook-bridge.py &
    BRIDGE_PID=$!
    
    # Wait for bridge to be ready
    local max_attempts=10
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:$BRIDGE_SERVER_PORT/health > /dev/null; then
            echo -e "${GREEN}✅ OpenClaw bridge ready on port $BRIDGE_SERVER_PORT${NC}"
            break
        fi
        
        if [ $attempt -eq $max_attempts ]; then
            echo -e "${RED}❌ OpenClaw bridge failed to start${NC}"
            kill $BRIDGE_PID 2>/dev/null || true
            kill $PYTHON_PID 2>/dev/null || true
            exit 1
        fi
        
        echo "   Waiting for bridge server... ($attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done
}

# Start TypeScript plugin server
start_typescript_server() {
    echo -e "${YELLOW}📱 Starting TypeScript channel plugin...${NC}"
    
    # Start in background with Node.js
    cd src
    node -e "
    const { IntegratedVoiceChannelPlugin } = require('./channel/voice/integrated-plugin');
    const yaml = require('js-yaml');
    const fs = require('fs');
    
    // Load configuration
    const configPath = '../config/integration-config.yaml';
    const config = yaml.load(fs.readFileSync(configPath, 'utf8'));
    
    // Start the plugin
    const plugin = new IntegratedVoiceChannelPlugin(config);
    
    plugin.initialize().then(() => {
        console.log('✅ TypeScript channel plugin ready on port $TYPESCRIPT_SERVER_PORT');
    }).catch(err => {
        console.error('❌ TypeScript plugin failed to start:', err);
        process.exit(1);
    });
    
    // Handle shutdown
    process.on('SIGTERM', () => plugin.shutdown());
    process.on('SIGINT', () => plugin.shutdown());
    " &
    TYPESCRIPT_PID=$!
    cd ..
    
    # Wait for TypeScript server to be ready
    local max_attempts=15
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:$TYPESCRIPT_SERVER_PORT/health > /dev/null; then
            echo -e "${GREEN}✅ TypeScript plugin ready on port $TYPESCRIPT_SERVER_PORT${NC}"
            break
        fi
        
        if [ $attempt -eq $max_attempts ]; then
            echo -e "${RED}❌ TypeScript plugin failed to start${NC}"
            kill $TYPESCRIPT_PID 2>/dev/null || true
            kill $BRIDGE_PID 2>/dev/null || true
            kill $PYTHON_PID 2>/dev/null || true
            exit 1
        fi
        
        echo "   Waiting for TypeScript plugin... ($attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done
}

# Show status and URLs
show_status() {
    echo ""
    echo -e "${GREEN}🎉 OpenClaw Voice Channel Integration System Started!${NC}"
    echo "=================================================="
    echo ""
    echo "Services running:"
    echo -e "  🐍 Python Webhook Server:   ${BLUE}http://localhost:$PYTHON_SERVER_PORT${NC}"
    echo -e "  🌉 OpenClaw Bridge:          ${BLUE}http://localhost:$BRIDGE_SERVER_PORT${NC}"  
    echo -e "  📱 TypeScript Plugin:        ${BLUE}http://localhost:$TYPESCRIPT_SERVER_PORT${NC}"
    echo ""
    echo "Health check URLs:"
    echo "  http://localhost:$PYTHON_SERVER_PORT/health"
    echo "  http://localhost:$BRIDGE_SERVER_PORT/health"
    echo "  http://localhost:$TYPESCRIPT_SERVER_PORT/health"
    echo ""
    echo "OpenClaw Voice API endpoints:"
    echo "  POST http://localhost:$BRIDGE_SERVER_PORT/openclaw/call"
    echo "  GET  http://localhost:$BRIDGE_SERVER_PORT/openclaw/sessions"
    echo "  POST http://localhost:$BRIDGE_SERVER_PORT/openclaw/context"
    echo ""
    echo "Process IDs:"
    echo "  Python Server: $PYTHON_PID"
    echo "  Bridge Server: $BRIDGE_PID"  
    echo "  TypeScript Plugin: $TYPESCRIPT_PID"
    echo ""
    echo -e "${YELLOW}Press Ctrl+C to shutdown all services${NC}"
}

# Cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Shutting down OpenClaw Voice Integration System...${NC}"
    
    # Kill background processes
    kill $TYPESCRIPT_PID 2>/dev/null || true
    kill $BRIDGE_PID 2>/dev/null || true
    kill $PYTHON_PID 2>/dev/null || true
    
    # Wait a moment for graceful shutdown
    sleep 2
    
    # Force kill if still running
    kill -9 $TYPESCRIPT_PID 2>/dev/null || true
    kill -9 $BRIDGE_PID 2>/dev/null || true
    kill -9 $PYTHON_PID 2>/dev/null || true
    
    echo -e "${GREEN}✅ All services stopped${NC}"
    exit 0
}

# Set up signal handling
trap cleanup SIGINT SIGTERM

# Main execution
main() {
    # Pre-flight checks
    check_env_vars
    check_ports
    build_typescript
    
    # Start services
    start_python_server
    start_bridge_server  
    start_typescript_server
    
    # Show status
    show_status
    
    # Keep script running
    while true; do
        # Check if all processes are still running
        if ! kill -0 $PYTHON_PID 2>/dev/null; then
            echo -e "${RED}❌ Python server died${NC}"
            cleanup
        fi
        
        if ! kill -0 $BRIDGE_PID 2>/dev/null; then
            echo -e "${RED}❌ Bridge server died${NC}"  
            cleanup
        fi
        
        if ! kill -0 $TYPESCRIPT_PID 2>/dev/null; then
            echo -e "${RED}❌ TypeScript plugin died${NC}"
            cleanup
        fi
        
        sleep 5
    done
}

# Check if running as source or script
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi