#!/bin/bash
#
# Fix Bridge Port Conflict
# 
# Stops the Python bridge and ensures TypeScript session-bridge runs on port 8082
#
# Usage: ./fix-bridge-conflict.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}🔧 Fixing Bridge Port Conflict${NC}"
echo "=============================="
echo ""

# Step 1: Kill Python bridge
echo -e "${YELLOW}Step 1: Stopping Python bridge...${NC}"
if pgrep -f "openclaw-webhook-bridge.py" > /dev/null; then
    pkill -f "openclaw-webhook-bridge.py" || true
    sleep 1
    echo -e "${GREEN}✅ Python bridge stopped${NC}"
else
    echo -e "${GREEN}✅ Python bridge not running${NC}"
fi

# Step 2: Check port 8082 is free
echo ""
echo -e "${YELLOW}Step 2: Checking port 8082...${NC}"
if lsof -i :8082 -sTCP:LISTEN > /dev/null 2>&1; then
    echo -e "${RED}⚠️  Port 8082 still in use:${NC}"
    lsof -i :8082
    echo ""
    echo "Please kill that process manually and re-run this script."
    exit 1
else
    echo -e "${GREEN}✅ Port 8082 is free${NC}"
fi

# Step 3: Restart OpenClaw gateway (which starts TS bridge)
echo ""
echo -e "${YELLOW}Step 3: Restarting OpenClaw gateway...${NC}"
if command -v openclaw &> /dev/null; then
    openclaw gateway restart
    sleep 3
    echo -e "${GREEN}✅ Gateway restarted${NC}"
else
    echo -e "${YELLOW}⚠️  'openclaw' command not found${NC}"
    echo "   You may need to start the TS bridge manually:"
    echo "   cd channel-plugin && node -e \"require('./dist/adapters/session-bridge.js').createSessionBridge({port:8082,webhookServerUrl:'http://localhost:8080'}).start()\""
fi

# Step 4: Verify the bridge
echo ""
echo -e "${YELLOW}Step 4: Verifying TypeScript bridge...${NC}"
sleep 2
if curl -s http://localhost:8082/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Bridge is responding on port 8082${NC}"
    echo ""
    echo "Health check response:"
    curl -s http://localhost:8082/health | jq . 2>/dev/null || curl -s http://localhost:8082/health
else
    echo -e "${RED}⚠️  Bridge not responding on port 8082${NC}"
    echo ""
    echo "The gateway may not have started the bridge automatically."
    echo "Check gateway logs: openclaw gateway logs"
    echo ""
    echo "Manual start (for testing):"
    echo "  cd /Users/ec2-user/.openclaw/workspace/openai-voice-skill/channel-plugin"
    echo "  node dist/adapters/session-bridge.js"
fi

# Step 5: Test the critical endpoint
echo ""
echo -e "${YELLOW}Step 5: Testing /call-event endpoint...${NC}"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST http://localhost:8082/call-event \
  -H "Content-Type: application/json" \
  -d '{"callId":"test-fix","eventType":"call_started","phoneNumber":"+1234567890","direction":"inbound","timestamp":"2026-02-04T14:00:00Z"}' 2>/dev/null || echo -e "\n000")

HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ /call-event endpoint working!${NC}"
    echo "Response: $BODY"
else
    echo -e "${RED}⚠️  /call-event endpoint returned HTTP $HTTP_CODE${NC}"
    echo "Response: $BODY"
    echo ""
    echo "This is the key endpoint that call_recording.py needs."
fi

echo ""
echo "=============================="
echo -e "${GREEN}🎉 Bridge conflict resolution complete!${NC}"
echo ""
echo "Summary:"
echo "  • Python bridge: STOPPED"
echo "  • TypeScript bridge (port 8082): should be running"
echo "  • /call-event endpoint: tested"
echo ""
echo "If issues persist, see: docs/bridge-cleanup.md"
