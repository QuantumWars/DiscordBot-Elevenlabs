import discord
from discord.ext import commands
import requests
from bs4 import BeautifulSoup
import os
import re
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs import save
from pydub import AudioSegment

load_dotenv()

# Load environment variables
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Validate required environment variables
if not ELEVENLABS_API_KEY:
    raise ValueError("ELEVENLABS_API_KEY not found in environment variables")
if not DISCORD_BOT_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN not found in environment variables")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

elevenlabs = ElevenLabs(api_key=ELEVENLABS_API_KEY)
executor = ThreadPoolExecutor(max_workers=3)

# Global state for tracking active generation sessions
active_sessions = {}

# Voice storage file
VOICES_FILE = 'voices.json'

# Default voices
DEFAULT_VOICE_IDS = {
    '1': {'name': 'James', 'id': 'ztnpYzQJyWffPj1VC5Uw'},
    '2': {'name': 'Melissa', 'id': '27ximz35zKCDKjbjZGNt'},
    '3': {'name': 'Default', 'id': 'hWUa9vMm0D2rSFio6QYm'},
}

def load_voices():
    """Load voices from JSON file"""
    if os.path.exists(VOICES_FILE):
        try:
            with open(VOICES_FILE, 'r') as f:
                saved_voices = json.load(f)
                # Merge with default voices
                voices = DEFAULT_VOICE_IDS.copy()
                voices.update(saved_voices)
                return voices
        except Exception as e:
            print(f"Error loading voices: {e}")
            return DEFAULT_VOICE_IDS.copy()
    return DEFAULT_VOICE_IDS.copy()

