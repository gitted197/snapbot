import logging
from utils.setup_logging import logger
import discord
import configparser
import threading
from time import sleep
from discord.ext import commands
from utils.bot_utils import setEmbed, setAddSnapEmbed, setLoggingEmbed, getLogs
import script
import script_adduser
import sys


logger.debug("Starting script")
logger.debug("Parsing and reading config.ini")
config = configparser.ConfigParser()
config.read('config.ini')
logger.debug("Config read. Finding token.")
token = config['BOT']['token']

logger.debug("Setting Discord intents")
intents = discord.Intents.all()
client = commands.Bot(command_prefix='!', intents=intents)

myThread = None
myAddSnapThread = None

@client.command()
async def snap(ctx):
    booster = str(ctx.author)
    logger.info("Snap command by: " + booster)
    await ctx.message.delete()
    logger.debug("Snap command message deleted")

    global myThread
    global myAddSnapThread
    #check if thread is running
    logger.debug("Checking if snap thread is running")
    if myThread is None or not myThread.is_alive():
        logger.debug("Snap thread is not running. Setting embed")
        description = ""
        embed, description = setEmbed(description, booster)
        sent = await ctx.send(embed=embed)
        logger.debug("Embed sent to channel")

        def check(msg):
            return msg.author == ctx.author and msg.channel == ctx.channel
        
        msg = await client.wait_for("message", check=check)

        if msg.content != "/quit":
            logger.debug("User message for setting screenname found")
            username = msg.content
            logger.info("Set screenname to send snaps to: " + username)
            await msg.delete()
            logger.debug("Deleted screenname message")
            description = description + username + "\nEnter amount of points to generate: "
            embed, description = setEmbed(description, booster)
            await sent.edit(embed=embed)
            logger.debug("Added screenname information to embed")

            while True:
                msg = await client.wait_for("message", check=check)
                logger.debug("Received message, checking for int")
                if msg.content != "/quit":
                    try:
                        await msg.delete()
                        logger.debug("Deleted potential int message")
                        points = int(msg.content)
                        logpoints = str(points)
                        logger.info("Set points to generate to: " + logpoints)
                        break
                    except Exception:
                        botmsg = await ctx.send("Error getting points input. Please try again after this message is gone.")
                        logging.exception("Error while getting points input:")
                        sleep(3)
                        await botmsg.delete()
                        logging.debug("Deleted bot error message")
                        continue
                else: 
                    await msg.delete()
                    botmsg = await ctx.send("Program was stopped by user.")
                    logger.info("Program was stopped by user")
                    sleep(3)
                    await botmsg.delete()
                    logger.debug("Bot message deleted")
                    return
        

            strpoints = str(points)
            description = description + strpoints + "\nNow generating points. Please wait."
            embed, description = setEmbed(description, booster)
            await sent.edit(embed=embed)
            logger.debug("Added points information to embed")

            #sending variables to thread
            myThread = threading.Thread(target=script.mainScript, args=(username, points), name="sending_snaps")
            myThread.start()
            logger.debug("Started thread for sending snaps")
        else:
            await msg.delete()
            botmsg = await ctx.send("Program was stopped by user.")
            logger.info("Program was stopped by user")
            sleep(3)
            await botmsg.delete()
            logger.debug("Bot message deleted")
    else:
        botmsg = await ctx.send("Program is currently running. Please try again later")
        logger.info("Snap thread is running. Prompted user to try again later")
        sleep(3)
        await botmsg.delete()
        logger.debug("Bot message deleted")

@client.command()
async def addsnap(ctx):
    addfor = str(ctx.author)
    logger.info("Addsnap command by: " + addfor)
    await ctx.message.delete()
    logger.debug("Addsnap command message deleted")

    global myAddSnapThread
    global myThread
    #check if thread is running
    logger.debug("Checking if addsnap thread is running")
    if myAddSnapThread is None or not myAddSnapThread.is_alive():
        logger.debug("Snap thread is not running. Setting embed")
        description = ""
        embed, description = setAddSnapEmbed(description, addfor)
        sent = await ctx.send(embed=embed)
        botmsgid = sent.id
        logger.debug("Embed sent to channel")

        def check(msg):
            return msg.author == ctx.author and msg.channel == ctx.channel
        
        while True:
            msg = await client.wait_for("message", check=check)
            logger.debug("User message for setting username found. Checking validity")
            try:
                await msg.delete()
                logger.debug("Deleted potential username message")
                username = msg.content
                if ("_" in username):
                    usernameValidation = username.replace("_", "")
                    if (usernameValidation.isalnum() == True):
                        print("Valid1!")
                        break
                    else:
                        botmsg = await ctx.send("Username can only contain A-Z, 0-9 and _ (underscore) sign. Please try again after this message is gone.")
                        logging.exception("Error while getting username input:")
                        sleep(3)
                        await botmsg.delete()
                        logging.debug("Deleted bot error message")
                        continue
                else:
                    if (username.isalnum() == False):
                        botmsg = await ctx.send("Username can only contain A-Z, 0-9 and _ (underscore) sign. Please try again after this message is gone.")
                        logging.exception("Error while getting username input:")
                        sleep(3)
                        await botmsg.delete()
                        logging.debug("Deleted bot error message")
                        continue
                    else:
                        print("Isalnum!")
                        break
                #logger.info("Set username to add to account: " + username)
            except Exception:
                botmsg = await ctx.send("Error getting points input. Please try again after this message is gone.")
                logging.exception("Error while getting points input:")
                sleep(3)
                await botmsg.delete()
                logging.debug("Deleted bot error message")
                continue

        logger.info("Set username to add to account: " + username)
        description = description + username + "\nUsername received. Will now add user: " + username + ". Please wait a few minutes before boosting."
        embed, description = setAddSnapEmbed(description, addfor)
        await sent.edit(embed=embed)
        logger.debug("Added username information to embed")

        print(username)
        myAddSnapThread = threading.Thread(target=script_adduser.mainScriptAddSnap, args=(username,), name="adding_snap_account")
        myAddSnapThread.start()
        logger.debug("Started thread for adding account")
    else:
        botmsg = await ctx.send("Program is currently running. Please try again later")
        logger.info("Add Snap thread is running. Prompted user to try again later")
        sleep(3)
        await botmsg.delete()
        logger.debug("Bot message deleted")

