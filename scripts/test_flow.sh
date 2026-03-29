#!/bin/bash
# ============================================================
# End-to-End Test Script for Recommender Micro-Mesh
#
# Prerequisites:
#   - All services running (docker compose up --build)
#   - Database seeded (docker compose exec user-service python manage.py seed_data)
#
# Usage:
#   chmod +x scripts/test_flow.sh
#   ./scripts/test_flow.sh
# ============================================================

set -e

GATEWAY="http://localhost:8002"
USER_SVC="http://localhost:8000"
ML_SVC="http://localhost:8001"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN} Recommender Micro-Mesh — E2E Test${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

# --- Test 1: Health Check ---
echo -e "${YELLOW}[TEST 1] Gateway Health Check${NC}"
echo -e "  GET ${GATEWAY}/health"
curl -s "${GATEWAY}/health" | python3 -m json.tool
echo ""

# --- Test 2: ML Service Health ---
echo -e "${YELLOW}[TEST 2] ML Service Health${NC}"
echo -e "  GET ${ML_SVC}/health"
curl -s "${ML_SVC}/health" | python3 -m json.tool
echo ""

# --- Test 3: List Movies ---
echo -e "${YELLOW}[TEST 3] List Movies in Catalog${NC}"
echo -e "  GET ${ML_SVC}/movies"
curl -s "${ML_SVC}/movies" | python3 -m json.tool
echo ""

# --- Test 4: List Users ---
echo -e "${YELLOW}[TEST 4] List Users${NC}"
echo -e "  GET ${USER_SVC}/api/users/"
curl -s "${USER_SVC}/api/users/" | python3 -m json.tool
echo ""

# --- Test 5: Get User Ratings ---
echo -e "${YELLOW}[TEST 5] Get Ratings for User 1 (Alice — Sci-fi fan)${NC}"
echo -e "  GET ${USER_SVC}/api/users/1/ratings/"
curl -s "${USER_SVC}/api/users/1/ratings/" | python3 -m json.tool
echo ""

# --- Test 6: Direct ML Recommendation ---
echo -e "${YELLOW}[TEST 6] Direct Recommendation (ML Service)${NC}"
echo -e "  POST ${ML_SVC}/recommend {user_id: 1, top_n: 5}"
curl -s -X POST "${ML_SVC}/recommend" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "top_n": 5}' | python3 -m json.tool
echo ""

# --- Test 7: Gateway Recommendation (Aggregated) ---
echo -e "${YELLOW}[TEST 7] Gateway Recommendation (Aggregated)${NC}"
echo -e "  GET ${GATEWAY}/recommendations/1"
curl -s "${GATEWAY}/recommendations/1" | python3 -m json.tool
echo ""

# --- Test 8: Recommendations for Bob (Crime fan) ---
echo -e "${YELLOW}[TEST 8] Recommendations for User 2 (Bob — Crime fan)${NC}"
echo -e "  GET ${GATEWAY}/recommendations/2"
curl -s "${GATEWAY}/recommendations/2" | python3 -m json.tool
echo ""

# --- Test 9: Recommendations for Charlie (Animation fan) ---
echo -e "${YELLOW}[TEST 9] Recommendations for User 3 (Charlie — Animation fan)${NC}"
echo -e "  GET ${GATEWAY}/recommendations/3"
curl -s "${GATEWAY}/recommendations/3" | python3 -m json.tool
echo ""

# --- Test 10: Create a new rating and see updated recommendations ---
echo -e "${YELLOW}[TEST 10] Create New Rating → Check Updated Recommendations${NC}"
echo -e "  Step A: Rate 'Fight Club' (ID=6) as User 1"
curl -s -X POST "${USER_SVC}/api/ratings/" \
  -H "Content-Type: application/json" \
  -d '{"user": 1, "movie_id": 6, "score": 4.0}' | python3 -m json.tool
echo ""

echo -e "  Step B: Get updated recommendations for User 1"
echo -e "  (Fight Club's genres should influence new suggestions)"
curl -s "${GATEWAY}/recommendations/1" | python3 -m json.tool
echo ""

# --- Test 11: Unknown user (fallback) ---
echo -e "${YELLOW}[TEST 11] Unknown User (Fallback Recommendations)${NC}"
echo -e "  GET ${GATEWAY}/recommendations/999"
curl -s "${GATEWAY}/recommendations/999" | python3 -m json.tool
echo ""

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN} All tests complete!${NC}"
echo -e "${GREEN}============================================${NC}"
