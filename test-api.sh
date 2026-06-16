#!/bin/bash
# API Test Script - проверка всех endpoints

API_URL="http://localhost:8000"
EMAIL="test_$(date +%s)@example.com"
PASSWORD="TestPass123!"
TOKEN=""
ACCESS_TOKEN=""
TASK_ID=""

echo "🧪 AI Healthy API Test Suite"
echo "==============================="
echo "API URL: $API_URL"
echo ""

# 1. Health check
echo "1️⃣ Health Check"
curl -s -X GET "$API_URL/health" | jq . || echo "❌ Failed"
echo ""

# 2. Register
echo "2️⃣ Register User"
REGISTER_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/register" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"$EMAIL\",
    \"password\": \"$PASSWORD\",
    \"full_name\": \"Test User\"
  }")

echo "$REGISTER_RESPONSE" | jq .
USER_ID=$(echo "$REGISTER_RESPONSE" | jq -r '.id // empty')
echo ""

# 3. Login
echo "3️⃣ Login"
LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/login" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"$EMAIL\",
    \"password\": \"$PASSWORD\",
    \"grant_type\": \"password\"
  }")

echo "$LOGIN_RESPONSE" | jq .
ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token // empty')
REFRESH_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.refresh_token // empty')

if [ -z "$ACCESS_TOKEN" ]; then
  echo "❌ Failed to get access token"
  exit 1
fi
echo ""

# 4. Get Profile
echo "4️⃣ Get Profile (/api/v1/me)"
curl -s -X GET "$API_URL/api/v1/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq .
echo ""

# 5. Add Meal
echo "5️⃣ Add Meal (/api/v1/meals)"
ADD_MEAL_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/meals" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"food_name\": \"куриное филе с рисом\",
    \"calories\": 350,
    \"protein_g\": 35,
    \"fat_g\": 8,
    \"carbs_g\": 35,
    \"weight_g\": 200,
    \"meal_type\": \"lunch\"
  }")

echo "$ADD_MEAL_RESPONSE" | jq .
MEAL_ID=$(echo "$ADD_MEAL_RESPONSE" | jq -r '.id // empty')
echo ""

# 6. Get Daily Log
echo "6️⃣ Get Daily Log (/api/v1/daily-log)"
curl -s -X GET "$API_URL/api/v1/daily-log" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq .
echo ""

# 7. Update Meal (if we have a meal ID)
if [ ! -z "$MEAL_ID" ]; then
  echo "7️⃣ Update Meal (/api/v1/meals/$MEAL_ID)"
  curl -s -X PATCH "$API_URL/api/v1/meals/$MEAL_ID" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"food_name\": \"куриное филе с овощами\",
      \"calories\": 300,
      \"protein_g\": 35,
      \"fat_g\": 5,
      \"carbs_g\": 20,
      \"weight_g\": 180,
      \"meal_type\": \"lunch\"
    }" | jq .
  echo ""
fi

# 8. Refresh Token
echo "8️⃣ Refresh Token (/api/v1/token)"
curl -s -X POST "$API_URL/api/v1/token" \
  -H "Content-Type: application/json" \
  -d "{
    \"grant_type\": \"refresh_token\",
    \"refresh_token\": \"$REFRESH_TOKEN\"
  }" | jq .
echo ""

# 9. Get Tasks History
echo "9️⃣ Get Tasks History (/api/v1/tasks)"
curl -s -X GET "$API_URL/api/v1/tasks" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq .
echo ""

# 10. Delete Meal (if we have a meal ID)
if [ ! -z "$MEAL_ID" ]; then
  echo "🔟 Delete Meal (/api/v1/meals/$MEAL_ID)"
  curl -s -X DELETE "$API_URL/api/v1/meals/$MEAL_ID" \
    -H "Authorization: Bearer $ACCESS_TOKEN" | jq .
  echo ""
fi

echo "✅ Test Suite Complete!"
