import logging
from logging.handlers import TimedRotatingFileHandler

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = TimedRotatingFileHandler("botlog.log", when="midnight", interval=1)
dt_fmt = '%Y-%m-%d %H:%M:%S'
formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')
handler.setFormatter(formatter)
logger.addHandler(handler)

def setLog(logger):
    logger.setLevel(logging.DEBUG)
    handler = TimedRotatingFileHandler("botlog.log", when="midnight", interval=1)
    dt_fmt = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger