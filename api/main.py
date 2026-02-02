"""
FastAPI Backend for Spotify Agent Chatbot
Provides REST and WebSocket endpoints for agent communication with Redis session storage
"""

import os
import json
import uuid
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis.asyncio as redis

# Import agent components from parent directory
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent import (
    Agent, Tool, SpotifyClient, SpotifyPlaybackClient,
    create_spotify_tools, create_playback_tools
)

# Initialize FastAPI app
app = FastAPI(title="Spotify Agent API", version="1.0.0")

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis connection
redis_client: Optional[redis.Redis] = None

# Session storage (in-memory backup if Redis fails)
sessions: Dict[str, Dict] = {}

# Agent cache
coordinator_agent: Optional[Agent] = None


# ==================== Pydantic Models ====================

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str


class HealthResponse(BaseModel):
    status: str
    redis_connected: bool
    agent_initialized: bool


# ==================== Redis Session Management ====================

async def get_redis():
    """Get Redis connection."""
    global redis_client
    if redis_client is None:
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_client = await redis.from_url(
            f"redis://{redis_host}:{redis_port}",
            encoding="utf-8",
            decode_responses=True
        )
    return redis_client


async def save_session(session_id: str, messages: List[Dict], ttl: int = 3600):
    """Save session messages to Redis with TTL."""
    try:
        r = await get_redis()
        await r.setex(
            f"session:{session_id}",
            ttl,
            json.dumps(messages)
        )
    except Exception as e:
        print(f"Redis save error: {e}")
        # Fallback to in-memory
        sessions[session_id] = {"messages": messages}


async def load_session(session_id: str) -> List[Dict]:
    """Load session messages from Redis."""
    try:
        r = await get_redis()
        data = await r.get(f"session:{session_id}")
        if data:
            return json.loads(data)
    except Exception as e:
        print(f"Redis load error: {e}")
        # Fallback to in-memory
        if session_id in sessions:
            return sessions[session_id].get("messages", [])
    return []


# ==================== Agent Initialization ====================

def initialize_coordinator_agent() -> Agent:
    """Initialize the coordinator agent with all specialized agents."""
    print("🔧 Initializing Spotify Agent...")
    
    # Initialize Spotify client
    spotify_client = SpotifyClient()
    spotify_tools = create_spotify_tools(spotify_client)
    
    # Create Search Agent
    search_agent = Agent(
        name="Spotify Search Agent",
        system_prompt="""You are a Spotify search specialist. Help users find tracks, artists, and get recommendations.
        
IMPORTANT: After using tools to search, you MUST provide a natural language response summarizing the results. Never output JSON or tool syntax as your final response."""
    )
    
    for tool in spotify_tools:
        search_agent.add_tool(tool)
    
    # Create Playlist Agent
    playlist_agent = Agent(
        name="Playlist Agent",
        system_prompt="""You are a Spotify playlist specialist. Help users explore playlists and discover music collections.
        
IMPORTANT: After getting playlist information, you MUST provide a natural language response summarizing the playlist. Never output JSON or tool syntax as your final response."""
    )
    playlist_agent.add_tool(spotify_tools[4])  # get_playlist tool
    
    # Initialize Playback Agent (may fail if no OAuth)
    playback_agent = None
    try:
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
        
        # Enable agent collaboration
        playback_agent.add_tool(Tool.from_agent(search_agent))
        search_agent.add_tool(Tool.from_agent(playback_agent))
        
        print("✅ Playback Agent initialized (single-user mode)")
    except Exception as e:
        print(f"⚠️  Playback features disabled: {str(e)}")
    
    # Create Coordinator Agent
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
    
    print("✅ Coordinator Agent initialized!")
    return coordinator


def get_coordinator() -> Agent:
    """Get or create coordinator agent."""
    global coordinator_agent
    if coordinator_agent is None:
        coordinator_agent = initialize_coordinator_agent()
    return coordinator_agent


