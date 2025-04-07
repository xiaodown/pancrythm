


def load_discord_api_key():
    with open('discordapikey.txt', 'r') as file:
        api_key = file.read().strip()
    return api_key

def load_yt_api_key():
    with open('ytapikey.txt', 'r') as file:
        api_key = file.read().strip()
    return api_key

bot_name = "Pancrythm"
wake_phrase = "cake"
idle_timeout = 600  # in seconds, default is 10 minutes (600 seconds)