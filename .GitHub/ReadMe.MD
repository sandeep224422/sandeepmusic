<h1 align="center">zefmusic</h1>

<p align="center">
  <strong>Music for Telegram voice chats.</strong><br>
  Audio and video playback with rich controls, queue management and assistant accounts.
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/zefronxd/zefmusic/main/zefmusic/assets/zefmusic.png" alt="zefmusic" width="220">
</p>

<p align="center">
  <a href="https://heroku.com/deploy?template=https://github.com/zefronxd/zefmusic">
    <img src="https://www.herokucdn.com/deploy/button.svg" alt="Deploy to Heroku">
  </a>
</p>

<p align="center">
  <a href="https://render.com/deploy?repo=https://github.com/zefronxd/zefmusic">
    <img src="https://render.com/images/deploy-to-render-button.svg" alt="Deploy to Render">
  </a>
</p>

<p align="center">
  <a href="https://t.me/destiny_bots">
    <img src="https://img.shields.io/badge/Channel-zefBots-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" alt="zefBots channel">
  </a>
  <a href="https://t.me/yaaro_ka_kafla">
    <img src="https://img.shields.io/badge/Support-Join%20Chat-5865F2?style=for-the-badge&logo=telegram&logoColor=white" alt="Support chat">
  </a>
  <a href="https://t.me/Cryptex_here">
     <img src="https://img.shields.io/badge/Contact-Zefron%20xd-20232A?style=for-the-badge&logo=telegram&logoColor=white" alt="Contact cryptex">
  </a>
</p>

<p align="center">
  <sub>Open any section below to explore the documentation.</sub>
</p>

---

<details>
<summary><b>Overview</b></summary>

<br>

- The bot client (Kurigram) receives commands and renders the player interface.
- One to five assistant accounts (string sessions) join voice chats through PyTgCalls and stream audio or video, processed by FFmpeg.
- Track metadata comes from YouTube search and the Spotify, Apple Music, Resso and SoundCloud resolvers. Audio and video files are downloaded through the zefBots API.
- Queue state is kept in memory per chat. Settings, authorized users, bans and statistics are stored in MongoDB.
- The now playing message is a photo card with native inline buttons. Its keyboard, including the live progress bar, is edited in place as playback progresses.

</details>

<details>
<summary><b>Features</b></summary>

<br>

<details>
<summary>Playback</summary>

<br>

Play audio or video in group voice chats, or in a linked channel with the `c` commands. Pause, resume, skip, end, seek forward and back, change speed from 0.5x to 2.0x, loop, shuffle, and replace the current track with force play. Autoplay keeps music going when the queue ends and can be toggled per group.

</details>

<details>
<summary>Player interface</summary>

<br>

The now playing panel uses native inline buttons: a live progress bar, then Replay, Pause or Resume and Skip, then Queue and More (autoplay and suggestions), and End Queue at the bottom. Songs added to a running queue get their own Play Now, Skip and End controls.

</details>

<details>
<summary>Sources</summary>

<br>

YouTube search, links and playlists. Spotify tracks, albums, playlists and artists. Apple Music, Resso and SoundCloud links. Telegram audio and video files. Live streams and index or M3U8 links.

</details>

<details>
<summary>Administration</summary>

<br>

Authorized users per group, sudo users, global bans and chat blacklist. Broadcast, logger, maintenance mode and auto end. Statistics, speedtest, git based update and restart.

</details>

<details>
<summary>Languages</summary>

<br>

English, Hindi, Punjabi and Arabic.

</details>

</details>

<details>
<summary><b>Requirements</b></summary>

<br>

