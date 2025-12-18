# Spotify Playback Setup Guide

## Quick Setup for Playback Features

### 1. Configure Redirect URI in Spotify Dashboard

1. Go to https://developer.spotify.com/dashboard
2. Click on your app
3. Click "Edit Settings"
4. Under "Redirect URIs", add: `https://127.0.0.1:8888/callback`
5. Click "Add"
6. Click "Save" at the bottom

### 2. Update Your .env File

Add this line to your `.env` file:
```
SPOTIFY_REDIRECT_URI=https://127.0.0.1:8888/callback
```

### 3. First-Time Authorization

When you run the agent for the first time with playback features:

1. The agent will open a browser window automatically
2. Log in to Spotify if needed
3. Click "Agree" to authorize the app
4. You'll be redirected to `https://127.0.0.1:8888/callback?code=...`
5. **Copy the entire URL from your browser's address bar**
6. **Paste it back into the terminal where the agent is waiting**
7. Press Enter

The authorization is cached in `.spotify_cache` file, so you only need to do this once.

## Required Spotify Scopes

The playback features require these permissions:
- `user-modify-playback-state` - Play, pause, skip tracks
- `user-read-playback-state` - Get current playback info
- `user-read-currently-playing` - See what's playing

## Playback Features

### Available Commands

- **Play a song**: "Play [song name] by [artist]"
- **Pause**: "Pause the music"
- **Resume**: "Resume playback"
- **Skip forward**: "Skip to the next track"
- **Skip backward**: "Go to the previous track"
- **Volume control**: "Set volume to 75" or "Turn volume down to 20"
- **Current track**: "What's playing?" or "What song is this?"
- **List devices**: "Show my Spotify devices"

### How It Works

1. **Coordinator Agent** receives your request
2. Determines it's a playback request
3. Delegates to **Playback Agent**
4. Playback Agent may first use **Search Agent** to find the track
5. Uses playback tools to control Spotify
6. Returns confirmation or current status

### Example Flow

```
You: Play Stairway to Heaven by Led Zeppelin

Coordinator → Search Agent → Finds track URI
Coordinator → Playback Agent → Plays the track

Response: "Playing Stairway to Heaven by Led Zeppelin"
```

## Troubleshooting

### "No active device found"
- Open Spotify on any device (phone, desktop, web player)
- Start playing any song (or just open the app)
- Try the command again

### "Invalid redirect URI"
- Verify `https://127.0.0.1:8888/callback` is added in Spotify Dashboard
- Make sure there are no typos or extra spaces
- The URI is case-sensitive and must match exactly

### "Unauthorized" error
- Delete `.spotify_cache` file
- Run the agent again to re-authorize
- Make sure you're using the same Spotify account

### Browser doesn't open automatically
- Manually copy the URL from terminal output
- Paste it in your browser
- Complete the authorization
- Copy the redirect URL and paste it back in terminal

## Agent Architecture

```
Coordinator Agent
├── Search Agent (find tracks, artists, recommendations)
├── Playlist Agent (explore playlists)
└── Playback Agent (control playback)
    ├── play_track
    ├── pause_playback
    ├── resume_playback
    ├── skip_to_next
    ├── skip_to_previous
    ├── set_volume
    ├── get_current_playback
    └── get_available_devices
```

## Notes

- **Playback requires an active Spotify Premium account** (Free accounts can't use the playback API)
- The agent can control any device where you're logged into Spotify
- If no device is specified, Spotify will use your most recently active device
- Volume control works per-device (doesn't affect system volume)
