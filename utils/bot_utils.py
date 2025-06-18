import discord
from discord.ext import commands
import logging
from utils.setup_logging import setLog
#import os

logger = logging.getLogger(__name__)
logger = setLog(logger)


def setEmbed(desc, booster):
    if desc == "":
        description = "Type '/quit' to stop. \nEnter screenname to boost: "
        logging.debug("setEmbed: Description is empty, setting embed")
    else:
        description = desc
        logging.debug("setEmbed: Description exists. Adding to it")
    embed = discord.Embed(
        title="Snap boosting for user " + booster,
        description = description
    )
    return embed, description

def setAddSnapEmbed(desc, addfor):
    if desc == "":
        description = "Type '/quit' to stop. \nEnter username to add to Snapchat account: "
        logging.debug("setAddSnapEmbed: Description is empty, setting embed")
    else:
        description = desc
        logging.debug("setAddSnapEmbed: Description exists. Adding to it")
    embed = discord.Embed(
        title="Adding username to Snapchat for user " + addfor,
        description = description
    )
    return embed, description

def setLoggingEmbed(desc, booster):
    if desc == "":
        description = "Grabbing latest 30 log lines: "
        logging.debug("setLoggingEmbed: Description is empty, setting embed")
    else:
        description = desc
        logging.debug("setLoggingEmbed: Description exists. Adding to it")
    embed = discord.Embed(
        title="Grabbing logs for user " + booster,
        description = description
    )
    return embed, description

def getLogs():
    logarray = []
    with open("botlog.log.2023-07-18") as file:
        for line in (file.readlines() [-20:]):
            print(line, end ='')
            logarray.append(line)
    return logarray