@client.command()
async def status(ctx):
    checker = str(ctx.author)
    logger.info("Status command by: " + checker)
    await ctx.message.delete()
    logger.debug("Status command message deleted")

    global pointscounter
    global myThread
    #check if thread is running
    logger.debug("Checking if snap thread is running")
    if myThread is None or not myThread.is_alive():
        logger.debug("Snap thread is not running. Setting embed")
        embed = discord.Embed(
            title="Checked status for user " + checker,
            description = "Bot is currently not generating points. Go ahead and boost your account! This message will delete in a few seconds."
        )
        sent = await ctx.send(embed=embed)
        logger.debug("Embed sent to channel")
        sleep(5)
        await sent.delete()
        logger.debug("Status embed deleted")
    else:
        logger.debug("Snap thread is running.")
        embed = discord.Embed(
            title="Checked status for user " + checker,
            description = "Bot is currently generating points. It has currently generated " + pointscounter + " points. This message will delete in a few seconds."
        )
        sent = await ctx.send(embed=embed)
        logger.debug("Embed sent to channel")
        sleep(5)
        await sent.delete()


@client.command()
async def purge(ctx):
        await ctx.channel.delete()
        new_channel = await ctx.channel.clone(reason="Channel was purged")
        await new_channel.edit(position=ctx.channel.position)


@client.command()
async def logs(ctx):
    logging_user = str(ctx.author)
    logger.info("Logging command by: " + logging_user)
    await ctx.message.delete()
    logger.debug("Logging command message deleted")
    logger.debug("Setting embed")
    description = ""
    embed, description = setLoggingEmbed(description, logging_user)
    sent = await ctx.send(embed=embed)
    logger.debug("Embed sent to channel")

    loglines = getLogs()
    logger.info(loglines)
    logger.info(sys.getsizeof(loglines))
    
    description = description.join(loglines)
    embed, description = setEmbed(description, logging_user)
    logger.info(sys.getsizeof(embed))
    await sent.edit(embed=embed)
    logger.debug("Added logs to embed")


    """def check(msg):
        return msg.author == ctx.author and msg.channel == ctx.channel
        
    msg = await client.wait_for("message", check=check)

        if msg.content != "/quit":
            logger.debug("User message for setting screenname found")
            username = msg.content
            logger.info("Set screenname to send snaps to: " + username)
            await msg.delete()
            logger.debug("Deleted screenname message")
            description = description + username + "\nEnter amount of points to generate: "
            embed, description = setEmbed(description, booster)
            await sent.edit(embed=embed)
            logger.debug("Added screenname information to embed")

            while True:
                msg = await client.wait_for("message", check=check)
                logger.debug("Received message, checking for int")
                if msg.content != "/quit":
                    try:
                        await msg.delete()
                        logger.debug("Deleted potential int message")
                        points = int(msg.content)
                        logpoints = str(points)
                        logger.info("Set points to generate to: " + logpoints)
                        break
                    except Exception:
                        botmsg = await ctx.send("Error getting points input. Please try again after this message is gone.")
                        logging.exception("Error while getting points input:")
                        sleep(3)
                        await botmsg.delete()
                        logging.debug("Deleted bot error message")
                        continue
                else: 
                    await msg.delete()
                    botmsg = await ctx.send("Program was stopped by user.")
                    logger.info("Program was stopped by user")
                    sleep(3)
                    await botmsg.delete()
                    logger.debug("Bot message deleted")
                    return
        

            strpoints = str(points)
            description = description + strpoints + "\nNow generating points. Please wait."
            embed, description = setEmbed(description, booster)
            await sent.edit(embed=embed)
            logger.debug("Added points information to embed")

            #sending variables to thread
            myThread = threading.Thread(target=script.mainScript, args=(username, points), name="sending_snaps")
            myThread.start()
            logger.debug("Started thread for sending snaps")
        else:
            await msg.delete()
            botmsg = await ctx.send("Program was stopped by user.")
            logger.info("Program was stopped by user")
            sleep(3)
            await botmsg.delete()
            logger.debug("Bot message deleted")
    else:
        botmsg = await ctx.send("Program is currently running. Please try again later")
        logger.info("Snap thread is running. Prompted user to try again later")
        sleep(3)
        await botmsg.delete()
        logger.debug("Bot message deleted")"""

client.run(token)