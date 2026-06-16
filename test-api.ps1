# Test API endpoints using PowerShell
# Usage: .\test-api.ps1

param(
    [string]$ApiUrl = "http://localhost:8000"
)

function Test-Endpoint {
    param(
        [string]$Method,
        [string]$Endpoint,
        [object]$Body,
        [string]$Token
    )
    
    $uri = "$ApiUrl$Endpoint"
    $headers = @{ "Content-Type" = "application/json" }
    
    if ($Token) {
        $headers["Authorization"] = "Bearer $Token"
    }
    
    Write-Host ""
    Write-Host "📍 $Method $Endpoint" -ForegroundColor Cyan
    Write-Host "---" -ForegroundColor Gray
    
    try {
        if ($Body) {
            $response = Invoke-RestMethod -Uri $uri -Method $Method -Headers $headers -Body ($Body | ConvertTo-Json)
        } else {
            $response = Invoke-RestMethod -Uri $uri -Method $Method -Headers $headers
        }
        
        Write-Host ($response | ConvertTo-Json -Depth 3) -ForegroundColor Green
        return $response
    }
    catch {
        Write-Host "❌ Error: $($_.Exception.Message)" -ForegroundColor Red
        if ($_.Exception.Response) {
            Write-Host "Status: $($_.Exception.Response.StatusCode)" -ForegroundColor Red
        }
        return $null
    }
}

Write-Host "🧪 AI Healthy API Test Suite" -ForegroundColor Yellow
Write-Host "API URL: $ApiUrl" -ForegroundColor Cyan
Write-Host ""

# Test variables
$email = "test_$(Get-Random)@example.com"
$password = "TestPass123!"
$token = $null
$refreshToken = $null
$mealId = $null

# 1. Health Check
Write-Host "1️⃣  Health Check" -ForegroundColor Yellow
Test-Endpoint -Method "GET" -Endpoint "/health" | Out-Null

# 2. Register
Write-Host "2️⃣  Register User" -ForegroundColor Yellow
$registerBody = @{
    email = $email
    password = $password
    full_name = "Test User"
}
$registerResponse = Test-Endpoint -Method "POST" -Endpoint "/api/v1/register" -Body $registerBody

# 3. Login
Write-Host "3️⃣  Login" -ForegroundColor Yellow
$loginBody = @{
    email = $email
    password = $password
    grant_type = "password"
}
$loginResponse = Test-Endpoint -Method "POST" -Endpoint "/api/v1/login" -Body $loginBody

if ($loginResponse) {
    $token = $loginResponse.access_token
    $refreshToken = $loginResponse.refresh_token
    Write-Host "✅ Login successful, token: $($token.Substring(0, 20))..." -ForegroundColor Green
}
else {
    Write-Host "❌ Login failed, stopping tests" -ForegroundColor Red
    exit 1
}

# 4. Get Profile
Write-Host "4️⃣  Get Profile" -ForegroundColor Yellow
Test-Endpoint -Method "GET" -Endpoint "/api/v1/me" -Token $token | Out-Null

# 5. Add Meal
Write-Host "5️⃣  Add Meal" -ForegroundColor Yellow
$mealBody = @{
    food_name = "куриное филе с рисом"
    calories = 350
    protein_g = 35
    fat_g = 8
    carbs_g = 35
    weight_g = 200
    meal_type = "lunch"
}
$mealResponse = Test-Endpoint -Method "POST" -Endpoint "/api/v1/meals" -Body $mealBody -Token $token
if ($mealResponse) {
    $mealId = $mealResponse.id
}

# 6. Get Daily Log
Write-Host "6️⃣  Get Daily Log" -ForegroundColor Yellow
Test-Endpoint -Method "GET" -Endpoint "/api/v1/daily-log" -Token $token | Out-Null

# 7. Update Meal (if we have a meal ID)
if ($mealId) {
    Write-Host "7️⃣  Update Meal" -ForegroundColor Yellow
    $updateBody = @{
        food_name = "куриное филе с овощами"
        calories = 300
        protein_g = 35
        fat_g = 5
        carbs_g = 20
        weight_g = 180
        meal_type = "lunch"
    }
    Test-Endpoint -Method "PATCH" -Endpoint "/api/v1/meals/$mealId" -Body $updateBody -Token $token | Out-Null
}

# 8. Refresh Token
Write-Host "8️⃣  Refresh Token" -ForegroundColor Yellow
$refreshBody = @{
    grant_type = "refresh_token"
    refresh_token = $refreshToken
}
Test-Endpoint -Method "POST" -Endpoint "/api/v1/token" -Body $refreshBody | Out-Null

# 9. Get Tasks History
Write-Host "9️⃣  Get Tasks History" -ForegroundColor Yellow
Test-Endpoint -Method "GET" -Endpoint "/api/v1/tasks" -Token $token | Out-Null

# 10. Delete Meal (if we have a meal ID)
if ($mealId) {
    Write-Host "🔟 Delete Meal" -ForegroundColor Yellow
    Test-Endpoint -Method "DELETE" -Endpoint "/api/v1/meals/$mealId" -Token $token | Out-Null
}

Write-Host ""
Write-Host "✅ Test Suite Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Quick Commands:" -ForegroundColor Cyan
Write-Host "  curl http://localhost:8000/health" -ForegroundColor Gray
Write-Host "  curl -X POST http://localhost:8000/api/v1/register \" -ForegroundColor Gray
Write-Host "    -H 'Content-Type: application/json' \" -ForegroundColor Gray
Write-Host "    -d '{\"email\":\"user@example.com\",\"password\":\"pass123\"}'" -ForegroundColor Gray
