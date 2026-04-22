import asyncio
import configparser
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import discord  # type: ignore
from discord.ext import commands  # type: ignore

import script
import script_adduser
from utils.bot_utils import setEmbed, setAddSnapEmbed, setLoggingEmbed, getLogs
from utils.setup_logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

def _load_token() -> str:
    # Prefer env var; fallback to config.ini for backwards compatibility
    token = os.getenv("DISCORD_TOKEN")
    if token:
        return token

    config = configparser.ConfigParser()
    config.read("config.ini")
    if "BOT" in config and "token" in config["BOT"]:
        return config["BOT"]["token"]

    raise RuntimeError("No Discord token found. Set DISCORD_TOKEN or provide config.ini with [BOT] token=...")

@dataclass
class BotState:
    running: bool = False
    points_counter: int = 0
    last_error: Optional[str] = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

state = BotState()

intents = discord.Intents.all()
client = commands.Bot(command_prefix="!", intents=intents)

@client.event
async def on_ready():
    logger.info("Logged in as %s", client.user)

@client.command()
async def snap(ctx: commands.Context):
    booster = str(ctx.author)
    logger.info("Snap command by: %s", booster)
    await ctx.message.delete()

    async with state.lock:
        if state.running:
            botmsg = await ctx.send("Program is currently running. Please try again later")
            await asyncio.sleep(3)
            await botmsg.delete()
            return

        state.running = True
        state.last_error = None

        description = "Enter the screenname to send snaps to (or /quit): "
        embed, description = setEmbed(description, booster)
        sent = await ctx.send(embed=embed)

        def check(msg):
            return msg.author == ctx.author and msg.channel == ctx.channel

        try:
            msg = await client.wait_for("message", check=check)
            if msg.content == "/quit":
                await msg.delete()
                botmsg = await ctx.send("Program was stopped by user.")
                await asyncio.sleep(3)
                await botmsg.delete()
                return

            username = msg.content
            await msg.delete()
            description = description + username + "\nEnter amount of points to generate: "
            embed, description = setEmbed(description, booster)
            await sent.edit(embed=embed)

            while True:
                msg = await client.wait_for("message", check=check)
                if msg.content == "/quit":
                    await msg.delete()
                    botmsg = await ctx.send("Program was stopped by user.")
                    await asyncio.sleep(3)
                    await botmsg.delete()
                    return
                try:
                    await msg.delete()
                    points = int(msg.content)
                    break
                except Exception:
                    botmsg = await ctx.send("Error getting points input. Please try again.")
                    logger.exception("Error while getting points input")
                    await asyncio.sleep(3)
                    await botmsg.delete()

            description = description + str(points) + "\nNow generating. Please wait."
            embed, description = setEmbed(description, booster)
            await sent.edit(embed=embed)

            # Run blocking script in a worker thread
            try:
                generated = await asyncio.to_thread(script.mainScript, username, points)
                state.points_counter = generated
            except Exception as e:
                logger.exception("snap failed")
                state.last_error = str(e)
                await sent.edit(content=f"Fout: {e}")
                return

            description = description + f"\nDone. Generated {state.points_counter} points."
            embed, description = setEmbed(description, booster)
            await sent.edit(embed=embed)
            await asyncio.sleep(5)
            await sent.delete()

        finally:
            state.running = False

@client.command()
async def addsnap(ctx: commands.Context):
    booster = str(ctx.author)
    logger.info("AddSnap command by: %s", booster)
    await ctx.message.delete()

    async with state.lock:
        if state.running:
            botmsg = await ctx.send("Program is currently running. Please try again later")
            await asyncio.sleep(3)
            await botmsg.delete()
            return

        state.running = True
        state.last_error = None

        description = "Enter the screenname to add (or /quit): "
        embed, description = setAddSnapEmbed(description, booster)
        sent = await ctx.send(embed=embed)

        def check(msg):
            return msg.author == ctx.author and msg.channel == ctx.channel

        try:
            msg = await client.wait_for("message", check=check)
            if msg.content == "/quit":
                await msg.delete()
                botmsg = await ctx.send("Program was stopped by user.")
                await asyncio.sleep(3)
                await botmsg.delete()
                return

            username = msg.content
            await msg.delete()
            description = description + username + "\nAdding friend…"
            embed, description = setAddSnapEmbed(description, booster)
            await sent.edit(embed=embed)

            rc = await asyncio.to_thread(script_adduser.mainScriptAddSnap, username)
            if rc != 0:
                await sent.edit(content="Fout bij toevoegen.")
                return

            description = description + "\nDone."
            embed, description = setAddSnapEmbed(description, booster)
            await sent.edit(embed=embed)
            await asyncio.sleep(5)
            await sent.delete()

        finally:
            state.running = False

@client.command()
async def status(ctx: commands.Context):
    checker = str(ctx.author)
    logger.info("Status command by: %s", checker)
    await ctx.message.delete()

    if not state.running:
        embed = discord.Embed(
            title="Checked status for user " + checker,
            description="Bot is currently not running. This message will delete in a few seconds.",
        )
    else:
        embed = discord.Embed(
            title="Checked status for user " + checker,
            description=f"Bot is currently running. It has generated {state.points_counter} points so far.",
        )

    sent = await ctx.send(embed=embed)
    await asyncio.sleep(5)
    await sent.delete()

@client.command()
async def purge(ctx: commands.Context):
    await ctx.channel.delete()
    new_channel = await ctx.channel.clone(reason="Channel was purged")
    await new_channel.edit(position=ctx.channel.position)

@client.command()
async def logs(ctx: commands.Context):
    logging_user = str(ctx.author)
    logger.info("Logs command by: %s", logging_user)
    await ctx.message.delete()

    description = "Collecting logs…"
    embed, description = setLoggingEmbed(description, logging_user)
    sent = await ctx.send(embed=embed)

    loglines = getLogs()
    description = "```" + loglines + "```"
    embed = discord.Embed(
        title="Logs for user " + logging_user,
        description=description,
    )
    await sent.edit(embed=embed)

if __name__ == "__main__":
    token = _load_token()
    client.run(token)
