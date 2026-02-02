# Spotify Agent Orchestrator

A Python-based agent orchestration system where agents have individual memory, can use tools, and can call each other as tools. Agents are specialized for interacting with the Spotify API.

## Features

- 🤖 **Agent Orchestration**: Multiple specialized agents that can delegate tasks to each other
- 🧠 **Memory**: Each agent maintains conversation history
- 🔧 **Tools**: Extensible tool system with OpenAI function calling format
- 🎵 **Spotify Integration**: Search tracks, get artist info, playlists, and recommendations
- ☁️ **AWS Bedrock**: Uses Amazon Bedrock with Claude for powerful LLM inference

## Architecture

- **Coordinator Agent**: Routes tasks to specialized agents
- **Search Agent**: Handles track/artist search and recommendations
- **Playlist Agent**: Manages playlist queries
- **Agent-as-Tool**: Agents can call other agents as tools

## Prerequisites

### 1. AWS Account & Bedrock Access

**Setup AWS Credentials:**

1. **Create an AWS Account** (if you don't have one):
   - Go to [AWS Console](https://aws.amazon.com/console/)
   - Sign up for an AWS account

2. **Enable Amazon Bedrock Access**:
   - Navigate to Amazon Bedrock in AWS Console
   - Request model access for Claude models (if not already enabled)
   - Go to "Model access" and enable "Claude 3 Sonnet"

3. **Configure AWS Credentials**:

   **Option A: AWS CLI (Recommended)**
   ```bash
   # Install AWS CLI
   # Windows: Download from https://aws.amazon.com/cli/
   # macOS: brew install awscli
   # Linux: pip install awscli
   
   # Configure credentials
   aws configure
   ```
   Enter your:
   - AWS Access Key ID
   - AWS Secret Access Key
   - Default region (e.g., `us-east-1`)
   - Output format (e.g., `json`)

   **Option B: Environment Variables**
   Add to your `.env` file:
   ```
   AWS_ACCESS_KEY_ID=your_access_key
   AWS_SECRET_ACCESS_KEY=your_secret_key
   AWS_REGION=us-east-1
   ```

   **Option C: IAM Role** (for EC2/ECS)
   - Attach IAM role with Bedrock permissions to your instance

4. **Required IAM Permissions**:
   Your AWS user/role needs:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "bedrock:InvokeModel",
           "bedrock:InvokeModelWithResponseStream"
         ],
         "Resource": "arn:aws:bedrock:*::foundation-model/anthropic.claude-*"
       }
     ]
   }
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
pip install -r requirements.txt
```

Or install individually:
```bash
pip install requests python-dotenv spotipy boto3
```

## Setup

1. **Clone or download this project**

2. **Create `.env` file from template:**
   ```bash
   copy .env.example .env
   ```

3. **Add your credentials to `.env`:**
   ```
   # Spotify Credentials
   SPOTIFY_CLIENT_ID=your_actual_client_id
   SPOTIFY_CLIENT_SECRET=your_actual_client_secret
   SPOTIFY_REDIRECT_URI=https://127.0.0.1:8888/callback
   
   # AWS Configuration (optional if using AWS CLI)
   AWS_ACCESS_KEY_ID=your_aws_access_key
   AWS_SECRET_ACCESS_KEY=your_aws_secret_key
   AWS_REGION=us-east-1
   ```
   
   **Note**: For playback features, the first run will open a browser for authorization. After authorizing, you'll be redirected to a 127.0.0.1 URL - just copy that full URL and paste it back in the terminal.

4. **Verify AWS Bedrock access:**
   - Test with: `aws bedrock list-foundation-models --region us-east-1`
   - Or just run the agent - it will check connectivity on startup

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
4. **LLM Processing**: AWS Bedrock (Claude) processes the query and decides which tools to call
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
agent = Agent(
    name="Agent",
    system_prompt="...",
    model="anthropic.claude-3-sonnet-20240229-v1:0"  # Default
    # or "anthropic.claude-3-haiku-20240307-v1:0"  # Faster, cheaper
    # or "anthropic.claude-3-opus-20240229-v1:0"   # Most capable
)
```

## Troubleshooting

### "Cannot connect to AWS Bedrock"
- Verify AWS credentials are configured: `aws sts get-caller-identity`
- Check you have Bedrock access in your AWS region
- Ensure model access is enabled in AWS Bedrock console
- Verify IAM permissions include `bedrock:InvokeModel`
- Try setting AWS_REGION in .env file explicitly

### "Failed to initialize Spotify"
- Verify `.env` file exists and has correct credentials
- Check credentials are valid at [Spotify Dashboard](https://developer.spotify.com/dashboard)
- Ensure no extra spaces in `.env` file

### Tool calls not working
- Claude models have excellent function calling support
- Check AWS Bedrock console for any service issues
- Verify you're using a supported Claude model version

### AWS Cost Concerns
- Claude 3 Haiku is the most cost-effective option (~$0.25 per million input tokens)
- Claude 3 Sonnet offers good balance (~$3 per million input tokens)
- Monitor usage in AWS Cost Explorer
- Set up billing alerts in AWS Console

## Limitations

- **Spotify Playback**: Client credentials flow doesn't support playback control (requires user OAuth)
- **Rate Limits**: Spotify API has rate limits (typically sufficient for personal use)
- **AWS Costs**: AWS Bedrock is a paid service (but very affordable for personal use)
- **AWS Regions**: Claude models may not be available in all AWS regions

## License

This project is provided as-is for educational and personal use.

## Resources

- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Anthropic Claude Documentation](https://docs.anthropic.com/)
- [Boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [Spotify Web API Documentation](https://developer.spotify.com/documentation/web-api)
- [Spotipy Documentation](https://spotipy.readthedocs.io/)
