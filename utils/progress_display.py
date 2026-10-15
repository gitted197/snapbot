"""Update a single run message with throttled confirmed progress."""
import asyncio
import logging
from time import monotonic

import discord

logger = logging.getLogger(__name__)


class ProgressDisplay:
    def __init__(self, message, booster, recipient, total, interval=5.0):
        self.message = message
        self.booster = booster
        self.recipient = recipient
        self.total = total
        self.interval = interval
        self.last_edit = float("-inf")
        self.closed = False
        self.lock = asyncio.Lock()

    async def update(self, completed, status="Bezig", detail="", recipient=None, force=False, final=False):
        async with self.lock:
            if self.closed:
                return
            if recipient:
                self.recipient = recipient
            now = monotonic()
            if not force and now - self.last_edit < self.interval:
                return
            self.last_edit = now
            text = (f"Ontvanger: {str(self.recipient)[:200]}\n"
                    f"Voortgang: **{completed} / {self.total} bevestigde snaps**\n"
                    f"Status: **{status}**")
            if detail:
                text += "\n\n" + detail[:2000]
            embed = discord.Embed(title="Boosting account for user " + self.booster,
                                  description=text)
            try:
                await self.message.edit(content=None, embed=embed,
                                        allowed_mentions=discord.AllowedMentions.none())
            except Exception:
                # A Discord edit failure must never trigger a resend on the phone.
                logger.exception("Could not edit the run progress message")
            finally:
                if final:
                    self.closed = True
