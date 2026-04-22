import glob
import os
from typing import Optional, Tuple

import discord  # type: ignore

def setEmbed(description: str, booster: str) -> Tuple[discord.Embed, str]:
    embed = discord.Embed(
        title="Boosting account for user " + booster,
        description=description,
    )
    return embed, description

def setAddSnapEmbed(description: str, booster: str) -> Tuple[discord.Embed, str]:
    embed = discord.Embed(
        title="Adding friend for user " + booster,
        description=description,
    )
    return embed, description

def setLoggingEmbed(description: str, booster: str) -> Tuple[discord.Embed, str]:
    embed = discord.Embed(
        title="Getting logs for user " + booster,
        description=description,
    )
    return embed, description

def _latest_logfile(base: str = "botlog.log") -> Optional[str]:
    candidates = glob.glob(base) + glob.glob(base + ".*")
    if not candidates:
        return None
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return candidates[0]

def getLogs(max_chars: int = 1800, base: str = "botlog.log") -> str:
    path = _latest_logfile(base=base)
    if not path:
        return "Geen logfile gevonden."

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    if len(content) > max_chars:
        return content[-max_chars:]
    return content
