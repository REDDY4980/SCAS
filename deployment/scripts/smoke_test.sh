#!/usr/bin/env bash
# SCAS post-deployment smoke test.
#
# AIB v1.0 Vol 16.10 Deployment Workflow, step 8: "Execute smoke tests."
#
# Run this AFTER `docker compose up --build` reports all services
# healthy. It exercises the real, live API — not mocks — covering the
# same journey Vol 19.5 describes end-to-end: register, login, create a
# farm, and confirm the API is actually answering, not just that the
# container started.
#
# Usage: ./deployment/scripts/smoke_test.sh [base_url]
# Default base_url: http://localhost:8000

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
PASS=0
FAIL=0

check() {
  local description="$1"
  local actual="$2"
  local expected="$3"
  if [ "$actual" = "$expected" ]; then
    echo "  [PASS] $description"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] $description (expected $expected, got $actual)"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== SCAS Smoke Test against $BASE_URL ==="
echo ""

echo "1. Health check"
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health" || echo "000")
check "GET /health returns 200" "$HEALTH_STATUS" "200"

echo ""
echo "2. API docs available"
DOCS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/docs" || echo "000")
check "GET /docs returns 200" "$DOCS_STATUS" "200"

echo ""
echo "3. Register a smoke-test user"
SMOKE_EMAIL="smoketest+$(date +%s)@example.com"
REGISTER_STATUS=$(curl -s -o /tmp/register_response.json -w "%{http_code}" \
  -X POST "$BASE_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"full_name\":\"Smoke Test\",\"email\":\"$SMOKE_EMAIL\",\"phone\":\"+919000000000\",\"password\":\"SmokeTest123\"}")
check "POST /auth/register returns 201" "$REGISTER_STATUS" "201"

echo ""
echo "4. Login with the new user"
LOGIN_STATUS=$(curl -s -o /tmp/login_response.json -w "%{http_code}" \
  -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"identifier\":\"$SMOKE_EMAIL\",\"password\":\"SmokeTest123\"}")
check "POST /auth/login returns 200" "$LOGIN_STATUS" "200"

TOKEN=$(python3 -c "import json; print(json.load(open('/tmp/login_response.json'))['data']['access_token'])" 2>/dev/null || echo "")

if [ -n "$TOKEN" ]; then
  echo ""
  echo "5. Fetch profile with JWT"
  ME_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/auth/me" \
    -H "Authorization: Bearer $TOKEN")
  check "GET /auth/me with valid token returns 200" "$ME_STATUS" "200"

  echo ""
  echo "6. Reject unauthenticated request"
  UNAUTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/farms")
  check "GET /farms without token returns 401" "$UNAUTH_STATUS" "401"

  echo ""
  echo "7. Create a farm"
  FARM_STATUS=$(curl -s -o /tmp/farm_response.json -w "%{http_code}" \
    -X POST "$BASE_URL/api/v1/farms" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"farm_name":"Smoke Test Farm","state":"Karnataka","district":"Bagalkote"}')
  check "POST /farms returns 201" "$FARM_STATUS" "201"
else
  echo ""
  echo "  [SKIP] Steps 5-7 skipped: could not extract JWT from login response."
  echo "         (jq/python3 unavailable, or login itself failed above.)"
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
rm -f /tmp/register_response.json /tmp/login_response.json /tmp/farm_response.json

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
