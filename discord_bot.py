import asyncio
import discord
import settings
import yt_dlp
import os
from datetime import datetime, timedelta
from mutagen import File as MutagenFile
import re


class IdleTimerManager:
    """
    Manages idle timers for each guild.
    """
    def __init__(self):
        self._timers = {}
        self._remaining = {}
        self._locks = {}

    async def start_timer(self, voice_client, timeout):
        guild_id = voice_client.guild.id
        guild_name = voice_client.guild.name

        if guild_id not in self._locks:
            self._locks[guild_id] = asyncio.Lock()

        # Cancel any existing timer
        if guild_id in self._timers:
            self._timers[guild_id].cancel()

        async with self._locks[guild_id]:
            self._remaining[guild_id] = timeout
            print(f"Initialized idle timer for guild {guild_name} with timeout {timeout} seconds.")

        async def leave_after_timeout():
            while self._remaining[guild_id] > 0:
                await asyncio.sleep(1)
                self._remaining[guild_id] -= 1

                # Check every 60 seconds if the bot is alone
                if self._remaining[guild_id] % 60 == 0:
                    channel_members = voice_client.channel.members
                    non_bot_members = [member for member in channel_members if not member.bot]
                    if not non_bot_members:
                        print(f"No users left in the voice channel {voice_client.channel.name}. Disconnecting.")
                        await voice_client.disconnect()
                        del self._timers[guild_id]
                        del self._remaining[guild_id]
                        return

            # Disconnect after the timer expires
            if voice_client.is_connected():
                await voice_client.disconnect()
                print(f"Disconnected from voice channel in guild {guild_name} due to inactivity.")
                del self._timers[guild_id]
                del self._remaining[guild_id]

        async with self._locks[guild_id]:
            self._timers[guild_id] = asyncio.create_task(leave_after_timeout())

    async def add_time(self, guild, additional_time):
        guild_id = guild.id
        if guild_id in self._remaining:
            async with self._locks[guild_id]:
                self._remaining[guild_id] += additional_time
                print(f"Added {additional_time} seconds to the idle timer for guild {guild.name}. New remaining time: {self._remaining[guild_id]} seconds.")
        else:
            print(f"No active idle timer for guild {guild.name} to add time to.")


class QueueManager:
    """
    Manages song queues for each guild.
    """
    def __init__(self):
        self._queues = {}
        self._locks = {}

    def get_queue(self, guild_id):
        if guild_id not in self._queues:
            self._queues[guild_id] = []
        return self._queues[guild_id]

    async def add_to_queue(self, guild_id, song):
        if guild_id not in self._locks:
            self._locks[guild_id] = asyncio.Lock()

        async with self._locks[guild_id]:
            queue = self.get_queue(guild_id)
            queue.append(song)
            print(f"Added to queue: {song['title']}")

    async def pop_from_queue(self, guild_id):
        if guild_id not in self._locks:
            self._locks[guild_id] = asyncio.Lock()

        async with self._locks[guild_id]:
            queue = self.get_queue(guild_id)
            if queue:
                return queue.pop(0)
            return None

    def clear_queue(self, guild_id):
        if guild_id in self._queues:
            self._queues[guild_id].clear()


class MusicBot(discord.Client):
    """
    A Discord bot for playing music.
    """
    def __init__(self, intents, settings):
        super().__init__(intents=intents)
        self.settings = settings
        self.idle_timer_manager = IdleTimerManager()
        self.queue_manager = QueueManager()
        self.cache_dir = settings.cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    async def on_ready(self):
        custom_status = f"!{self.settings.wake_phrase} {self.settings.status}"
        await self.set_custom_status(custom_status)
        guild_count = len(self.guilds)
        print(f"{self.settings.bot_name} is on {guild_count} servers.")
        for guild in self.guilds:
            print(f"- {guild.id} (name: {guild.name})")

    async def on_message(self, message):
        print(f"Received message: {message.content}")
        if message.author == self.user:
            return

        command, verb, args = self.parse_message(message)
        if command == self.settings.wake_phrase:
            await self.handle_command(message, verb, args)

    async def handle_command(self, message, verb, args):
        channel = message.channel
        guild = message.guild
        voice_client = discord.utils.get(self.voice_clients, guild=guild)

        if verb == "play" and args:
            await self.handle_play_command(voice_client, args, channel, message.author)
        elif verb == "stop":
            await self.handle_stop_command(voice_client, channel)
        elif verb == "queue":
            await self.handle_queue_command(voice_client, channel)
        elif verb == "skip":
            await self.handle_skip_command(voice_client, channel)
        else:
            await channel.send(f"Unknown command: {verb}")

    async def handle_play_command(self, voice_client, query, channel, author):
        voice_channel = author.voice.channel if author.voice else None
        if not voice_channel:
            await channel.send("You need to be in a voice channel to use this command.")
            return

        if not voice_client or not voice_client.is_connected():
            voice_client = await voice_channel.connect()

        # Search and download the song
        song = await self.search_and_download(query)
        if not song:
            await channel.send("Failed to find or download the song.")
            return

        await self.queue_manager.add_to_queue(voice_client.guild.id, song)
        await self.idle_timer_manager.start_timer(voice_client, self.settings.idle_timeout)
        await channel.send(f"Now playing: {song['title']}")

    async def search_and_download(self, query):
        """
        Searches for a song on YouTube and downloads it.
        """
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(self.cache_dir, '%(title)s.%(ext)s'),
            'quiet': True,
            'noplaylist': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(f"ytsearch:{query}", download=True)['entries'][0]
                filepath = ydl.prepare_filename(info)
                return {
                    "title": info.get('title', 'Unknown Title'),
                    "filepath": filepath,
                    "duration": info.get('duration', 0)
                }
            except Exception as e:
                print(f"Error downloading song: {e}")
                return None

    async def set_custom_status(self, status_message):
        activity = discord.Activity(type=discord.ActivityType.custom, name=status_message)
        await self.change_presence(activity=activity)
        print(f"Custom status set to: {status_message}")

    def parse_message(self, message):
        if not message.content.startswith("!"):
            return None, None, None

        parts = message.content[1:].split(" ", 2)
        command = parts[0]
        verb = parts[1].lower() if len(parts) > 1 else None
        args = parts[2] if len(parts) > 2 else None
        return command, verb, args


# Bot setup
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.voice_states = True

bot = MusicBot(intents=intents, settings=settings)
bot.run(settings.load_discord_api_key())