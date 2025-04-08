import asyncio
import discord
import settings
import yt_dlp
import json
import os
from datetime import datetime, timedelta

api_key = settings.load_discord_api_key()
intents = discord.Intents.default()
intents.messages = True  # Enable message intents
intents.message_content = True  # Enable message content intents
intents.guilds = True  # Enable guild-related intents
intents.voice_states = True  # Enable voice state intents
bot = discord.Client(intents=intents)
bot_name = settings.bot_name

# Dictionary to track idle timers for each voice connection
_idle_timers = {}
_idle_timer_remaining = {}  # Tracks remaining time for each guild

cache_dir = settings.cache_dir


def ensure_cache_dir_exists():
    """
    Ensure that the cache directory exists.
    """
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

async def on_ready():
    guild_count = 0
    for guild in bot.guilds:
        print(f"- {guild.id} (name: {guild.name})")
        guild_count = guild_count + 1

    print(f"{bot_name} is on " + str(guild_count) + " servers.")


async def start_idle_timer(voice_client, timeout=None):
    """
    Starts an idle timer for the bot to leave the voice channel after `timeout` seconds.
    Also checks periodically if the bot is alone in the voice channel and disconnects if true.
    """
    guild_id = voice_client.guild.id
    guild_name = voice_client.guild.name
    if timeout is None:
        timeout = settings.idle_timeout

    # Cancel any existing timer for this guild
    if guild_id in _idle_timers:
        _idle_timers[guild_id].cancel()

    # Set the remaining time
    _idle_timer_remaining[guild_id] = timeout
    print(f"Initialized idle timer for guild {guild_name} with timeout {timeout} seconds.")

    async def leave_after_timeout():
        while _idle_timer_remaining[guild_id] > 0:
            await asyncio.sleep(1)
            _idle_timer_remaining[guild_id] -= 1

            # Check every 60 seconds if the bot is alone in the voice channel
            if _idle_timer_remaining[guild_id] % 60 == 0:
                channel_members = voice_client.channel.members
                non_bot_members = [member for member in channel_members if not member.bot]
                if not non_bot_members:  # If no non-bot members are in the channel
                    print(f"No users left in the voice channel {voice_client.channel.name}. Disconnecting.")
                    await voice_client.disconnect()
                    del _idle_timers[guild_id]
                    del _idle_timer_remaining[guild_id]
                    return

        # Disconnect after the idle timer expires
        if voice_client.is_connected():
            await voice_client.disconnect()
            print(f"Disconnected from voice channel in guild {guild_name} due to inactivity.")
            del _idle_timers[guild_id]
            del _idle_timer_remaining[guild_id]

    # Start a new timer
    _idle_timers[guild_id] = asyncio.create_task(leave_after_timeout())


def add_idle_time(guild, additional_time):
    """
    Adds additional time to the idle timer for the specified guild.
    """
    if guild.id in _idle_timer_remaining:
        _idle_timer_remaining[guild.id] += additional_time
        print(f"Added {additional_time} seconds to the idle timer for guild {guild.name}. New remaining time: {_idle_timer_remaining[guild.id]} seconds.")
    else:
        print(f"No active idle timer for guild {guild.name} to add time to.")

def search_youtube(query):
    """
    Searches YouTube for the given query and returns the first result.
    """
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'noplaylist': True,
        'default_search': 'auto',
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
            return info
        except Exception as e:
            print(f"Error searching YouTube: {e}")
            return None 

async def clean_cache():
    """
    Cleans the cache directory by removing files older than 7 days.
    """
    now = datetime.now()
    seven_days_ago = now - timedelta(days=7)

    for filename in os.listdir(cache_dir):
        file_path = os.path.join(cache_dir, filename)
        if os.path.isfile(file_path):
            file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            if file_mod_time < seven_days_ago:  # Correct condition
                try:
                    os.remove(file_path)
                    print(f"Removed old cache file: {file_path}")
                except Exception as e:
                    print(f"Error removing file {file_path}: {e}")

async def download_audio(url, cache_dir, title):
    """
    Downloads the audio file using yt-dlp and saves it in the cache directory.
    Updates the file's modification time to the current time after downloading.
    """
    filename = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).rstrip() + ".mp3"
    filepath = os.path.join(cache_dir, filename)

    # Clean the cache directory before downloading (probably aggressive but w/e)
    await clean_cache()

    # Check if the file already exists in the cache
    if os.path.exists(filepath):
        print(f"File already exists in cache: {filepath}")
        return filepath

    # Use yt-dlp to download the file
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': filepath,
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([url])
            print(f"Audio downloaded and saved to: {filepath}")

            # Update the file's modification time to "now"
            now = datetime.now().timestamp()
            os.utime(filepath, (now, now))  # Set both access and modification times to "now"
            print(f"Updated modification time for {filepath} to {datetime.fromtimestamp(now)}")

            return filepath
        except Exception as e:
            print(f"Failed to download audio with yt-dlp: {e}")
            return None

def stop_playback(voice_client):
    """
    Stops the audio playback in the voice client.
    """
    if voice_client.is_playing():
        voice_client.stop()
        print("Stopped audio playback.")
    else:
        print("No audio is currently playing.")

