$Url = "https://chatbot-beta-weld.vercel.app/api/chatbot"
$Body = @{
    input = "Hallo DUB5 AI, ben je online?"
    personality = "general"
    thinking_mode = "balanced"
    model = "auto"
    history = @()
} | ConvertTo-Json

Write-Host "Testing DUB5 AI at $Url..." -ForegroundColor Cyan

try {
    $Response = Invoke-WebRequest -Uri $Url -Method Post -Body $Body -ContentType "application/json" -TimeoutSec 30
    Write-Host "`nStatus Code: $($Response.StatusCode)" -ForegroundColor Green
    Write-Host "Response Headers:" -ForegroundColor Yellow
    $Response.Headers | Out-String | Write-Host
    Write-Host "`nResponse Body (Streaming Preview):" -ForegroundColor White
    $Response.Content | Out-String | Write-Host
} catch {
    Write-Host "`nERROR DETECTED!" -ForegroundColor Red
    if ($_.Exception.Response) {
        Write-Host "Status Code: $($_.Exception.Response.StatusCode)" -ForegroundColor Red
        Write-Host "Headers:" -ForegroundColor Yellow
        $_.Exception.Response.Headers | Out-String | Write-Host
        $Reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $ErrorBody = $Reader.ReadToEnd()
        Write-Host "Error Body: $ErrorBody" -ForegroundColor White
    } else {
        Write-Host "Exception: $($_.Exception.Message)" -ForegroundColor Red
    }
}
