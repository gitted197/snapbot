"""Remember the command channel automatically and show commands on startup."""
import asyncio
import json
from pathlib import Path
import logging

import discord

logger = logging.getLogger(__name__)

DESCRIPTIONS = {
    "snap": "Start een run en voer ontvangernaam en aantal in.",
    "snapnaam": "Corrigeer de naam wanneer je run daarom vraagt.",
    "snapverder": "Bij onzekere verzending: verzonden of opnieuw. Controleer eerst de wachtrij.",
    "snapstop": "Stop je actieve run; een al verzonden snap kan nog onderweg zijn.",
    "addsnap": "Voeg een Snapchat-vriend toe via de invoervragen.",
    "status": "Toon de huidige botstatus.",
    "logs": "Toon recente logregels.",
    "purge": "Verwijder dit Discord-kanaal en maak het opnieuw aan.",
    "help": "Toon de ingebouwde command-help.",
    "commando": "Toon dit commando-overzicht opnieuw.",
}


def overview_embed(client):
    embed = discord.Embed(title="SnapBot — commando’s", colour=0x229ED9)
    commands = sorted((c for c in client.commands if not c.hidden), key=lambda c: c.name)
    lines = []
    for command in commands:
        usage = f"!{command.name} {command.signature}".rstrip()
        description = DESCRIPTIONS.get(command.name) or command.short_doc or "Geen beschrijving beschikbaar."
        lines.append(f"`{usage}` — {description}")
    embed.description = "\n\n".join(lines) or "Er zijn geen commands geladen."
    embed.set_footer(text="Tijdens de invoervragen: /quit om te annuleren. Gebruik !commando voor dit overzicht.")
    return embed


CHANNEL_FILE = Path(__file__).resolve().parents[1] / "xml" / "discord_channel.json"


def startup_channel_id():
    try:
        value = json.loads(CHANNEL_FILE.read_text(encoding="utf-8"))["channel_id"]
        return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _lock(client):
    lock = getattr(client, "_command_overview_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        client._command_overview_lock = lock
    return lock


async def remember_command_channel(client, channel, replace=False, post=True):
    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        return
    try:
        async with _lock(client):
            if replace or startup_channel_id() is None:
                CHANNEL_FILE.parent.mkdir(parents=True, exist_ok=True)
                temp = CHANNEL_FILE.with_suffix(".tmp")
                temp.write_text(json.dumps({"channel_id": channel.id}), encoding="utf-8")
                temp.replace(CHANNEL_FILE)
                client._command_overview_sent = False
        if post:
            await post_startup_commands(client)
    except Exception:
        logger.exception("Kon het gebruikte Discord-kanaal niet onthouden")


async def post_startup_commands(client):
    # on_ready can run again after reconnecting. Serialize concurrent events.
    async with _lock(client):
        if getattr(client, "_command_overview_sent", False):
            return
        try:
            channel_id = startup_channel_id()
            if channel_id is None:
                logger.info("Nog geen kanaal onthouden; het eerste commando kiest dit automatisch.")
                return
            channel = client.get_channel(channel_id)
            if channel is None:
                channel = await client.fetch_channel(channel_id)
            if not isinstance(channel, (discord.TextChannel, discord.Thread)):
                logger.error("Opstartkanaal %s is geen tekstkanaal of thread", channel_id)
                return
            await channel.send(embed=overview_embed(client), allowed_mentions=discord.AllowedMentions.none())
            client._command_overview_sent = True
            logger.info("Commando-overzicht geplaatst in kanaal %s", channel_id)
        except Exception:
            # A missing permission or invalid channel must not stop the bot.
            logger.exception("Kon het commando-overzicht niet plaatsen")
