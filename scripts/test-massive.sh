#!/usr/bin/env bash
# ==============================================================================
# Project Alex - Massive/Polygon.io API Connection Test Script
# Tests Polygon.io REST API endpoints for stock market price retrieval
# ==============================================================================

set -e

# Colors for terminal formatting
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Determine project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load .env file if present
if [ -f "$PROJECT_ROOT/.env" ]; then
  # Export lines from .env ignoring comments
  export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
fi

API_KEY="${POLYGON_API_KEY:-}"
PLAN="${POLYGON_PLAN:-free}"

echo "📊 Project Alex - Polygon/Massive API Test"
echo "=================================================="

if [ -z "$API_KEY" ]; then
  echo -e "${RED}❌ Error: POLYGON_API_KEY is not set in environment or .env file.${NC}"
  echo "   Sign up for a free key at https://polygon.io and set POLYGON_API_KEY in .env"
  exit 1
fi

echo -e "API Key:  ${YELLOW}${API_KEY:0:6}****************${NC}"
echo -e "Plan:     ${YELLOW}${PLAN}${NC}"
echo "=================================================="
echo ""

# Test 1: Market Status Check
echo -n "1. Testing Market Status Endpoint (/v1/marketstatus/now)... "
STATUS_RESPONSE=$(curl -s "https://api.polygon.io/v1/marketstatus/now?apiKey=${API_KEY}")

if echo "$STATUS_RESPONSE" | grep -q '"market"'; then
  MARKET_STATE=$(echo "$STATUS_RESPONSE" | jq -r '.market // "unknown"')
  SERVER_TIME=$(echo "$STATUS_RESPONSE" | jq -r '.serverTime // "N/A"')
  echo -e "${GREEN}SUCCESS (Status 200)${NC}"
  echo -e "   Market State: ${YELLOW}${MARKET_STATE}${NC} | Server Time: ${SERVER_TIME}"
else
  echo -e "${RED}FAILED${NC}"
  echo "   Response: $STATUS_RESPONSE"
fi

echo ""

# Test 2: Ticker Previous Close (SPY)
echo -n "2. Testing Previous Close Aggregate for SPY (/v2/aggs/ticker/SPY/prev)... "
PREV_RESPONSE=$(curl -s "https://api.polygon.io/v2/aggs/ticker/SPY/prev?adjusted=true&apiKey=${API_KEY}")

if echo "$PREV_RESPONSE" | grep -q '"results"'; then
  SPY_CLOSE=$(echo "$PREV_RESPONSE" | jq -r '.results[0].c // "N/A"')
  SPY_VOL=$(echo "$PREV_RESPONSE" | jq -r '.results[0].v // "N/A"')
  echo -e "${GREEN}SUCCESS (Status 200)${NC}"
  echo -e "   SPY Close Price: ${GREEN}\$${SPY_CLOSE}${NC} | Volume: ${SPY_VOL}"
else
  echo -e "${YELLOW}WARNING / FAILED${NC}"
  ERROR_MSG=$(echo "$PREV_RESPONSE" | jq -r '.message // .error // "Unknown error"')
  echo "   Response Message: $ERROR_MSG"
  
  if echo "$PREV_RESPONSE" | grep -q -i "NOT_AUTHORIZED"; then
    echo -e "   ${YELLOW}💡 Note: Free Polygon plan limits today's data access until end-of-day UTC.${NC}"
  elif echo "$PREV_RESPONSE" | grep -q -i "429"; then
    echo -e "   ${RED}💡 Note: Rate limit exceeded (5 requests/minute for free tier).${NC}"
  fi
fi

echo ""

# Test 3: Snapshot Ticker Test (for Paid Plan or Free Single Quote)
echo -n "3. Testing Single Ticker Snapshot for AAPL (/v2/snapshot/locale/us/markets/stocks/tickers/AAPL)... "
SNAP_RESPONSE=$(curl -s "https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/AAPL?apiKey=${API_KEY}")

if echo "$SNAP_RESPONSE" | grep -q '"ticker"'; then
  AAPL_MIN=$(echo "$SNAP_RESPONSE" | jq -r '.ticker.min.c // .ticker.prevDay.c // "N/A"')
  echo -e "${GREEN}SUCCESS (Status 200)${NC}"
  echo -e "   AAPL Price: ${GREEN}\$${AAPL_MIN}${NC}"
else
  STATUS_ERR=$(echo "$SNAP_RESPONSE" | jq -r '.status // .message // "NOT_AUTHORIZED"')
  echo -e "${YELLOW}SKIPPED / LIMITED (${STATUS_ERR})${NC}"
  if [ "$PLAN" == "free" ]; then
    echo "   (Snapshot API requires a Polygon Paid Plan. On free tier, Alex falls back to EOD batch aggs)."
  fi
fi

echo ""
echo "=================================================="
echo -e "${GREEN}🎉 Polygon/Massive API connectivity test finished!${NC}"
