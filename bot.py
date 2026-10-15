import asyncio
import configparser
import logging
import os
from utils.progress_display import ProgressDisplay
from dataclasses import dataclass, field
from typing import Optional

import discord  # type: ignore
from discord.ext import commands  # type: ignore

import script
import script_adduser
from utils import check_adb_access, AdbAccessError
from utils.run_control import RunControl, RunStopped
from utils.bot_utils import setEmbed, setAddSnapEmbed, setLoggingEmbed, getLogs
from utils.setup_logging import setup_logging
from utils.command_overview import overview_embed, post_startup_commands, remember_command_channel

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
    control: Optional[RunControl] = None
    owner_id: Optional[int] = None
    channel_id: Optional[int] = None
    paused: bool = False

state = BotState()

intents = discord.Intents.all()
client = commands.Bot(command_prefix="!", intents=intents)

@client.event
async def on_ready():
    logger.info("Logged in as %s", client.user)
    await post_startup_commands(client)

@client.listen("on_command")
async def remember_channel_on_command(ctx: commands.Context):
    if ctx.command.name != "commando":
        await remember_command_channel(client, ctx.channel)


@client.command(name="commando")
async def command_overview(ctx: commands.Context):
    await remember_command_channel(client, ctx.channel, replace=True, post=False)
    await ctx.send(embed=overview_embed(client), allowed_mentions=discord.AllowedMentions.none())
    client._command_overview_sent = True

@client.command()
async def snap(ctx: commands.Context):
    booster = str(ctx.author)
    logger.info("Snap command by: %s", booster)
    await ctx.message.delete()

    if state.running:
        await ctx.send("Er is al een run actief; gebruik !status.")
        return
    async with state.lock:
        if state.running:
            botmsg = await ctx.send("Program is currently running. Please try again later")
            await asyncio.sleep(3)
            await botmsg.delete()
            return

        try:
            await asyncio.to_thread(check_adb_access)
        except AdbAccessError as exc:
            state.last_error = str(exc)
            await ctx.send(f"❌ !snap kan niet starten: {exc}\nHerstel dit en voer opnieuw !snap uit.")
            return

        state.running = True
        state.last_error = None
        state.points_counter = 0
        state.owner_id = ctx.author.id
        state.channel_id = ctx.channel.id
        loop = asyncio.get_running_loop()
        progress = None

        async def deliver(kind, message, completed, total):
            if state.control is not run_control:
                return
            state.points_counter = completed
            if kind == "paused":
                state.paused = True
            elif kind == "resumed":
                state.paused = False
            if progress is not None:
                await progress.update(
                    completed,
                    status="Gepauzeerd" if state.paused else "Bezig",
                    detail=message if kind != "progress" else "",
                    recipient=getattr(run_control, "username", None),
                    force=kind != "progress",
                )

        def notify(kind, message, completed, total):
            future = asyncio.run_coroutine_threadsafe(deliver(kind, message, completed, total), loop)
            def report_error(done):
                try:
                    done.result()
                except Exception:
                    logger.exception("Discord run feedback could not be delivered")
            future.add_done_callback(report_error)

        run_control = RunControl(notify)
        state.control = run_control

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
                    if points <= 0:
                        raise ValueError("Aantal moet positief zijn")
                    break
                except Exception:
                    botmsg = await ctx.send("Error getting points input. Please try again.")
                    logger.exception("Error while getting points input")
                    await asyncio.sleep(3)
                    await botmsg.delete()

            progress = ProgressDisplay(sent, booster, username, points)
            await progress.update(0, force=True)

            # Run blocking script in a worker thread
            try:
                generated = await asyncio.to_thread(script.mainScript, username, points, state.control)
                state.points_counter, elapsed_seconds = generated
            except Exception as e:
                logger.exception("snap failed")
                state.last_error = str(e)
                state.points_counter = state.control.completed
                await progress.update(
                    state.points_counter, status="Gestopt" if isinstance(e, RunStopped) else "Fout",
                    detail=str(e), recipient=getattr(run_control, "username", None),
                    force=True, final=True,
                )
                return

            await progress.update(
                state.points_counter, status="Afgerond",
                detail=f"Duur: {script.formatDuration(elapsed_seconds)}",
                recipient=getattr(run_control, "username", None), force=True, final=True,
            )

        finally:
            if progress is not None:
                progress.closed = True
            state.running = False
            state.paused = False
            state.control = None
            state.owner_id = None
            state.channel_id = None

def _owns_run(ctx):
    return (state.control is not None and ctx.author.id == state.owner_id
            and ctx.channel.id == state.channel_id)


@client.command()
async def snapnaam(ctx: commands.Context, *, naam: str):
    if not _owns_run(ctx) or not naam.strip():
        await ctx.send("Geen eigen run in dit kanaal beschikbaar.")
        return
    if not state.control.decide("username", naam.strip()):
        await ctx.send("De run wacht momenteel niet op een nieuwe naam.")


@client.command()
async def snapverder(ctx: commands.Context, keuze: str):
    if not _owns_run(ctx):
        await ctx.send("Alleen de eigenaar van de run kan deze keuze maken.")
        return
    if keuze not in ("verzonden", "opnieuw"):
        await ctx.send("Gebruik !snapverder verzonden of !snapverder opnieuw.")
        return
    if not state.control.decide("send", keuze):
        await ctx.send("De run wacht momenteel niet op een verzendbeslissing.")


@client.command()
async def snapstop(ctx: commands.Context):
    if not _owns_run(ctx):
        await ctx.send("Geen eigen run in dit kanaal beschikbaar.")
        return
    state.control.cancelled.set()
    await ctx.send("Stop aangevraagd. Een reeds getikte verzending kan nog onderweg zijn.")


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
        mode = "gepauzeerd" if state.paused else "actief"
        embed = discord.Embed(
            title="Checked status for user " + checker,
            description=f"Run {mode}. Bevestigd: {state.points_counter} snaps.",
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
