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
    Write-Host "Headers:" -ForegroundColor Cyan
    $Response.Headers | Format-List | Out-String | Write-Host
    
    if ($Response.Headers.Contains("X-Vercel-Error")) {
        Write-Host "Vercel Error Detail: $($Response.Headers['X-Vercel-Error'])" -ForegroundColor Red
    }
    Write-Host "`nResponse Body (Streaming Preview):" -ForegroundColor White
    $Response.Content | Out-String | Write-Host
} catch {
    Write-Host "`nERROR DETECTED!" -ForegroundColor Red
    if ($_.Exception.Response) {
        Write-Host "Status Code: $($_.Exception.Response.StatusCode)" -ForegroundColor Red
        Write-Host "Headers:" -ForegroundColor Yellow
        $_.Exception.Response.Headers | Out-String | Write-Host
        
        if ($_.Exception.Response.Headers.Contains("X-Vercel-Error")) {
            Write-Host "Vercel Error Detail: $($_.Exception.Response.Headers['X-Vercel-Error'])" -ForegroundColor Red
        }
        $Reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $ErrorBody = $Reader.ReadToEnd()
        Write-Host "Error Body: $ErrorBody" -ForegroundColor White
    } else {
        Write-Host "Exception: $($_.Exception.Message)" -ForegroundColor Red
    }
}
