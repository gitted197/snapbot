from ppadb.client import Client as AdbClient # type: ignore
from time import sleep
import logging
from utils.setup_logging import setLog
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../snapbot
XML_DIR = PROJECT_ROOT / "xml"
XML_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
logger = setLog(logger)



def adbConnection():
    try:
        adb = AdbClient(host='127.0.0.1', port=5037)
        logger.debug("Set AdbClient")
    except Exception:
        logger.exception("Error while setting AdbClient: ")
    try:
        devices = adb.devices()
        logger.debug("Listed adb devices")
    except Exception:
        logger.exception("Error while listing adb devices")
    device = devices[0]
    #print("Selected device")
    return device

def checkInt(points_input):
    try:
        userInput = int(points_input)
    except ValueError:
        print("Please enter a number.")
        exit
    else:
        return userInput

def startSnap(device):
        try:
            device.shell("input keyevent KEYCODE_WAKEUP")
            #device.shell("input swipe 550 2100 550 500")
            device.shell("am force-stop com.snapchat.android")
            #sleep(2)
            #device.shell("pm disable com.snapchat.android")
            #sleep(3)
            #device.shell("pm enable com.snapchat.android")
            sleep(1)
            device.shell("monkey -p com.snapchat.android -c android.intent.category.LAUNCHER 1")
            sleep(1)
            logger.debug("Succesfuly opened snap")
        except Exception:
            logger.exception("Error while starting snap: ")    

def rebootSnap(device):
        try:
            device.shell("am force-stop com.snapchat.android")
            #sleep(2)
            #device.shell("pm disable com.snapchat.android")
            #sleep(3)
            #device.shell("pm enable com.snapchat.android")
            sleep(1)
            device.shell("monkey -p com.snapchat.android -c android.intent.category.LAUNCHER 1")
            sleep(1)
            logger.debug("Succesfuly opened snap")
        except Exception:
            logger.exception("Error while starting snap: ")  

#def getDump(device, phase):
#    try:
#        dumpstring = "uiautomator dump /sdcard/{0}.xml".format(phase)
#        device.shell(dumpstring)
#        pullstring1, pullstring2 = "/sdcard/{0}.xml".format(phase), "xml/{0}.xml".format(phase)
#        device.pull(pullstring1, pullstring2)
#        logger.debug("Got xml dump from phone")
#    except Exception:
#        logger.exception("Error while getting dump from phone: ")

def getDump(device, phase):
    try:
        dumpstring = f"uiautomator dump /sdcard/{phase}.xml"
        device.shell(dumpstring)

        pull_src = f"/sdcard/{phase}.xml"
        pull_dst = str(XML_DIR / f"{phase}.xml")
        device.pull(pull_src, pull_dst)

        logger.debug("Got xml dump from phone")
    except Exception:
        logger.exception("Error while getting dump from phone: ")