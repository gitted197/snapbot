# SnapGen

## Description
Generate Snapchat account points for a user by sending multiple photo's to that user. Opening them on the user's side generates 1 point for each photo.

## Installation
Extract all files to a location of your choice. To use the script from discord, setup a discord bot in the developer portal and add it to your server. Copy the bot token from the developer portal to your config.ini in the main folder, following this setup:
```
[BOT]
token = bottokenhere
```

Install dependencies according to requirements.txt.

## Usage
The script is usable in two ways: directly from the command line or using a discord bot. Please follow the steps at [Installation](#installation) to setup the script for usage.

To use the script from the command line simply enter the username and amount of points as an argument:
```
python script.py [username] [points to generate]
python script.py TheAmazingUser 4223
```

To use the script from discord, start the script from 'bot.py' and use the !snap command in any discord channel to trigger the username/points user input.
## Roadmap
```
- Make exit command to interrupt bot questions
    ~~- For !snap~~
    - For !addsnap
- Prevent script from starting when the other script is running
- Notify in discord channel that bot is finished
~~- Implement logging~~
    ~~- Make log file each day~~
- Make log callable for certain users
    - Pass amount of lines you want the bot the return when calling the log
```
## Authors and acknowledgment
Thanks J.

## Project status
December '22 - Currently in development
<<<<<<< HEAD
# snapbot
=======
>>>>>>> 367aef1 (original)
