


def load_discord_api_key():
    with open('discordapikey.txt', 'r') as file:
        api_key = file.read().strip()
    return api_key


########################################
# Change your settings here as desired #
########################################

bot_name = "Pancrythm" # flavor text, used in bot responses
wake_phrase = "cake" # i.e. !cake <command> to interact with the bot
idle_timeout = 300  # in seconds, default is 5 minutes (300 seconds)
volume = 0.5  # Set the volume (1.0 is 100%, 0.5 is 50%, etc.)
cache_dir = "cache"  # Directory to store cached files 
queue_limit = 100 # limit the number of songs in the queue