# ==================== API Endpoints ====================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    print("🚀 Starting Spotify Agent API...")
    try:
        await get_redis()
        print("✅ Redis connected")
    except Exception as e:
        print(f"⚠️  Redis connection failed: {e}")
        print("   Using in-memory session storage")
    
    # Initialize agent
    try:
        get_coordinator()
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global redis_client
    if redis_client:
        await redis_client.close()


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    redis_ok = False
    try:
        r = await get_redis()
        await r.ping()
        redis_ok = True
    except:
        pass
    
    return HealthResponse(
        status="healthy",
        redis_connected=redis_ok,
        agent_initialized=coordinator_agent is not None
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Synchronous chat endpoint (for simple requests).
    For real-time streaming, use WebSocket endpoint instead.
    """
    # Generate or use existing session ID
    session_id = request.session_id or str(uuid.uuid4())
    
    # Load session history
    messages = await load_session(session_id)
    
    # Get coordinator agent
    coordinator = get_coordinator()
    
    # Restore agent memory from session
    coordinator.memory = messages.copy()
    
    # Execute agent
    try:
        response = coordinator.execute(request.message)
    except Exception as e:
        print(f"Agent execution error: {e}")
        response = f"Sorry, I encountered an error: {str(e)}"
    
    # Save updated memory to session
    await save_session(session_id, coordinator.memory)
    
    return ChatResponse(response=response, session_id=session_id)


@app.get("/messages/{session_id}")
async def get_messages(session_id: str):
    """
    Get all messages for a session.
    """
    messages = await load_session(session_id)
    return {"messages": messages, "session_id": session_id}


@app.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time streaming chat.
    Sends incremental updates as the agent processes the request.
    """
    await websocket.accept()
    print(f"🔌 WebSocket connected: {session_id}")
    
    try:
        # Load session history
        messages = await load_session(session_id)
        
        # Get coordinator agent
        coordinator = get_coordinator()
        
        # Restore agent memory from session
        coordinator.memory = messages.copy()
        
        # Store event loop reference
        loop = asyncio.get_event_loop()
        
        # Define event callback for streaming updates
        async def event_callback(event_type: str, data: Dict):
            """Send agent events to client in real-time."""
            try:
                await websocket.send_json({
                    "type": event_type,
                    **data
                })
            except Exception as e:
                print(f"Error sending event: {e}")
        
        # Create a sync wrapper for the async callback
        def sync_event_callback(event_type: str, data: Dict):
            """Synchronous wrapper for event callback."""
            try:
                # Schedule the coroutine in the event loop
                asyncio.run_coroutine_threadsafe(event_callback(event_type, data), loop)
            except Exception as e:
                print(f"Error in sync callback: {e}")
        
        # Set the event callback on coordinator
        coordinator.set_event_callback(sync_event_callback)
        
        # Listen for messages from client
        while True:
            # Receive message
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_message = message_data.get("message", "")
            
            if not user_message:
                continue
            
            # Send thinking indicator
            await websocket.send_json({
                "type": "thinking",
                "content": "Processing your request..."
            })
            
            # Execute agent in background and stream response
            try:
                # Run agent execution (blocking, but in async context)
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None, 
                    coordinator.execute, 
                    user_message
                )
                
                # Send final response
                await websocket.send_json({
                    "type": "message",
                    "content": response,
                    "role": "assistant"
                })
                
                # Save updated memory to session
                await save_session(session_id, coordinator.memory)
                
            except Exception as e:
                print(f"Agent execution error: {e}")
                await websocket.send_json({
                    "type": "error",
                    "content": f"Sorry, I encountered an error: {str(e)}"
                })
    
    except WebSocketDisconnect:
        print(f"🔌 WebSocket disconnected: {session_id}")
    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "content": f"Connection error: {str(e)}"
            })
        except:
            pass


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Spotify Agent API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "chat": "/chat (POST)",
            "websocket": "/ws/chat/{session_id}"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
