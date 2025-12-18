# Spotify Agent Orchestrator

A Python-based agent orchestration system where agents have individual memory, can use tools, and can call each other as tools. Agents are specialized for interacting with the Spotify API.

## Features

- 🤖 **Agent Orchestration**: Multiple specialized agents that can delegate tasks to each other
- 🧠 **Memory**: Each agent maintains conversation history
- 🔧 **Tools**: Extensible tool system with OpenAI function calling format
- 🎵 **Spotify Integration**: Search tracks, get artist info, playlists, and recommendations
- 🆓 **Free LLM**: Uses Ollama for local, free LLM inference

## Architecture

- **Coordinator Agent**: Routes tasks to specialized agents
- **Search Agent**: Handles track/artist search and recommendations
- **Playlist Agent**: Manages playlist queries
- **Agent-as-Tool**: Agents can call other agents as tools

## Prerequisites

### 1. Install Ollama

#### Option A: Docker (Recommended)

**Prerequisites:**
- Docker Desktop installed ([download here](https://www.docker.com/products/docker-desktop))

**Setup (Windows PowerShell):**
```powershell
.\setup-ollama.ps1
```

**Setup (macOS/Linux):**
```bash
chmod +x setup-ollama.sh
./setup-ollama.sh
```

**Manual Docker Setup:**
```bash
# Start Ollama container
docker-compose up -d

# Pull the model
docker exec ollama ollama pull llama3.2

# Verify it's running
docker logs ollama -f
```

**Useful Docker commands:**
- View logs: `docker logs ollama -f`
- Stop container: `docker-compose down`
- List models: `docker exec ollama ollama list`
- Pull other models: `docker exec ollama ollama pull llama3.1`

Other recommended models:
- `llama3.1` (larger, more capable)
- `mistral` (fast alternative)
- `phi3` (lightweight)

#### Option B: Native Installation

**Windows/macOS/Linux:**
- Download from [https://ollama.ai](https://ollama.ai)
- Install and start Ollama

**Pull a model:**
```bash
ollama pull llama3.2
```

### 2. Get Spotify API Credentials

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Log in with your Spotify account
3. Click "Create App"
4. Fill in app name and description
5. **Important for Playback**: Click "Edit Settings" and add `https://127.0.0.1:8888/callback` to "Redirect URIs"
6. Copy your **Client ID** and **Client Secret**

### 3. Install Python Dependencies

```bash
pip install requests python-dotenv spotipy
```

## Setup

1. **Clone or download this project**

2. **Create `.env` file from template:**
   ```bash
   copy .env.example .env
   ```

3. **Add your Spotify credentials to `.env`:**
   ```
   SPOTIFY_CLIENT_ID=your_actual_client_id
   SPOTIFY_CLIENT_SECRET=your_actual_client_secret
   SPOTIFY_REDIRECT_URI=https://127.0.0.1:8888/callback
   ```
   
   **Note**: For playback features, the first run will open a browser for authorization. After authorizing, you'll be redirected to a 127.0.0.1 URL - just copy that full URL and paste it back in the terminal.

4. **Ensure Ollama is running:**
   - Ollama usually starts automatically after installation
   - Test with: `ollama list`

## Usage

Run the agent orchestrator:

```bash
python agent.py
```

### Example Queries

**Search & Discovery:**
- "Search for Bohemian Rhapsody"
- "Tell me about Taylor Swift as an artist"
- "Find tracks similar to Spotify track ID: 3n3Ppam7vgaVa1iaRUc9Lp"
- "Get the playlist 37i9dQZF1DXcBWIGoYBM5M" (Spotify playlist ID)
- "Recommend songs based on track ID: 11dFghVXANMlKmJXsNCbNl"

**Playback Control (requires authorization):**
- "Play Bohemian Rhapsody by Queen"
- "What's currently playing?"
- "Pause the music"
- "Skip to the next track"
- "Set volume to 50"
- "Resume playback"

### Commands

- Type your question or request
- Type `quit`, `exit`, or `q` to exit
- Press `Ctrl+C` to interrupt

## Project Structure

```
agent.py           # Main orchestrator with Agent, Tool, and SpotifyClient classes
.env               # Your API credentials (create from .env.example)
.env.example       # Template for environment variables
README.md          # This file
```

## How It Works

1. **User Input**: You ask a question about Spotify
2. **Coordinator**: Routes the request to appropriate specialized agent
3. **Specialized Agent**: Uses tools to query Spotify API
4. **LLM Processing**: Ollama processes the query and decides which tools to call
5. **Tool Execution**: Spotify API calls are made via tools
6. **Response**: Agent synthesizes the information and responds

## Customization

### Add New Tools

```python
new_tool = Tool(
    name="your_tool_name",
    description="What your tool does",
    parameters={
        "type": "object",
        "properties": {
            "param_name": {
                "type": "string",
                "description": "Parameter description"
            }
        },
        "required": ["param_name"]
    },
    function=your_function
)

agent.add_tool(new_tool)
```

### Create New Agents

```python
custom_agent = Agent(
    name="Custom Agent",
    system_prompt="You are a specialist in...",
    model="llama3.2"  # or another Ollama model
)
```

### Change LLM Model

Edit the `model` parameter when creating agents:

```python
agent = Agent(name="Agent", system_prompt="...", model="mistral")
```

## Troubleshooting

### "Cannot connect to Ollama"
- Ensure Ollama is installed and running
- Check if the model is downloaded: `ollama list`
- Try pulling the model again: `ollama pull llama3.2`

### "Failed to initialize Spotify"
- Verify `.env` file exists and has correct credentials
- Check credentials are valid at [Spotify Dashboard](https://developer.spotify.com/dashboard)
- Ensure no extra spaces in `.env` file

### Tool calls not working
- Some models handle function calling better than others
- Try `llama3.1` or `llama3.2` for best results
- Check that Ollama is updated to the latest version

## Limitations

- **Spotify Playback**: Client credentials flow doesn't support playback control (requires user OAuth)
- **Rate Limits**: Spotify API has rate limits (typically sufficient for personal use)
- **Local LLM**: Responses depend on the model's capabilities; larger models generally perform better

## License

This project is provided as-is for educational and personal use.

## Resources

- [Ollama Documentation](https://github.com/ollama/ollama)
- [Spotify Web API Documentation](https://developer.spotify.com/documentation/web-api)
- [Spotipy Documentation](https://spotipy.readthedocs.io/)
