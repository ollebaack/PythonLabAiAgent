# PowerShell script to setup Ollama in Docker and pull the model

Write-Host "🐳 Starting Ollama Docker container..." -ForegroundColor Cyan

# Start the container
docker-compose up -d

# Wait for Ollama to be ready
Write-Host "⏳ Waiting for Ollama to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Pull the model
Write-Host "📥 Pulling llama3.2 model..." -ForegroundColor Cyan
docker exec ollama ollama pull llama3.2

Write-Host ""
Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Useful commands:" -ForegroundColor Cyan
Write-Host "  - View logs:         docker logs ollama -f"
Write-Host "  - Stop container:    docker-compose down"
Write-Host "  - Pull other models: docker exec ollama ollama pull <model-name>"
Write-Host "  - List models:       docker exec ollama ollama list"
Write-Host ""