def save_voices(voices):
    """Save custom voices to JSON file"""
    try:
        # Only save non-default voices
        custom_voices = {k: v for k, v in voices.items() if k not in DEFAULT_VOICE_IDS}
        with open(VOICES_FILE, 'w') as f:
            json.dump(custom_voices, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving voices: {e}")
        return False

# Load voices at startup
VOICE_IDS = load_voices()

def extract_text(url):
    """Extract text from URL"""
    try:
        doc_id = url.split("/d/")[1].split("/")[0]
        export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"

        response = requests.get(export_url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove scripts and styles
        for script in soup(['script', 'style']):
            script.decompose()
        
        # Extract and clean text
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text
    except Exception as e:
        return f"Error extracting text: {str(e)}"

def parse_scripts(text):
    """Extract individual scripts from text"""
    scripts = {}
    pattern = r'Script #(\d+)\s*(?:INSPO)?\s*(.*?)(?=Script #|\Z)'
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
    
    for script_num, content in matches:
        clean_content = content.strip()
        if clean_content:
            scripts[script_num] = clean_content
    
    return scripts

def split_text_into_paragraphs(text, target_words=55):
    sentences = re.split(r'[.!?]+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    
    paragraphs = []
    current_paragraph = ""
    current_word_count = 0
    
    for sentence in sentences:
        sentence_words = len(sentence.split())
        if current_word_count > 0 and current_word_count + sentence_words > 60:
            if current_paragraph:
                paragraphs.append(current_paragraph.strip())
            current_paragraph = sentence
            current_word_count = sentence_words
        else:
            if current_paragraph:
                current_paragraph += ". " + sentence
            else:
                current_paragraph = sentence
            current_word_count += sentence_words
    
    if current_paragraph.strip():
        paragraphs.append(current_paragraph.strip())
    
    return paragraphs

def generate_audio_for_paragraph(text, paragraph_index, voice_id):
    """Synchronous function to generate audio"""
    audio = elevenlabs.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )
    temp_file = f"paragraph_{paragraph_index + 1}.mp3"
    save(audio, temp_file)
    return temp_file

async def generate_audio_async(text, paragraph_index, voice_id):
    """Async wrapper for audio generation"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        executor, 
        generate_audio_for_paragraph, 
        text, 
        paragraph_index, 
        voice_id
    )

def stitch_audio_files(audio_files, output_filename):
    combined_audio = AudioSegment.from_mp3(audio_files[0])
    for audio_file in audio_files[1:]:
        audio_segment = AudioSegment.from_mp3(audio_file)
        combined_audio += AudioSegment.silent(duration=0)
        combined_audio += audio_segment
    combined_audio.export(output_filename, format="mp3")
    return output_filename

def cleanup_temp_files(files):
    for file in files:
        try:
            os.remove(file)
        except OSError:
            pass

@bot.command(name='addvoice')
async def add_voice(ctx, name: str, voice_id: str):
    """Add a custom voice to the library
    Usage: !addvoice VoiceName voice_id_here"""
    global VOICE_IDS

    # Find next available number
    next_num = str(max([int(k) for k in VOICE_IDS.keys() if k.isdigit()], default=0) + 1)

    VOICE_IDS[next_num] = {'name': name, 'id': voice_id}

    if save_voices(VOICE_IDS):
        await ctx.send(f"✅ Added voice **{name}** (#{next_num}) with ID: `{voice_id}`")
    else:
        await ctx.send(f"❌ Failed to save voice.")

@bot.command(name='searchvoice')
async def search_voice(ctx, limit: int = 50):
    """Search recent messages for voice IDs
    Usage: !searchvoice [limit]"""
    await ctx.send(f"🔍 Searching last {limit} messages for voice IDs...")

    voice_pattern = re.compile(r'\b([a-zA-Z0-9]{20,})\b')
    found_voices = []

    try:
        async for message in ctx.channel.history(limit=limit):
            # Look for patterns that might be voice IDs
            matches = voice_pattern.findall(message.content)
            for match in matches:
                if len(match) >= 20 and match not in [v['id'] for v in VOICE_IDS.values()]:
                    found_voices.append({
                        'id': match,
                        'context': message.content[:100],
                        'author': message.author.name,
                        'timestamp': message.created_at
                    })

        if found_voices:
            result = "🎤 **Found potential voice IDs:**\n"
            for i, voice in enumerate(found_voices[:10], 1):  # Limit to 10
                result += f"\n{i}. `{voice['id']}`\n   Context: {voice['context']}\n   By: {voice['author']}\n"
            result += f"\n💡 Use `!addvoice YourName voice_id` to add a voice"
            await ctx.send(result)
        else:
            await ctx.send("❌ No potential voice IDs found in recent messages.")

    except Exception as e:
        await ctx.send(f"❌ Error searching messages: {str(e)}")

@bot.command(name='voices')
async def list_voices(ctx):
    """List all available voices"""
    voice_list = "🎤 **Available Voices:**\n```\n"
    for key, voice in sorted(VOICE_IDS.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
        voice_list += f"{key}. {voice['name']}\n"
    voice_list += "```\n💡 Use `!addvoice Name voice_id` to add more voices"
    await ctx.send(voice_list)

@bot.command(name='removevoice')
async def remove_voice(ctx, number: str):
    """Remove a custom voice
    Usage: !removevoice 4"""
    global VOICE_IDS

    if number in DEFAULT_VOICE_IDS:
        await ctx.send(f"❌ Cannot remove default voice #{number}")
        return

    if number in VOICE_IDS:
        voice_name = VOICE_IDS[number]['name']
        del VOICE_IDS[number]
        if save_voices(VOICE_IDS):
            await ctx.send(f"✅ Removed voice **{voice_name}** (#{number})")
        else:
            await ctx.send(f"❌ Failed to save changes.")
    else:
        await ctx.send(f"❌ Voice #{number} not found.")

@bot.command(name='stop')
async def stop_generation(ctx):
    """Stop all audio generation for this user"""
    user_id = ctx.author.id
    if user_id in active_sessions:
        active_sessions[user_id]['stop_all'] = True
        await ctx.send("🛑 **Stopping all generation...** Current tasks will finish, then stop.")
    else:
        await ctx.send("❌ No active generation session found.")

@bot.command(name='skip')
async def skip_current(ctx):
    """Skip current script being generated"""
    user_id = ctx.author.id
    if user_id in active_sessions:
        active_sessions[user_id]['skip_current'] = True
        current = active_sessions[user_id].get('current_script', 'Unknown')
        await ctx.send(f"⏭️ **Skipping Script #{current}...** Moving to next script.")
    else:
        await ctx.send("❌ No active generation session found.")

@bot.command(name='extract')
async def extract_url(ctx, url: str):
    """Usage: !extract <url>"""
    user_id = ctx.author.id

    # Initialize session state
    active_sessions[user_id] = {
        'stop_all': False,
        'skip_current': False,
        'current_script': None,
        'temp_files': []
    }

    await ctx.send("🔍 Extracting text...")
    text = extract_text(url)
    
    if not text:
        await ctx.send("❌ Failed to extract text. Check URL accessibility.")
        return
    
    # Parse scripts
    scripts = parse_scripts(text)
    
    if not scripts:
        await ctx.send("❌ No scripts found in the document.")
        return
    
    # Show available scripts
    script_list = "\n".join([f"Script #{num}" for num in sorted(scripts.keys())])
    await ctx.send(f"📄 **Available Scripts:**\n```\n{script_list}\n```\nEnter script numbers (e.g., `1,3` or `all`):")
    
    def check_msg(m):
        return m.author == ctx.author and m.channel == ctx.channel
    
    try:
        # Get script selection
        msg = await bot.wait_for('message', check=check_msg, timeout=60.0)
        
        if msg.content.lower() == 'all':
            selected_scripts = list(scripts.keys())
        else:
            selected_scripts = [s.strip() for s in msg.content.split(',') if s.strip() in scripts]
        
        if not selected_scripts:
            await ctx.send("❌ Invalid script selection.")
            return
        
        await ctx.send(f"✅ Selected: {', '.join([f'Script #{s}' for s in selected_scripts])}")

        # Collect all voice IDs upfront
        script_voices = {}
        voice_list = "\n".join([f"{k}. {v['name']}" for k, v in VOICE_IDS.items()])

        for script_num in selected_scripts:
            await ctx.send(f"🎤 **Script #{script_num}** - Select voice(s):\n```\n{voice_list}\n```\nEnter single voice (e.g., `1`) or multiple voices (e.g., `1,2,3`):")

            voice_msg = await bot.wait_for('message', check=check_msg, timeout=60.0)

            # Parse voice selection - can be single or multiple
            voice_selections = [v.strip() for v in voice_msg.content.split(',')]
            voices_for_script = []

            for voice_selection in voice_selections:
                # Determine voice ID
                if voice_selection in VOICE_IDS:
                    voice = VOICE_IDS[voice_selection]
                    voice_id = voice['id']
                    voice_name = voice['name']
                else:
                    voice_id = voice_selection.strip()
                    voice_name = 'Custom'

                voices_for_script.append({'id': voice_id, 'name': voice_name})

            script_voices[script_num] = voices_for_script

            if len(voices_for_script) == 1:
                await ctx.send(f"✅ Script #{script_num} → **{voices_for_script[0]['name']}** voice")
            else:
                voice_names = ", ".join([v['name'] for v in voices_for_script])
                await ctx.send(f"✅ Script #{script_num} → **{len(voices_for_script)} voices**: {voice_names}")

        # Now generate audio for all scripts
        await ctx.send(f"\n🎵 Starting audio generation for {len(selected_scripts)} script(s)...")
        await ctx.send("💡 Use `!stop` to stop all, or `!skip` to skip current script.")

        for script_num in selected_scripts:
            # Check if user requested stop all
            if active_sessions[user_id]['stop_all']:
                await ctx.send("🛑 **Generation stopped by user.**")
                break

            # Reset skip flag for new script
            active_sessions[user_id]['skip_current'] = False
            active_sessions[user_id]['current_script'] = script_num

            script_text = scripts[script_num]
            voices_list = script_voices[script_num]

            # Generate audio for each voice selected for this script
            for voice_info in voices_list:
                # Check for stop/skip before each voice generation
                if active_sessions[user_id]['stop_all']:
                    await ctx.send("🛑 **Generation stopped by user.**")
                    break

                if active_sessions[user_id]['skip_current']:
                    await ctx.send(f"⏭️ **Skipped remaining voices for Script #{script_num}**")
                    break

                voice_id = voice_info['id']
                voice_name = voice_info['name']

                await ctx.send(f"🎵 Generating Script #{script_num} with **{voice_name}** voice...")

                # Generate audio
                paragraphs = split_text_into_paragraphs(script_text)
                audio_files = []

                try:
                    for i, paragraph in enumerate(paragraphs):
                        # Check for stop/skip during paragraph generation
                        if active_sessions[user_id]['stop_all']:
                            await ctx.send("🛑 **Stopping...** Cleaning up temp files.")
                            cleanup_temp_files(audio_files)
                            active_sessions[user_id]['temp_files'].extend(audio_files)
                            break

                        if active_sessions[user_id]['skip_current']:
                            await ctx.send(f"⏭️ **Skipped Script #{script_num} - {voice_name}**")
                            cleanup_temp_files(audio_files)
                            active_sessions[user_id]['temp_files'].extend(audio_files)
                            break

                        audio_file = await generate_audio_async(paragraph, i, voice_id)
                        audio_files.append(audio_file)
                        active_sessions[user_id]['temp_files'].append(audio_file)

                    # Only stitch and send if not stopped/skipped
                    if not active_sessions[user_id]['stop_all'] and not active_sessions[user_id]['skip_current']:
                        final_audio = stitch_audio_files(audio_files, f"script_{script_num}_{voice_name}.mp3")
                        active_sessions[user_id]['temp_files'].append(final_audio)

                        # Send to Discord
                        with open(final_audio, 'rb') as f:
                            discord_file = discord.File(f, filename=f"script_{script_num}_{voice_name}.mp3")
                            await ctx.send(f"✅ **Script #{script_num}** - {voice_name} voice:", file=discord_file)

                        cleanup_temp_files(audio_files + [final_audio])

                except Exception as e:
                    await ctx.send(f"❌ Error generating Script #{script_num} with {voice_name}: {str(e)}")
                    cleanup_temp_files(audio_files)
                    if not active_sessions[user_id]['stop_all']:
                        continue  # Try next voice
                    else:
                        break

            # Break outer loop if stopped
            if active_sessions[user_id]['stop_all']:
                break

        # Final cleanup
        if active_sessions[user_id]['stop_all']:
            cleanup_temp_files(active_sessions[user_id]['temp_files'])
            await ctx.send("🧹 Cleaned up all temporary files.")
        else:
            await ctx.send("🎉 All scripts completed!")

        # Remove session
        del active_sessions[user_id]
        
    except TimeoutError:
        await ctx.send("⏱️ Timed out. Please try again.")
        if user_id in active_sessions:
            del active_sessions[user_id]
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")
        if user_id in active_sessions:
            cleanup_temp_files(active_sessions[user_id].get('temp_files', []))
            del active_sessions[user_id]

@bot.event
async def on_ready():
    print(f'✅ Bot logged in as {bot.user}')
    print(f'📝 Prefix: {bot.command_prefix}')
    print(f'🎤 Available voices: {", ".join([v["name"] for v in VOICE_IDS.values()])}')

if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)