async def handle_stop_command(voice_client, channel):
    """
    Stops the audio playback and disconnects from the voice channel.
    """
    stop_playback(voice_client)
    await voice_client.disconnect()
    await channel.send("Stopped audio playback and disconnected from the voice channel.")
    print("Disconnected from voice channel.")

async def handle_pause_command(voice_client, channel):
    """
    Pauses the audio playback in the voice client.
    """
    if voice_client.is_playing():
        voice_client.pause()
        print("Paused audio playback.")
    else:
        await channel.send("Audio is not currently playing.")
        print("No audio is currently playing.")

async def handle_resume_command(voice_client, channel):
    """
    Resumes the audio playback in the voice client.
    """
    if voice_client.is_paused():
        voice_client.resume()
        print("Resumed audio playback.")
    else:
        await channel.send("Audio is not paused.")
        print("Audio is not paused.")

async def handle_play_command(voice_client, query, message_channel):
    """
    Plays the audio from the given query in the voice channel.
    """
    info = search_youtube(query)
    if info is None:
        print("No information returned from YouTube search.")
        return

    # Navigate to the correct entry and formats
    if 'entries' not in info or not info['entries']:
        print("Error: 'entries' key not found or empty in the info dictionary.")
        return

    formats = info['entries'][0].get('formats', [])
    if not formats:
        print("Error: 'formats' key not found or empty in the first entry.")
        return

    # Find the format with format_id == 234
    url = None
    for fmt in formats:
        if fmt.get('format_id') == '234':  # Match format_id as a string
            url = fmt.get('url')
            break
    title = info['entries'][0].get('title', "Unknown Title")
    print(f"Title: {title}")

    if not url:
        print("Error: No format with format_id == 234 found.")
        return

    # Extract the duration
    duration = info['entries'][0].get('duration', 0)
    if duration == 0:
        print("Warning: 'duration' key not found or is 0 in the first entry.")

    # Download the audio file to the cache directory
    filepath = await download_audio(url, cache_dir, title)
    if not filepath:
        await message_channel.send("Failed to download audio. Please try again.")
        return

    # Check if the bot is already playing audio
    if voice_client.is_playing():
        print("Bot is already playing audio.")
        await message_channel.send(f"Currently playing audio. Queuing your request: {title}")
        # Optionally, you can implement a queue system here to handle multiple requests
        return

    # Start the idle timer
    await start_idle_timer(voice_client)  # Ensure the timer is initialized first

    # Add the song's duration to the idle timer
    add_idle_time(voice_client.guild, duration)

    # Send a message to the text channel before playing
    await message_channel.send(f"Now playing: {title}")

    # Play the audio with volume control from the cached file
    volume = settings.volume
    ffmpeg_options = {
        'options': f'-filter:a "volume={volume}"'
    }
    voice_client.play(discord.FFmpegPCMAudio(filepath, **ffmpeg_options), after=lambda e: print(f"Finished playing: {e}"))


def parse_message(message):
    """
    Parses the message to extract the command, verb, and arguments.
    Example: "!cake play <string>" -> command="cake", verb="play", args="<string>"
    """
    if not message.content.startswith("!"):
        return None, None, None  # Not a command

    parts = message.content[1:].split(" ", 2)  # Split into at most 3 parts: command, verb, and args
    if len(parts) < 2:
        return None, None, None  # Not enough parts to extract command and verb

    command = parts[0]  # The command (e.g., "cake")
    verb = parts[1].lower()  # Convert the verb to lowercase
    args = parts[2] if len(parts) > 2 else None  # The remaining string (e.g., "<string>")

    return command, verb, args


@bot.event
async def on_message(message):
    print(f"Received message: {message.content}")
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Parse the message
    command, verb, args = parse_message(message)

    channel = message.channel
    # Check if the command matches the wake phrase
    if command == settings.wake_phrase:
        # PLAY
        if verb == "play" and args:
            voice_channel = message.author.voice.channel if message.author.voice else None
            if voice_channel is None:
                await channel.send("You need to be in a voice channel to use this command.")
                return

            # Check if the bot is already connected to a voice channel in the same guild
            existing_voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
            if existing_voice_client and existing_voice_client.is_connected():
                print(f"Bot is already connected to a voice channel in guild {message.guild.id}.")
                await channel.send(f"Already connected to a voice channel. Processing your command: {args}")
                await handle_play_command(existing_voice_client, args, message.channel)
            else:
                # Connect to the voice channel
                voice_client = await voice_channel.connect()
                await handle_play_command(voice_client, args, message.channel)

        # STOP
        elif verb == "stop":
            voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
            if voice_client:
                await handle_stop_command(voice_client, channel)
            else:
                await channel.send(f"{bot_name} is not connected to a voice channel.")

        # PAUSE
        elif verb == "pause":
            voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
            if voice_client:
                await handle_pause_command(voice_client, channel)
            else:
                await channel.send(f"{bot_name} is not connected to a voice channel.")

        # RESUME
        elif verb == "resume":
            voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
            if voice_client:
                await handle_resume_command(voice_client, channel)
            else:
                await channel.send(f"{bot_name} is not connected to a voice channel.")

        else:
            await channel.send(f"Unknown command {verb}")

ensure_cache_dir_exists()
bot.run(api_key)