from ppadb.client import Client as AdbClient  # type: ignore
from time import sleep
import logging
from pathlib import Path

from utils.setup_logging import setup_logging

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../snapbot
XML_DIR = PROJECT_ROOT / "xml"
XML_DIR.mkdir(parents=True, exist_ok=True)

setup_logging()
logger = logging.getLogger(__name__)

def adbConnection():
    adb = AdbClient(host="127.0.0.1", port=5037)
    logger.debug("Set AdbClient")

    devices = adb.devices()
    logger.debug("Listed adb devices")

    if not devices:
        raise RuntimeError("No adb devices connected")
    return devices[0]

def checkInt(points_input):
    try:
        return int(points_input)
    except ValueError as e:
        raise ValueError("Please enter a number.") from e

def startSnap(device):
    try:
        device.shell("input keyevent KEYCODE_WAKEUP")
        device.shell("am force-stop com.snapchat.android")
        sleep(1)
        device.shell("monkey -p com.snapchat.android -c android.intent.category.LAUNCHER 1")
        sleep(1)
        logger.debug("Succesfuly opened snap")
    except Exception:
        logger.exception("Error while starting snap:")

def rebootSnap(device):
    try:
        device.shell("am force-stop com.snapchat.android")
        sleep(1)
        device.shell("monkey -p com.snapchat.android -c android.intent.category.LAUNCHER 1")
        sleep(1)
        logger.debug("Succesfuly opened snap")
    except Exception:
        logger.exception("Error while rebooting snap:")

def getDump(device, phase):
    try:
        dumpstring = f"uiautomator dump /sdcard/{phase}.xml"
        device.shell(dumpstring)

        pull_src = f"/sdcard/{phase}.xml"
        pull_dst = str(XML_DIR / f"{phase}.xml")
        device.pull(pull_src, pull_dst)

        logger.debug("Got xml dump from phone")
    except Exception:
        logger.exception("Error while getting dump from phone:")
