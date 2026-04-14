# SnapBot

A Discord-controlled Python bot that uses ADB to automate a few Snapchat actions on a connected Android device.

At a high level, the project lets you:

- send repeated snaps to a target username from Discord
- check whether the bot is currently busy
- read recent bot logs from Discord

The Discord bot is the main entry point (`bot.py`). It collects input from a Discord user, then runs the blocking phone-automation work in background threads via `script.py` and `script_adduser.py`.

## How it works

The bot connects to an Android device through ADB, opens Snapchat, dumps the current Android UI with `uiautomator`, finds UI elements in the XML, and taps randomized coordinates inside each element's bounds. That click flow is implemented in `clicking.py` and the shared ADB helpers in `utils/__init__.py`.

For the main send loop, `script.py` repeatedly:

1. opens the camera capture button
2. goes to the send screen
3. selects the target user
4. presses send
5. returns to the camera view

Every 10 sends, it restarts Snapchat as a recovery step.

## Features

### Discord commands

- `!snap` — interactive flow to enter a Snapchat username and the number of points/snaps to generate
- `!status` — shows whether a run is currently active and how many sends have completed so far
- `!logs` — shows the tail of the current log file
- `!purge` — deletes the current Discord channel and recreates it in the same position

The bot uses an internal lock so only one automation run can happen at a time.

### Logging

Logging is configured with a timed rotating file handler. By default the bot writes to `botlog.log`, rotates at midnight, and keeps 14 backups.

### Authentication

The Discord token is loaded from:

1. `DISCORD_TOKEN` environment variable
2. `config.ini` under `[BOT] token=...`

The environment variable is preferred.

## Project layout

The imports show that this project is expected to be organized with a `utils` package, even if your uploaded files are currently flattened.

Suggested layout:

```text
snapbot/
├─ bot.py
├─ script.py
├─ script_adduser.py
├─ requirements.txt
└─ utils/
   ├─ __init__.py
   ├─ bot_utils.py
   ├─ clicking.py
   ├─ setup_logging.py
   ├─ bounds.py
   └─ snapcode.py
```

If you keep everything in one folder, you will need to update imports like `from utils.bot_utils import ...` and `from utils import adbConnection`.

## Requirements

### Software

- Python 3.10+ recommended
- ADB installed and available on your PATH
- an Android phone connected through USB or network ADB
- USB debugging enabled on the phone
- Snapchat installed and already signed in on the device
- a Discord bot token

### Python packages

Install the main dependencies with:

```bash
pip install -r requirements.txt
```

The provided `requirements.txt` includes the bot and ADB dependencies such as `discord.py` and `pure-python-adb`.

## Installation

### 1. Clone the project

```bash
git clone <your-repo-url>
cd snapbot
```

### 2. Create and activate a virtual environment

#### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

#### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set your Discord token

Preferred:

```bash
export DISCORD_TOKEN="your-token-here"
```

On Windows PowerShell:

```powershell
$env:DISCORD_TOKEN="your-token-here"
```

Or create a `config.ini` file:

```ini
[BOT]
token=your-token-here
```

### 5. Connect and verify your Android device

```bash
adb devices
```

Make sure:

- your phone appears in the device list
- you accepted the device authorization prompt
- the phone is awake or can be woken by ADB
- Snapchat opens normally on the device

## Running the bot

Start the Discord bot with:

```bash
python bot.py
```

Once the bot is online, use the commands in your Discord server.

## Usage

### Send snaps / generate points

1. Run `!snap` in Discord.
2. Enter the target Snapchat username.
3. Enter the number of sends to perform.
4. Wait for the bot to finish.

You can cancel the interactive flow by replying with:

```text
/quit
```

## Running helper scripts directly

You can also call the worker scripts without Discord.

### Send snaps directly

```bash
python script.py <username> <points>
```

Example:

```bash
python script.py exampleuser 25
```

## Notes about device compatibility

This project relies on Snapchat Android UI identifiers and UI dumps. If Snapchat changes its layout, IDs, or flow, the automation may stop working until the selectors are updated.

The repository also contains an older `snapchat.py` GUI prototype that appears to be a more device-specific version built around screenshots, image matching, and fixed Pixel 5 coordinates. It is not part of the main Discord bot flow.

If you want to use that legacy GUI script, you will likely need extra packages that are **not** listed in the current `requirements.txt`, such as Pillow, PySimpleGUI, pyautogui, and pyscreeze.

## Troubleshooting

### `No Discord token found`

Set `DISCORD_TOKEN` or create `config.ini` with:

```ini
[BOT]
token=your-token-here
```

### `No adb devices connected`

- confirm USB debugging is enabled
- run `adb devices`
- reconnect the cable or re-authorize the device

### Snapchat opens but clicks fail

- unlock the phone first
- make sure Snapchat is already logged in
- verify the app UI still matches the expected selectors
- check the generated log output for the failing step


## Log files

By default logs are written to:

```text
botlog.log
```

You can override the log file path with:

```bash
export BOT_LOG_FILE="custom.log"
```