- Python 3.11
- FFmpeg
- MongoDB
- Telegram API credentials and a bot token
- A Pyrogram v2 string session for each assistant account
- A zefBots API key from [@zefAPIBOT](https://t.me/zefAPIBOT)

</details>

<details>
<summary><b>Configuration</b></summary>

<br>

Values are read from the environment or from a `.env` file in the project root.

<details>
<summary>Required variables</summary>

<br>

| Variable | Description |
| --- | --- |
| `API_ID` | Telegram API id |
| `API_HASH` | Telegram API hash |
| `BOT_TOKEN` | Bot token from BotFather |
| `MONGO_DB_URI` | MongoDB connection string |
| `OWNER_ID` | Telegram user id of the owner |
| `LOGGER_ID` | Log group id. The bot must be an admin there |
| `STRING_SESSION` | Session string of the first assistant account |
| `SHRUTI_API_KEY` | Key for the download API |
| `SHRUTI_API_URL` | Download API base URL. Default is `https://api.shrutibots.in` |

</details>

<details>
<summary>Optional variables</summary>

<br>

| Variable | Description |
| --- | --- |
| `STRING_SESSION2` to `STRING_SESSION5` | Additional assistant accounts |
| `DURATION_LIMIT` | Maximum track length in minutes. Default 60 |
| `PLAYLIST_FETCH_LIMIT` | Maximum tracks imported from a playlist. Default 25 |
| `SPOTIFY_CLIENT_ID` | Enables Spotify links |
| `SPOTIFY_CLIENT_SECRET` | Enables Spotify links |
| `SUPPORT_CHANNEL` | Channel link used by bot buttons |
| `SUPPORT_CHAT` | Chat link used by bot buttons |
| `UPSTREAM_REPO` | Repository used by `/update` |
| `UPSTREAM_BRANCH` | Branch used by `/update`. Default `main` |
| `GIT_TOKEN` | Needed if the upstream repository is private |
| `HEROKU_API_KEY` | Allows restart and update on Heroku |
| `HEROKU_APP_NAME` | Allows restart and update on Heroku |

</details>

Assistant accounts must not be banned in the target groups and should be members of the log group.

</details>

<details>
<summary><b>Deployment</b></summary>

<br>

<details>
<summary>Heroku and Render</summary>

<br>

Use the deploy buttons at the top of this page, fill in the variables from the Configuration section, and run a single worker. `app.json`, `heroku.yml`, `Procfile` and `runtime.txt` are included in the repository.

</details>

<details>
<summary>VPS (Ubuntu)</summary>

<br>

Install the system packages.

```bash
sudo apt-get update
```

```bash
sudo apt-get install -y python3 python3-pip python3-venv git ffmpeg screen
```

Start a screen session first, so the virtual environment is created and activated inside it.

```bash
screen -S zef
```

Inside the screen session, clone the repository.

```bash
git clone https://github.com/zefronxd/zefmusic
```

```bash
cd zefmusic
```

Create and activate the virtual environment.

```bash
python3 -m venv venv
```

```bash
source venv/bin/activate
```

Install the dependencies.

```bash
pip install -r requirements.txt
```

Create the configuration file and fill in the variables.

```bash
nano .env
```

Start the bot.

```bash
bash start
```

Detach from the session with `Ctrl+A` then `D`. Reattach later with:

```bash
screen -r zef
```

</details>

<details>
<summary>Docker</summary>

<br>

```bash
docker build -t zefmusic .
```

```bash
docker run -d --name zefmusic --env-file .env zefmusic
```

</details>

<details>
<summary>systemd service</summary>

<br>

Create `/etc/systemd/system/zefmusic.service`:

```ini
[Unit]
Description=zefmusic
After=network.target

[Service]
WorkingDirectory=/home/ubuntu/zefmusic
ExecStart=/home/ubuntu/zefmusic/venv/bin/python -m zefmusic
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Adjust the paths to match your server, then enable the service.

```bash
sudo systemctl daemon-reload
```

```bash
sudo systemctl enable --now zefmusic
```

View the logs.

```bash
journalctl -u zefmusic -f
```

</details>

</details>

<details>
<summary><b>Commands</b></summary>

<br>

Add the bot to a group, start a voice chat, and send `/play <name or link>`. Prefix a playback command with `c` (for example `/cplay` or `/cskip`) to control the linked channel. `/help` in a private chat shows every command with a description.

<details>
<summary>Playback</summary>

<br>

| Command | Description |
| --- | --- |
| `/play` | Play audio |
| `/vplay` | Play video |
| `/playforce` | Replace the current track with audio |
| `/vplayforce` | Replace the current track with video |
| `/pause` | Pause the stream |
| `/resume` | Resume the stream |
| `/skip` | Skip to the next track |
| `/end` | End playback and leave the voice chat |
| `/seek` | Seek forward |
| `/seekback` | Seek backward |
| `/speed` | Change playback speed |
| `/loop` | Set loop mode |
| `/shuffle` | Shuffle the queue |
| `/autoplay` | Toggle autoplay for the group |

</details>

<details>
<summary>Queue and information</summary>

<br>

| Command | Description |
| --- | --- |
| `/queue` | Show the queue |
| `/player` | Show the player |
| `/playing` | Show the current track |
| `/song` | Download a song |
| `/ping` | Bot latency and system status |
| `/stats` | Bot statistics |

</details>

<details>
<summary>Group settings</summary>

<br>

| Command | Description |
| --- | --- |
| `/auth` | Authorize a user |
| `/unauth` | Remove an authorized user |
| `/authlist` | List authorized users |
| `/playmode` | Set the play mode |
| `/channelplay` | Link a channel for channel play |
| `/settings` | Open group settings |
| `/language` | Change the language |

</details>

<details>
<summary>Sudo</summary>

<br>

| Command | Description |
| --- | --- |
| `/broadcast` | Send a message to all served chats |
| `/gban` | Ban a user globally |
| `/block` | Block a user from the bot |
| `/blchat` | Blacklist a chat |
| `/maintenance` | Toggle maintenance mode |
| `/logger` | Toggle logging |
| `/autoend` | Toggle automatic end of empty streams |
| `/addsudo` | Add a sudo user |
| `/delsudo` | Remove a sudo user |
| `/update` | Update from the upstream repository |
| `/restart` | Restart the bot |

</details>

</details>

<details>
<summary><b>Project layout</b></summary>

<br>

```text
zefmusic/
  core/        bot client, assistants, call layer, database, git helpers
  platforms/   YouTube, Spotify, Apple Music, Resso, SoundCloud, Telegram
  plugins/     command handlers: admins, bot, play, sudo, tools, misc
  utils/       stream engine, now playing player, inline keyboards, thumbnails
strings/       help text and language files
config.py      environment loading and defaults
```

</details>

<details>
<summary><b>Development</b></summary>

<br>

<details>
<summary>Add a command</summary>

<br>

Create a module under `zefmusic/plugins/<group>/` and register the handlers on the shared bot client.

</details>

<details>
<summary>Add a language</summary>

<br>

Copy `strings/langs/en.yml` to a new file named after the language code and translate the values. Keys missing from a translation fall back to English.

</details>

<details>
<summary>Add a help topic</summary>

<br>

Add the text as `HELP_<n>` in `strings/helpers.py`, the button label as `H_B_<n>` in the language files, and list the topic in `utils/inline/help.py` and `plugins/bot/help.py`. The help menu shows nine topics per page.

</details>

<details>
<summary>Player controls</summary>

<br>

The now playing player and its inline keyboards are defined in `zefmusic/utils/rich_stream.py`.

</details>

</details>

<details>
<summary><b>Troubleshooting</b></summary>

<br>

<details>
<summary>Assistant does not join the voice chat</summary>

<br>

A voice chat must already be running, and the assistant account must not be banned or restricted in that group.

</details>

<details>
<summary>No sound while playing</summary>

<br>

Run `ffmpeg -version`. If FFmpeg is missing, install it and restart the bot.

</details>

<details>
<summary>Tracks fail to load</summary>

<br>

Verify `SHRUTI_API_KEY` and `SHRUTI_API_URL`, and confirm the key is active in [@zefAPIBOT](https://t.me/zefAPIBOT).

</details>

<details>
<summary>Bot does not respond</summary>

<br>

Verify `MONGO_DB_URI` and, if you use MongoDB Atlas, that the server IP is on the allow list.

</details>

<details>
<summary>Playback stuck after a crash</summary>

<br>

Send `/reboot` in the group and play again.

</details>

</details>

<details>
<summary><b>Contributing</b></summary>

<br>

Open an issue before large changes and keep each pull request focused on one change.

</details>

<details>
<summary><b>License</b></summary>

<br>

See the `LICENSE` file. Personal and educational use is allowed. Credits and the original repository link must be kept in forks. Reselling and rebranding are not allowed.

</details>

## Contact

cryptex: [@Cryptex_here](https://t.me/Cryptex_here) on Telegram. Message directly for support, custom bots and business enquiries.
