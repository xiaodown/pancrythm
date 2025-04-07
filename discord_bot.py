import asyncio
import discord
import settings
import yt_dlp
import json

api_key = settings.load_discord_api_key()
intents = discord.Intents.default()
intents.messages = True  # Enable message intents
intents.message_content = True  # Enable message content intents
intents.guilds = True  # Enable guild-related intents
intents.voice_states = True  # Enable voice state intents
bot = discord.Client(intents=intents)

# Dictionary to track idle timers for each voice connection
idle_timers = {}
idle_timer_remaining = {}  # Tracks remaining time for each guild


async def on_ready():
    guild_count = 0
    for guild in bot.guilds:
        print(f"- {guild.id} (name: {guild.name})")
        guild_count = guild_count + 1

    print(f"{settings.bot_name} is on " + str(guild_count) + " servers.")


async def start_idle_timer(voice_client, timeout=None):
    """
    Starts an idle timer for the bot to leave the voice channel after `timeout` seconds.
    """
    guild_id = voice_client.guild.id
    if timeout is None:
        timeout = settings.idle_timeout  # Use the configurable timeout from settings

    # Cancel any existing timer for this guild
    if guild_id in idle_timers:
        idle_timers[guild_id].cancel()

    # Set the remaining time
    idle_timer_remaining[guild_id] = timeout

    async def leave_after_timeout():
        while idle_timer_remaining[guild_id] > 0:
            await asyncio.sleep(1)
            idle_timer_remaining[guild_id] -= 1

        if voice_client.is_connected():
            await voice_client.disconnect()
            print(f"Disconnected from voice channel in guild {guild_id} due to inactivity.")
            del idle_timers[guild_id]
            del idle_timer_remaining[guild_id]

    # Start a new timer
    idle_timers[guild_id] = asyncio.create_task(leave_after_timeout())


def add_idle_time(guild_id, additional_time):
    """
    Adds additional time to the idle timer for the specified guild.
    """
    if guild_id in idle_timer_remaining:
        idle_timer_remaining[guild_id] += additional_time
        print(f"Added {additional_time} seconds to the idle timer for guild {guild_id}.")
    else:
        print(f"No active idle timer for guild {guild_id} to add time to.")

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

def play_command(voice_client, query):
    """
    Plays the audio from the given query in the voice channel.
    """
    info = search_youtube(query)
    if info is None:
        print("No information returned from YouTube search.")
        return

    # Save the entire info dictionary to a file and pretty-print it
    with open("tempfile.json", "w") as f:
        json.dump(info, f, indent=4)
    print("YouTube info saved to tempfile.json")

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

    if not url:
        print("Error: No format with format_id == 234 found.")
        return

    # Extract the duration
    duration = info['entries'][0].get('duration', None)
    if duration is None:
        print("Warning: 'duration' key not found in the first entry. Defaulting to 0 seconds.")
        duration = 0

    # Add the song's duration to the idle timer
    add_idle_time(voice_client.guild.id, duration)
    print(f"Added {duration} seconds to the idle timer for guild {voice_client.guild.id}.")

    # Play the audio
    voice_client.play(discord.FFmpegPCMAudio(url), after=lambda e: print(f"Finished playing: {e}"))

    # Start the idle timer
    asyncio.create_task(start_idle_timer(voice_client))

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
    verb = parts[1]  # The verb (e.g., "play")
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

    # Check if the command matches the wake phrase
    if command == settings.wake_phrase:
        if verb == "play" and args:
            voice_channel = message.author.voice.channel if message.author.voice else None
            if voice_channel is None:
                await message.channel.send("You need to be in a voice channel to use this command.")
                return

            # Check if the bot is already connected to a voice channel in the same guild
            existing_voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
            if existing_voice_client and existing_voice_client.is_connected():
                # Bot is already connected to a voice channel in this guild
                print(f"Bot is already connected to a voice channel in guild {message.guild.id}.")
            else:
                # Connect to the voice channel
                voice_client = await voice_channel.connect()
            await message.channel.send(f"Playing: {args}")
            play_command(voice_client, args)
        else:
            await message.channel.send(f"Unknown verb or missing arguments for command: {verb}")

bot.run(api_key)