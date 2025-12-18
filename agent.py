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
from spotipy.oauth2 import SpotifyClientCredentials


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
            
            # Prepare messages for LLM
            messages = [{"role": "system", "content": self.system_prompt}] + self.memory
            
            # Prepare tools schema
            tools_schema = [tool.to_schema() for tool in self.tools.values()] if self.tools else None
            
            # Call Ollama
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
                    continue
                else:
                    # No tool calls, we have final response
                    assistant_message = response["message"]["content"]
                    self.memory.append({"role": "assistant", "content": assistant_message})
                    return assistant_message
                    
            except Exception as e:
                error_msg = f"Error calling LLM: {str(e)}"
                print(f"[{self.name}] {error_msg}")
                return error_msg
        
        return "Max iterations reached without final answer."
    
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


# ==================== Setup Validation ====================

def check_ollama_connection(model: str = "llama3.2") -> bool:
    """Check if Ollama is running and model is available."""
    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "test"}],
                "stream": False
            },
            timeout=5
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
        system_prompt="You are a Spotify search specialist. Help users find tracks, artists, and get recommendations. Use the available tools to search Spotify and provide detailed information."
    )
    
    for tool in spotify_tools:
        search_agent.add_tool(tool)
    
    playlist_agent = Agent(
        name="Playlist Agent",
        system_prompt="You are a Spotify playlist specialist. Help users explore playlists and discover music collections. Use the available tools to get playlist information."
    )
    
    # Add playlist-specific tool
    playlist_agent.add_tool(spotify_tools[4])  # get_playlist tool
    
    # Create coordinator agent that can delegate to specialized agents
    coordinator = Agent(
        name="Coordinator Agent",
        system_prompt="You are a coordinator that helps users with Spotify-related tasks. You can delegate tasks to specialized agents: Search Agent (for finding tracks, artists, recommendations) and Playlist Agent (for playlist information). Decide which agent to use based on the user's request, or handle simple queries directly."
    )
    
    # Register specialized agents as tools
    coordinator.add_tool(Tool.from_agent(search_agent))
    coordinator.add_tool(Tool.from_agent(playlist_agent))
    
    print("\n✅ Agents initialized!")
    print("\n💡 Available commands:")
    print("  - Ask about Spotify tracks, artists, or playlists")
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
    main()

