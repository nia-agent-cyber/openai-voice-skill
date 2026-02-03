#!/bin/bash
"""
OpenClaw Voice Channel Integration Test Script

This script tests the complete integration between the TypeScript plugin,
integration bridge, and Python webhook server.
"""

set -e

# Configuration
BRIDGE_URL="http://localhost:8082"
PYTHON_URL="http://localhost:8080" 
TYPESCRIPT_URL="http://localhost:8081"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🧪 Testing OpenClaw Voice Channel Integration${NC}"
echo "=============================================="

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Test function
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo -n "Testing $test_name... "
    
    if eval "$test_command" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ PASS${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}❌ FAIL${NC}"
        ((TESTS_FAILED++))
    fi
}

# Health check tests
echo -e "\n${YELLOW}📋 Health Check Tests${NC}"
echo "----------------------"

run_test "Python webhook server health" \
    "curl -s -f $PYTHON_URL/health | grep -q 'ok'"

run_test "Integration bridge health" \
    "curl -s -f $BRIDGE_URL/health | grep -q 'healthy'"

run_test "TypeScript plugin health" \
    "curl -s -f $TYPESCRIPT_URL/health | grep -q 'healthy'"

# Connectivity tests  
echo -e "\n${YELLOW}🔌 Connectivity Tests${NC}"
echo "----------------------"

run_test "Bridge can reach Python server" \
    "curl -s -f $BRIDGE_URL/health | grep -q 'main_server.*healthy'"

run_test "Bridge can reach TypeScript plugin" \
    "curl -s -f $BRIDGE_URL/health | grep -q 'typescript_plugin.*healthy'"

# API endpoint tests
echo -e "\n${YELLOW}🌐 API Endpoint Tests${NC}"
echo "----------------------"

run_test "Python server root endpoint" \
    "curl -s -f $PYTHON_URL/ | grep -q 'OpenAI Voice Server'"

run_test "Bridge OpenClaw sessions endpoint" \
    "curl -s -f $BRIDGE_URL/openclaw/sessions | grep -q 'active_sessions'"

run_test "TypeScript plugin status endpoint" \
    "curl -s -f $TYPESCRIPT_URL/status | grep -q 'voice_channel_plugin'"

# Configuration tests
echo -e "\n${YELLOW}⚙️ Configuration Tests${NC}"
echo "----------------------"

run_test "Python server has required environment" \
    "curl -s -f $PYTHON_URL/health | grep -q 'agent'"

run_test "Integration config file exists" \
    "test -f config/integration-config.yaml"

run_test "TypeScript build files exist" \
    "test -f src/channel/voice/integrated-plugin.js || test -f src/channel/voice/integrated-plugin.ts"

# Mock call test (if supported)
echo -e "\n${YELLOW}📞 Mock Call Test${NC}" 
echo "-------------------"

# Test session creation and mapping
TEST_SESSION_ID="test_$(date +%s)"
MOCK_CALL_PAYLOAD='{
    "to": "+15551234567",
    "openclaw_session_id": "'$TEST_SESSION_ID'",
    "context": {
        "agent_identity": "Test assistant",
        "test_mode": true
    }
}'

echo -n "Testing OpenClaw session creation... "
if curl -s -X POST "$BRIDGE_URL/openclaw/call" \
    -H "Content-Type: application/json" \
    -d "$MOCK_CALL_PAYLOAD" | grep -q "initiated"; then
    echo -e "${GREEN}✅ PASS${NC}"
    ((TESTS_PASSED++))
    
    # Test session retrieval
    echo -n "Testing session retrieval... "
    if curl -s -f "$BRIDGE_URL/openclaw/session/$TEST_SESSION_ID" | grep -q "$TEST_SESSION_ID"; then
        echo -e "${GREEN}✅ PASS${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}❌ FAIL${NC}"
        ((TESTS_FAILED++))
    fi
    
    # Cleanup test session
    curl -s -X DELETE "$BRIDGE_URL/openclaw/call/$TEST_SESSION_ID" >/dev/null || true
    
else
    echo -e "${RED}❌ FAIL${NC}"
    ((TESTS_FAILED++))
fi

# Integration flow test
echo -e "\n${YELLOW}🔄 Integration Flow Test${NC}"
echo "-------------------------"

# Test webhook event forwarding
MOCK_WEBHOOK_EVENT='{
    "call_id": "test_call_123",
    "event_type": "call_ringing", 
    "data": {
        "phone_number": "+15551234567",
        "direction": "outbound"
    }
}'

run_test "Webhook event forwarding" \
    "curl -s -X POST $BRIDGE_URL/webhook/forward \
     -H 'Content-Type: application/json' \
     -d '$MOCK_WEBHOOK_EVENT' | grep -q 'forwarded'"

# Performance tests
echo -e "\n${YELLOW}⚡ Performance Tests${NC}"
echo "--------------------"

run_test "Python server response time < 1s" \
    "timeout 1s curl -s $PYTHON_URL/health >/dev/null"

run_test "Bridge response time < 1s" \
    "timeout 1s curl -s $BRIDGE_URL/health >/dev/null"

run_test "TypeScript plugin response time < 2s" \
    "timeout 2s curl -s $TYPESCRIPT_URL/health >/dev/null"

# Security tests
echo -e "\n${YELLOW}🔒 Security Tests${NC}"
echo "------------------"

run_test "Python server rejects invalid JSON" \
    "! curl -s -X POST $PYTHON_URL/call -d 'invalid json' | grep -q 'call_id'"

run_test "Bridge validates session IDs" \
    "curl -s $BRIDGE_URL/openclaw/session/invalid_session_id | grep -q '404'"

# Summary
echo -e "\n${BLUE}📊 Test Results Summary${NC}"
echo "========================"
echo -e "Tests passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests failed: ${RED}$TESTS_FAILED${NC}"
echo -e "Total tests: $((TESTS_PASSED + TESTS_FAILED))"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}🎉 All tests passed! Integration is working correctly.${NC}"
    
    # Show integration status
    echo -e "\n${BLUE}📈 Integration Status${NC}"
    echo "-------------------"
    
    echo "Service URLs:"
    echo "  Python Server:    $PYTHON_URL"
    echo "  Integration Bridge: $BRIDGE_URL"  
    echo "  TypeScript Plugin: $TYPESCRIPT_URL"
    echo ""
    
    # Get session counts
    PYTHON_CALLS=$(curl -s $PYTHON_URL/calls | jq -r '.active_calls // 0' 2>/dev/null || echo "N/A")
    BRIDGE_SESSIONS=$(curl -s $BRIDGE_URL/openclaw/sessions | jq -r '.active_sessions // 0' 2>/dev/null || echo "N/A")
    
    echo "Current state:"
    echo "  Active Python calls: $PYTHON_CALLS"
    echo "  Active OpenClaw sessions: $BRIDGE_SESSIONS"
    
    exit 0
else
    echo -e "\n${RED}❌ Some tests failed. Please check the services and configuration.${NC}"
    
    echo -e "\n${YELLOW}💡 Troubleshooting Tips:${NC}"
    echo "- Ensure all services are running: ./scripts/start-integrated-system.sh"
    echo "- Check environment variables are set properly"
    echo "- Review service logs for error details"
    echo "- Verify network connectivity between services"
    
    exit 1
fi