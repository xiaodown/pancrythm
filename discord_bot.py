import asyncio
import discord
import logging
import settings

api_key = settings.load_discord_api_key()
intents = discord.Intents.default()
intents.messages = True  # Enable message intents
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


@bot.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Check if the message starts with "!" followed by the wake phrase
    if message.content.startswith(f"!{settings.wake_phrase}"):
        # Get the user who sent the message
        user = message.author

        # Check if the user is in a voice channel
        if user.voice and user.voice.channel:
            voice_channel = user.voice.channel

            # Join the voice channel
            try:
                voice_client = await voice_channel.connect()
                await message.channel.send(
                    f"{user.name}, I have joined the voice channel: {voice_channel.name}"
                )

                # Start the idle timer with the configurable timeout
                await start_idle_timer(voice_client)

            except discord.ClientException:
                await message.channel.send(
                    f"I'm already connected to a voice channel!"
                )
            except Exception as e:
                await message.channel.send(
                    f"Failed to join the voice channel: {e}"
                )
        else:
            await message.channel.send(f"{user.name} is not in a voice channel.")


bot.run(api_key)