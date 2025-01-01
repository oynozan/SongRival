# Song Rival
Song Rival is a music Telegram bot where users can bet cryptocurrencies and compete to guess a song faster.

# How to play?
Start a conversation with `@SongRivalBot` on Telegram, deposit some BNB to your wallet (optional), and start competing with others.

## How it works?
The application consists 2 parts:

1) Telegram Bot
2) Downloader

### Telegram Bot
The Telegram bot is made with `python-telegram-bot` library to serve users a fun gameplay in Telegram. Users can deposit & withdraw to their arbitrary wallet addresses, bet BNB while competing with others.

### Downloader
Since users are supposed to guess songs and win the matches by guessing it first, there must be some songs stored somehow. Song Rival uses DigitalOcean buckets to store the songs. The `downloader.py` script uses [Spotify Downloader](https://rapidapi.com/amiteshgupta/api/spotify-downloader9) API to download songs and store them in the bucket. Without at least 5 songs, there is no purpose of running the Telegram bot.

## Test Instructions
There are several steps you should follow to test the application yourself.

1) Create a Telegram bot using BotFather bot. Then copy the bot token.
2) Rename `.env.template` file to `.env` and fill corresponding values such as bot token, your DigitalOcean bucket details, RapidAPI key, etc.
3) Install necessary Python packages using the command `pip install -r requirements.txt`.
4) Rename `artists.template.py` to `artists.py` and fill the array with your favorite artists. This list will be used to download songs from the artists you provide. You can provide anything, Spotify Downloader API will run a search query on Spotify and use the matched artist. Even if you do a typo, you will more likely to download a correct song.
4) Run `py main.py`. This script runs `downloader.py` and `bot.py` in different processes.

And that's it. Now you can test the bot by yourself.