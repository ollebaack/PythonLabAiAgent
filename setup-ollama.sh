#!/bin/bash
# Bash script to setup Ollama in Docker and pull the model

echo "🐳 Starting Ollama Docker container..."

# Start the container
docker-compose up -d

# Wait for Ollama to be ready
echo "⏳ Waiting for Ollama to start..."
sleep 5

# Pull the model
echo "📥 Pulling llama3.2 model..."
docker exec ollama ollama pull llama3.2

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Useful commands:"
echo "  - View logs:         docker logs ollama -f"
echo "  - Stop container:    docker-compose down"
echo "  - Pull other models: docker exec ollama ollama pull <model-name>"
echo "  - List models:       docker exec ollama ollama list"
echo ""
