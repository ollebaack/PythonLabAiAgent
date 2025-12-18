"""
Spotify-Specialized Agent Orchestrator
An agent system where agents have memory, tools, and can call each other.
Uses Ollama for LLM inference and Spotify API for music operations.
"""

import os
import json
import requests
from typing import List, Dict, Any, Callable, Optional
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth


# ==================== Core Classes ====================

class Tool:
    """Represents a callable tool with OpenAI function schema."""
    
    def __init__(self, name: str, description: str, parameters: Dict[str, Any], function: Callable):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.function = function
    
    def to_schema(self) -> Dict[str, Any]:
        """Convert tool to OpenAI function calling schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }
    
    def execute(self, **kwargs) -> str:
        """Execute the tool function with given arguments."""
        try:
            result = self.function(**kwargs)
            return str(result)
        except Exception as e:
            return f"Error executing {self.name}: {str(e)}"
    
    @classmethod
    def from_agent(cls, agent: 'Agent') -> 'Tool':
        """Create a Tool from an Agent, enabling agent-as-tool pattern."""
        def agent_function(task: str) -> str:
            return agent.execute(task)
        
        return cls(
            name=f"call_{agent.name.lower().replace(' ', '_')}",
            description=f"Delegate a task to the {agent.name}. {agent.system_prompt}",
            parameters={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "The task or question to ask the agent"
                    }
                },
                "required": ["task"]
            },
            function=agent_function
        )


class Agent:
    """An agent with memory, tools, and the ability to call an LLM."""
    
    def __init__(self, name: str, system_prompt: str, model: str = "llama3.2"):
        self.name = name
        self.system_prompt = system_prompt
        self.model = model
        self.tools: Dict[str, Tool] = {}
        self.memory: List[Dict[str, Any]] = []
        self.ollama_url = "http://localhost:11434/api/chat"
    
    def add_tool(self, tool: Tool):
        """Register a tool with this agent."""
        self.tools[tool.name] = tool
        print(f"[{self.name}] Added tool: {tool.name}")
    
    def execute(self, user_input: str, max_iterations: int = 10) -> str:
        """Execute agent with user input, handling tool calls in a loop."""
        # Add user message to memory
        self.memory.append({"role": "user", "content": user_input})
        
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            
            # Prepare messages for LLM. TODO: self.memory shouldn't be system prompt
            messages = [{"role": "system", "content": self.system_prompt}] + self.memory
            
            # Prepare tools schema
            tools_schema = [tool.to_schema() for tool in self.tools.values()] if self.tools else None
            
            # Call Ollama with retry logic
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    response = self._call_ollama(messages, tools_schema)
                    
                    # Check if response contains tool calls
                    if response.get("message", {}).get("tool_calls"):
                        # Add assistant message with tool calls to memory
                        self.memory.append(response["message"])
                        
                        # Execute each tool call
                        for tool_call in response["message"]["tool_calls"]:
                            tool_name = tool_call["function"]["name"]
                            tool_args = tool_call["function"]["arguments"]
                            
                            print(f"[{self.name}] Calling tool: {tool_name} with args: {tool_args}")
                            
                            if tool_name in self.tools:
                                result = self.tools[tool_name].execute(**tool_args)
                            else:
                                result = f"Error: Tool {tool_name} not found"
                            
                            # Add tool result to memory
                            self.memory.append({
                                "role": "tool",
                                "content": result
                            })
                        
                        # Continue loop to let agent process tool results
                        break  # Break retry loop, continue main loop
                    else:
                        # No tool calls, we have final response
                        assistant_message = response["message"]["content"]
                        
                        # Validate response is not hallucinated JSON
                        if self._is_hallucinated_response(assistant_message):
                            print(f"[{self.name}] Detected hallucinated response, retrying...")
                            if attempt < max_retries - 1:
                                # Add correction message
                                self.memory.append({
                                    "role": "system",
                                    "content": "You MUST respond in natural language to the user. Do NOT output JSON or tool calls as text. Based on the tool results you received, provide a clear answer to the user's question."
                                })
                                continue  # Retry
                            else:
                                # Last attempt failed, return error
                                return "I apologize, but I'm having trouble generating a proper response. Please try rephrasing your question."
                        
                        self.memory.append({"role": "assistant", "content": assistant_message})
                        return assistant_message
                        
                except Exception as e:
                    error_msg = f"Error calling LLM: {str(e)}"
                    print(f"[{self.name}] {error_msg}")
                    if attempt < max_retries - 1:
                        continue  # Retry
                    return error_msg
        
        return "Max iterations reached without final answer."
    
    def _is_hallucinated_response(self, response: str) -> bool:
        """Detect if the response is a hallucinated JSON/tool call instead of natural language."""
        response = response.strip()
        # Check for common hallucination patterns
        hallucination_indicators = [
            response.startswith('{"name":'),
            response.startswith('{"parameters":'),
            'call_search_agent' in response and '{' in response,
            'call_playback_agent' in response and '{' in response,
            'call_playlist_agent' in response and '{' in response,
        ]
        return any(hallucination_indicators)
    
    def _call_ollama(self, messages: List[Dict], tools: Optional[List[Dict]] = None) -> Dict:
        """Call Ollama API with OpenAI-compatible format."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }
        
        if tools:
            payload["tools"] = tools
        
        response = requests.post(self.ollama_url, json=payload)
        response.raise_for_status()
        return response.json()


