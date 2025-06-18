from ppadb.client import Client as AdbClient
from time import sleep
import logging
from utils.setup_logging import setLog

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
            device.shell("input swipe 550 2100 550 500")
            device.shell("su -c \"am force-stop com.snapchat.android\"")
            sleep(2)
            device.shell("su -c \"pm disable com.snapchat.android\"")
            sleep(3)
            device.shell("su -c \"pm enable com.snapchat.android\"")
            sleep(1)
            device.shell("monkey -p com.snapchat.android -c android.intent.category.LAUNCHER 1")
            logger.debug("Succesfuly opened snap")
        except Exception:
            logger.exception("Error while starting snap: ")    

def rebootSnap(device):
        try:
            device.shell("su\"am force-stop com.snapchat.android\"")
            sleep(2)
            device.shell("su -c \"pm disable com.snapchat.android\"")
            sleep(3)
            device.shell("su -c \"pm enable com.snapchat.android\"")
            sleep(1)
            device.shell("monkey -p com.snapchat.android -c android.intent.category.LAUNCHER 1")
            logger.debug("Succesfuly opened snap")
        except Exception:
            logger.exception("Error while starting snap: ")  

def getDump(device, phase):
    try:
        dumpstring = "uiautomator dump /sdcard/{0}.xml".format(phase)
        device.shell(dumpstring)
        pullstring1, pullstring2 = "/sdcard/{0}.xml".format(phase), "xml/{0}.xml".format(phase)
        device.pull(pullstring1, pullstring2)
        logger.debug("Got xml dump from phone")
    except Exception:
        logger.exception("Error while getting dump from phone: ")