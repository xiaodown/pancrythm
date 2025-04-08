# pancrythm

Pancrythm (a portmanteau of pancake + rhythm) is a simple, small, badly coded discord bot for playing music with your friends.

This came about because my group of friends used both of the above-named bots in the past to listen to music - usually sea shanties
while playing Sea of Thieves - but these bots stopped working.  Flew too close to the sun, I suppose.

Anyway, my instance of this bot is private, and is not intended to join more than 1 or 2 servers that I hang out with my friends in.
In this way, I view it much like it would be if I were hanging out with friends, listening to music on the couch or in the car.

If you would like to also have a small music bot for your small discord server with your friends, you can run this one.

## Installation and Setup

Works in linux.  To set it up:
 * Clone the git repo: `git clone git@github.com:xiaodown/pancrythm.git`
 * Create a python virtual environment.
   * I use uv for this now: `cd pancrythm; uv venv`
   * You can do this with poetry or raw-dog with pip if you're a neanderthal, details left as an exercise for the reader.
 * Install the required libraries: `source .venv/bin/activate; uv pip install -r requirements.txt`
 * Create a discord bot:
   * This is covered elsewhere on the internet, but basically:
     * Go to the [Discord Developer Portal](https://discord.com/developers/applications) and register a new application
     * Save your API key somewhere safe!
     * App settings -> Installation -> set Install Link to None
     * App settings -> Bot -> Set "Public Bot" OFF
     * App settings -> Bot -> Set all three intents ON
     * App settings -> OAuth2 -> Generate a url -> Select "bot" and:
       * Voice Permissions: Connect, Speak
       * Text Permissions: Send Messages, Embed Links, Read Message History
       * Integration Type: Guild Install
       * Copy the generated URL
 * Have an admin (ideally you) invite the bot to your discord server
   * if necessary add it to a `#music` or whatever channel
 * Edit settings:
   * in `settings.py` there are several things that you may wish to change.  
     * Note that the bot's name is set via your discord developer app; the `bot_name` is just flavor text.
 * Add your api key:
   * Create a text file called `discordapikey.txt` in the root of the checkout.  It will be loaded from there.
     * Note: if you fork this repo, this file is in the .gitignore.  Do be careful about not checking in your API key.

## Running
 * Run the bot:
   * `source .venv/bin/activate; python ./discord_bot.py`
 * It is also trivial to set up a systemd service to run the bot if you would prefer - something like:
   * create a linux user for the bot (for safety) and check out everything in their homedir
   * create /etc/systemd/system/discordbot.service with contents similar to below
   * run with `systemctl enable discordbot; systemctl start discordbot`
```
[Unit]
Description=discord music bot for friends
After=network.target

[Service]
Type=simple
Restart=always
RestartSec=1
User=pancrythm
WorkingDirectory=/home/pancrythm/pancrythm/
ExecStart=/home/pancrythm/pancrythm/.venv/bin/python /home/pancrythm/discord_bot.py >/dev/null 2>&1

[Install]
WantedBy=multi-user.target
```

## Use

You can set the wake word in `settings.py` but by default it is `cake`.  So:

 * !cake play `<search term>`
   * searches for `<search term>` and plays the first result
   * also accepts a YT url as the search term, which skips searching and plays directly
 * !cake stop
   * immediately stops playback and disconnects the bot from the voice channel
 * !cake pause
   * pauses audio (note the bot will still idle timeout)
 * !cake resume
   * resume playback
 * !cake help
   * displays currently supported commands and help text

## TODO:

 * Queueing system needs to be implemented
   * Skipping / manipulating items in the queueing system
 * ~~Create help text (!cake help or something)~~ Done
 * ~~support URLs as a search term~~ Done
 * Clean up code / make more object oriented (unlikely)
   * This is really ugly; it started as a simple script and kept growing.  Oh well.  Refactoring is for chumps.

## Risks:

If youtube changes the way their API works, we're at the mercy of yt_dlp.  It may be possible to implement this without using yt_dlp, 
and I briefly looked into creating a google API key and using the Youtube Info V3 API, so there's a fallback plan, but...

Also if someone takes this and turns it into a huge commercial thing on hundreds of servers, rights-holders are going to be mad.
That's not what this bot is for; it's for small use among groups of close friends. Don't be a jerk.