class SpotifyClient:
    """Wrapper for Spotify API using spotipy."""
    
    def __init__(self):
        load_dotenv()
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            raise ValueError("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set in .env file")
        
        auth_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret
        )
        self.client = spotipy.Spotify(auth_manager=auth_manager)
    
    def search_track(self, query: str, limit: int = 5) -> Dict:
        """Search for tracks on Spotify."""
        results = self.client.search(q=query, type='track', limit=limit)
        tracks = []
        for item in results['tracks']['items']:
            tracks.append({
                'name': item['name'],
                'artist': item['artists'][0]['name'],
                'album': item['album']['name'],
                'id': item['id'],
                'uri': item['uri']
            })
        return {'tracks': tracks}
    
    def get_track_info(self, track_id: str) -> Dict:
        """Get detailed information about a track."""
        track = self.client.track(track_id)
        return {
            'name': track['name'],
            'artists': [artist['name'] for artist in track['artists']],
            'album': track['album']['name'],
            'duration_ms': track['duration_ms'],
            'popularity': track['popularity'],
            'uri': track['uri']
        }
    
    def get_artist_info(self, artist_id: str) -> Dict:
        """Get detailed information about an artist."""
        artist = self.client.artist(artist_id)
        return {
            'name': artist['name'],
            'genres': artist['genres'],
            'popularity': artist['popularity'],
            'followers': artist['followers']['total'],
            'uri': artist['uri']
        }
    
    def get_recommendations(self, seed_tracks: List[str], limit: int = 5) -> Dict:
        """Get track recommendations based on seed tracks."""
        results = self.client.recommendations(seed_tracks=seed_tracks[:5], limit=limit)
        tracks = []
        for item in results['tracks']:
            tracks.append({
                'name': item['name'],
                'artist': item['artists'][0]['name'],
                'id': item['id'],
                'uri': item['uri']
            })
        return {'recommendations': tracks}
    
    def get_playlist(self, playlist_id: str) -> Dict:
        """Get playlist information and tracks."""
        playlist = self.client.playlist(playlist_id)
        tracks = []
        for item in playlist['tracks']['items']:
            if item['track']:
                tracks.append({
                    'name': item['track']['name'],
                    'artist': item['track']['artists'][0]['name'],
                    'id': item['track']['id']
                })
        return {
            'name': playlist['name'],
            'description': playlist['description'],
            'tracks': tracks[:10]  # Limit to first 10 tracks
        }


