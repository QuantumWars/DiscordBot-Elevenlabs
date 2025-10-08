# Discord Audio Generation Bot

Automated text-to-speech Discord bot that extracts scripts from Google Docs and generates audio using ElevenLabs API.

## Features

- 📄 Extract scripts from Google Docs URLs
- 🎤 Multiple voice options (James, Melissa, Default, or custom)
- 🎵 Parallel audio generation with async processing
- ⏭️ Skip current script or stop all generation
- 🧹 Automatic cleanup of temporary files
- 👥 Multi-user session support

## Prerequisites

- Python 3.8+
- FFmpeg (required by pydub for audio processing)
- ElevenLabs API key
- Discord Bot Token

## Installation

### 1. Clone or download the repository

```bash
cd discord-automation
```

### 2. Install FFmpeg

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
Download from [ffmpeg.org](https://ffmpeg.org/download.html)

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` and add your credentials:
```env
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
DISCORD_BOT_TOKEN=your_discord_bot_token_here
```

#### Getting API Keys:

**ElevenLabs API Key:**
1. Sign up at [elevenlabs.io](https://elevenlabs.io)
2. Go to Profile → API Keys
3. Copy your API key

**Discord Bot Token:**
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a New Application
3. Go to Bot → Add Bot
4. Enable "Message Content Intent" under Privileged Gateway Intents
5. Copy the Bot Token

**Invite Bot to Server:**
1. Go to OAuth2 → URL Generator
2. Select scopes: `bot`
3. Select permissions: `Send Messages`, `Attach Files`, `Read Message History`
4. Copy the generated URL and open in browser

## Usage

### Start the bot

```bash
python step4_modify.py
```

### Commands

#### `!extract <google_docs_url>`
Extract and generate audio from Google Docs scripts.

**Workflow:**
1. Bot extracts all scripts from the document
2. User selects which scripts to generate (e.g., `1,3,5` or `all`)
3. Bot asks for voice selection for each script (single or multiple)
4. Bot generates audio and sends MP3 files

**Single Voice per Script:**
```
!extract https://docs.google.com/document/d/YOUR_DOC_ID/edit
> Select scripts: 1,2
> Script #1 voice: 1         (James voice)
> Script #2 voice: 2         (Melissa voice)
```

**Multiple Voices per Script:**
Generate the same script with different voices:
```
!extract https://docs.google.com/document/d/YOUR_DOC_ID/edit
> Select scripts: 1
> Script #1 voice: 1,2,3     (Generate with James, Melissa, AND Default)
```
This will create 3 audio files:
- `script_1_James.mp3`
- `script_1_Melissa.mp3`
- `script_1_Default.mp3`

#### `!skip`
Skip the currently generating script and move to the next one.

```
!skip
```

#### `!stop`
Stop all audio generation and cleanup temp files.

```
!stop
```

### Voice Management Commands

#### `!voices`
List all available voices (default + custom).

```
!voices
```

#### `!addvoice <name> <voice_id>`
Add a custom voice to your library.

```
!addvoice Morgan ztnpYzQJyWffPj1VC5Uw
```

#### `!searchvoice [limit]`
Search recent Discord messages for voice IDs. Useful for extracting voice IDs from old chat messages.

```
!searchvoice 100
```

**Example workflow:**
1. Someone shared a voice ID in chat earlier
2. Run `!searchvoice 100` to search last 100 messages
3. Bot shows found voice IDs with context
4. Copy the voice ID and add it: `!addvoice CustomName voice_id_here`

#### `!removevoice <number>`
Remove a custom voice from your library (cannot remove default voices).

```
!removevoice 4
```

### Voice Options

**Default Voices:**

| Number | Voice Name | Voice ID |
|--------|-----------|----------|
| 1 | James | ztnpYzQJyWffPj1VC5Uw |
| 2 | Melissa | 27ximz35zKCDKjbjZGNt |
| 3 | Default | hWUa9vMm0D2rSFio6QYm |

**Custom Voices:**
- Add custom voices using `!addvoice` command
- Stored persistently in `voices.json`
- Automatically loaded on bot restart
- Use `!voices` to see all available voices

## Google Docs Format

Scripts should be formatted in your Google Doc as:

```
Script #1
This is the content of script 1...

Script #2
This is the content of script 2...

Script #3 INSPO
This is script 3 with inspiration tag...
```

- Scripts are identified by `Script #<number>` pattern
- Content continues until the next script marker
- Optional `INSPO` tag is supported

## Configuration

### Custom Voice IDs

Edit `VOICE_IDS` dictionary in `step4_modify.py`:

```python
VOICE_IDS = {
    '1': {'name': 'YourVoice', 'id': 'your_voice_id'},
    '2': {'name': 'AnotherVoice', 'id': 'another_voice_id'},
}
```

### Thread Pool Workers

Adjust concurrent audio generation:

```python
executor = ThreadPoolExecutor(max_workers=3)  # Change to desired number
```

## Troubleshooting

### Bot doesn't respond
- Check that Message Content Intent is enabled in Discord Developer Portal
- Verify bot has proper permissions in the server

### Audio generation fails
- Verify ElevenLabs API key is valid
- Check API quota/rate limits
- Ensure FFmpeg is installed correctly

### Google Docs extraction fails
- Document must be publicly accessible or shared with link
- Check URL format is correct
- Verify document contains properly formatted scripts

## File Cleanup

Temporary files are automatically cleaned up:
- After successful audio generation
- When using `!stop` or `!skip` commands
- On errors or timeouts

## Security

⚠️ **Never commit `.env` file to version control**

The `.env` file contains sensitive credentials. It's already in `.gitignore`.

## Dependencies

- `discord.py` - Discord bot framework
- `requests` - HTTP requests
- `beautifulsoup4` - HTML parsing
- `python-dotenv` - Environment variable management
- `elevenlabs` - Text-to-speech API
- `pydub` - Audio processing

## License

MIT License