class SpotifyPlaybackClient:
    """Wrapper for Spotify Playback API using OAuth (requires user authorization)."""
    
    def __init__(self):
        load_dotenv()
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "https://127.0.0.1:8888/callback")
        
        if not client_id or not client_secret:
            raise ValueError("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set in .env file")
        
        # Required scopes for playback control
        scope = "user-modify-playback-state user-read-playback-state user-read-currently-playing"
        
        auth_manager = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=scope,
            cache_path=".spotify_cache"
        )
        self.client = spotipy.Spotify(auth_manager=auth_manager)
    
    def play_track(self, track_uri: str, device_id: Optional[str] = None) -> Dict:
        """Play a specific track by URI."""
        try:
            self.client.start_playback(device_id=device_id, uris=[track_uri])
            return {"status": "success", "message": f"Playing track: {track_uri}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def play_tracks(self, track_uris: List[str], device_id: Optional[str] = None) -> Dict:
        """Play multiple tracks by URIs."""
        try:
            self.client.start_playback(device_id=device_id, uris=track_uris)
            return {"status": "success", "message": f"Playing {len(track_uris)} tracks"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def pause_playback(self, device_id: Optional[str] = None) -> Dict:
        """Pause current playback."""
        try:
            self.client.pause_playback(device_id=device_id)
            return {"status": "success", "message": "Playback paused"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def resume_playback(self, device_id: Optional[str] = None) -> Dict:
        """Resume current playback."""
        try:
            self.client.start_playback(device_id=device_id)
            return {"status": "success", "message": "Playback resumed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def skip_to_next(self, device_id: Optional[str] = None) -> Dict:
        """Skip to next track."""
        try:
            self.client.next_track(device_id=device_id)
            return {"status": "success", "message": "Skipped to next track"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def skip_to_previous(self, device_id: Optional[str] = None) -> Dict:
        """Skip to previous track."""
        try:
            self.client.previous_track(device_id=device_id)
            return {"status": "success", "message": "Skipped to previous track"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def set_volume(self, volume_percent: int, device_id: Optional[str] = None) -> Dict:
        """Set playback volume (0-100)."""
        try:
            volume_percent = max(0, min(100, volume_percent))  # Clamp to 0-100
            self.client.volume(volume_percent, device_id=device_id)
            return {"status": "success", "message": f"Volume set to {volume_percent}%"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def get_current_playback(self) -> Dict:
        """Get information about current playback."""
        try:
            playback = self.client.current_playback()
            if not playback:
                return {"status": "no_playback", "message": "No active playback"}
            
            track = playback.get('item', {})
            return {
                "status": "playing" if playback['is_playing'] else "paused",
                "track_name": track.get('name', 'Unknown'),
                "artist": track.get('artists', [{}])[0].get('name', 'Unknown'),
                "album": track.get('album', {}).get('name', 'Unknown'),
                "progress_ms": playback.get('progress_ms', 0),
                "duration_ms": track.get('duration_ms', 0),
                "volume_percent": playback.get('device', {}).get('volume_percent', 0),
                "device_name": playback.get('device', {}).get('name', 'Unknown')
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def get_available_devices(self) -> Dict:
        """Get list of available playback devices."""
        try:
            devices = self.client.devices()
            device_list = []
            for device in devices.get('devices', []):
                device_list.append({
                    'id': device['id'],
                    'name': device['name'],
                    'type': device['type'],
                    'is_active': device['is_active'],
                    'volume_percent': device['volume_percent']
                })
            return {"status": "success", "devices": device_list}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ==================== Spotify Tool Functions ====================

def create_spotify_tools(spotify_client: SpotifyClient) -> List[Tool]:
    """Create Spotify-specialized tools."""
    
    tools = [
        Tool(
            name="search_track",
            description="Search for tracks on Spotify by query string",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (song name, artist, album, etc.)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of results to return (default 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            },
            function=lambda query, limit=5: json.dumps(spotify_client.search_track(query, limit), indent=2)
        ),
        Tool(
            name="get_track_info",
            description="Get detailed information about a specific track by ID",
            parameters={
                "type": "object",
                "properties": {
                    "track_id": {
                        "type": "string",
                        "description": "Spotify track ID"
                    }
                },
                "required": ["track_id"]
            },
            function=lambda track_id: json.dumps(spotify_client.get_track_info(track_id), indent=2)
        ),
        Tool(
            name="get_artist_info",
            description="Get detailed information about an artist by ID",
            parameters={
                "type": "object",
                "properties": {
                    "artist_id": {
                        "type": "string",
                        "description": "Spotify artist ID"
                    }
                },
                "required": ["artist_id"]
            },
            function=lambda artist_id: json.dumps(spotify_client.get_artist_info(artist_id), indent=2)
        ),
        Tool(
            name="get_recommendations",
            description="Get track recommendations based on seed track IDs",
            parameters={
                "type": "object",
                "properties": {
                    "seed_tracks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of track IDs to base recommendations on (max 5)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of recommendations to return (default 5)",
                        "default": 5
                    }
                },
                "required": ["seed_tracks"]
            },
            function=lambda seed_tracks, limit=5: json.dumps(
                spotify_client.get_recommendations(seed_tracks, limit), indent=2
            )
        ),
        Tool(
            name="get_playlist",
            description="Get playlist information and tracks by playlist ID",
            parameters={
                "type": "object",
                "properties": {
                    "playlist_id": {
                        "type": "string",
                        "description": "Spotify playlist ID"
                    }
                },
                "required": ["playlist_id"]
            },
            function=lambda playlist_id: json.dumps(spotify_client.get_playlist(playlist_id), indent=2)
        )
    ]
    
    return tools


def create_playback_tools(playback_client: SpotifyPlaybackClient) -> List[Tool]:
    """Create Spotify playback control tools."""
    
    tools = [
        Tool(
            name="play_track",
            description="Play a specific track by Spotify URI (e.g., spotify:track:xxxxx)",
            parameters={
                "type": "object",
                "properties": {
                    "track_uri": {
                        "type": "string",
                        "description": "Spotify track URI to play"
                    }
                },
                "required": ["track_uri"]
            },
            function=lambda track_uri: json.dumps(playback_client.play_track(track_uri), indent=2)
        ),
        Tool(
            name="play_multiple_tracks",
            description="Play multiple tracks by Spotify URIs",
            parameters={
                "type": "object",
                "properties": {
                    "track_uris": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of Spotify track URIs to play"
                    }
                },
                "required": ["track_uris"]
            },
            function=lambda track_uris: json.dumps(playback_client.play_tracks(track_uris), indent=2)
        ),
        Tool(
            name="pause_playback",
            description="Pause the current playback",
            parameters={
                "type": "object",
                "properties": {}
            },
            function=lambda: json.dumps(playback_client.pause_playback(), indent=2)
        ),
        Tool(
            name="resume_playback",
            description="Resume the current playback",
            parameters={
                "type": "object",
                "properties": {}
            },
            function=lambda: json.dumps(playback_client.resume_playback(), indent=2)
        ),
        Tool(
            name="skip_to_next",
            description="Skip to the next track",
            parameters={
                "type": "object",
                "properties": {}
            },
            function=lambda: json.dumps(playback_client.skip_to_next(), indent=2)
        ),
        Tool(
            name="skip_to_previous",
            description="Skip to the previous track",
            parameters={
                "type": "object",
                "properties": {}
            },
            function=lambda: json.dumps(playback_client.skip_to_previous(), indent=2)
        ),
        Tool(
            name="set_volume",
            description="Set the playback volume (0-100)",
            parameters={
                "type": "object",
                "properties": {
                    "volume_percent": {
                        "type": "integer",
                        "description": "Volume level from 0 to 100",
                        "minimum": 0,
                        "maximum": 100
                    }
                },
                "required": ["volume_percent"]
            },
            function=lambda volume_percent: json.dumps(playback_client.set_volume(volume_percent), indent=2)
        ),
        Tool(
            name="get_current_playback",
            description="Get information about what's currently playing",
            parameters={
                "type": "object",
                "properties": {}
            },
            function=lambda: json.dumps(playback_client.get_current_playback(), indent=2)
        ),
        Tool(
            name="get_available_devices",
            description="Get list of available Spotify devices for playback",
            parameters={
                "type": "object",
                "properties": {}
            },
            function=lambda: json.dumps(playback_client.get_available_devices(), indent=2)
        )
    ]
    
    return tools


# ==================== Setup Validation ====================

def check_ollama_connection(model: str = "llama3.2") -> bool:
    """Check if Ollama is running and model is available."""
    try:
        print("   (This may take 10-30 seconds on first run while model loads...)")
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "test"}],
                "stream": False
            },
            timeout=60  # Increased timeout for initial model load
        )
        return response.status_code == 200
    except Exception as e:
        print(f"\n❌ Cannot connect to Ollama: {str(e)}")
        print("\n📋 Setup Instructions:")
        print("1. Install Ollama from https://ollama.ai")
        print(f"2. Run: ollama pull {model}")
        print("3. Ensure Ollama is running (it should start automatically)")
        return False


# ==================== Main Orchestrator ====================

def main():
    """Main orchestrator with specialized agents."""
    print("=" * 60)
    print("🎵 Spotify Agent Orchestrator")
    print("=" * 60)
    
    # Check Ollama connection
    print("\n🔍 Checking Ollama connection...")
    if not check_ollama_connection():
        return
    print("✅ Ollama is running!")
    
    # Initialize Spotify client
    print("\n🔍 Initializing Spotify client...")
    try:
        spotify_client = SpotifyClient()
        print("✅ Spotify client initialized!")
    except Exception as e:
        print(f"❌ Failed to initialize Spotify: {str(e)}")
        print("\n📋 Setup Instructions:")
        print("1. Copy .env.example to .env")
        print("2. Add your SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET")
        print("3. Get credentials from https://developer.spotify.com/dashboard")
        return
    
    # Create Spotify tools
    spotify_tools = create_spotify_tools(spotify_client)
    
    # Create specialized agents
    search_agent = Agent(
        name="Spotify Search Agent",
        system_prompt="""You are a Spotify search specialist. Help users find tracks, artists, and get recommendations.
        
IMPORTANT: After using tools to search, you MUST provide a natural language response summarizing the results. Never output JSON or tool syntax as your final response."""
    )
    
    for tool in spotify_tools:
        search_agent.add_tool(tool)
    
    # Search Agent will get access to Playback Agent after it's created
    
    playlist_agent = Agent(
        name="Playlist Agent",
        system_prompt="""You are a Spotify playlist specialist. Help users explore playlists and discover music collections.
        
IMPORTANT: After getting playlist information, you MUST provide a natural language response summarizing the playlist. Never output JSON or tool syntax as your final response."""
    )
    
    # Add playlist-specific tool
    playlist_agent.add_tool(spotify_tools[4])  # get_playlist tool
    
    # Initialize playback client and create playback agent
    playback_agent = None
    try:
        print("\n🔍 Initializing Spotify playback (requires authorization)...")
        playback_client = SpotifyPlaybackClient()
        playback_tools = create_playback_tools(playback_client)
        
        playback_agent = Agent(
            name="Playback Agent",
            system_prompt="""You are a Spotify playback control specialist. Help users play songs, control playback (pause, resume, skip), adjust volume, and check what's currently playing.
            
IMPORTANT:
1. When asked 'what' is playing, use get_current_playback and respond with the artist and track name in natural language.
2. If asked to play a specific song/artist but you don't have a track URI, call the Search Agent first to find it, then use the URI to play it.
3. After performing actions or getting playback info, you MUST respond in natural language.
4. Never output JSON or tool syntax as your final response.
5. If an error occurs, explain it simply to the user.

You have access to the Search Agent to find tracks when needed."""
        )
        
        for tool in playback_tools:
            playback_agent.add_tool(tool)
        
        # Give Playback Agent access to Search Agent
        playback_agent.add_tool(Tool.from_agent(search_agent))
        
        # Enable agent collaboration: Search Agent can call Playback Agent if needed
        search_agent.add_tool(Tool.from_agent(playback_agent))
        
        print("✅ Playback client initialized!")
    except Exception as e:
        print(f"⚠️  Playback features disabled: {str(e)}")
        print("   (Playback requires user authorization. Search features still work!)")
    
    # Create coordinator agent that can delegate to specialized agents
    coordinator = Agent(
        name="Coordinator Agent",
        system_prompt="""You are a coordinator that helps users with Spotify-related tasks in Swedish or English.
        
IMPORTANT RULES:
1. You CAN perform multiple actions in sequence. Break down complex requests into steps.
2. When you receive tool results, you MUST respond to the user in natural language.
3. NEVER output JSON or tool call syntax as your response. Tool calls are internal only.
4. After calling all needed tools and getting results, provide a clear final answer based on those results.
5. If the user asks "Vem är det jag lyssnar på nu?" (Who am I listening to now?) or similar, call Playback Agent with task='what'.
6. If user asks to play a song ("spela", "play"), delegate to Playback Agent with task='play <song/artist name>'.
7. The Playback Agent can search for tracks itself - just pass it the task.

MULTI-STEP EXAMPLES:
- "Play Bohemian Rhapsody and turn volume to 50" → Call Playback Agent to play, then call again for volume
- "What's playing and skip to next" → Call Playback Agent for current track, then call again to skip
- "Find Queen songs and play the most popular one" → Call Search Agent, then Playback Agent with the URI

Available agents:
- Playback Agent: Play songs, control playback (pause, resume, skip, volume), check what's playing. Can search for tracks.
- Search Agent: Find tracks, artists, get recommendations
- Playlist Agent: Get playlist information

Respond naturally and conversationally. Extract information from tool results and present it clearly to the user."""
    )
    
    # Register specialized agents as tools
    coordinator.add_tool(Tool.from_agent(search_agent))
    coordinator.add_tool(Tool.from_agent(playlist_agent))
    if playback_agent:
        coordinator.add_tool(Tool.from_agent(playback_agent))
    
    print("\n✅ Agents initialized!")
    print("\n💡 Available commands:")
    print("  - Ask about Spotify tracks, artists, or playlists")
    if playback_agent:
        print("  - Play songs, pause, skip, control volume")
        print("  - Check what's currently playing")
    print("  - Type 'quit' or 'exit' to stop")
    print("=" * 60)
    
    # Interactive loop
    while True:
        try:
            user_input = input("\n🎤 You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye!")
                break
            
            print(f"\n🤖 {coordinator.name} is thinking...")
            response = coordinator.execute(user_input)
            print(f"\n🤖 {coordinator.name}: {response}")
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Fatal Error: {str(e)}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")  # Keep terminal open to see error

