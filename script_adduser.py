import sys
from utils import adbConnection, checkInt, startSnap
from utils.clicking import ClickButton
from time import sleep
from utils.clicking import ClickButton
import logging
from utils.setup_logging import setLog
from utils.snapcode import get_snapcode

logger = logging.getLogger(__name__)
logger = setLog(logger)

def mainScriptAddSnap(sys1):
    #Username to variable
    try:
        username_input = sys1
        print(username_input)
        logger.debug("Function mainScriptAddScript received: " + username_input)
    except Exception:
        logger.exception("Error while setting username in mainScriptAddSnap:")


    #Connecting to phone
    try:
        device = adbConnection()
        logger.debug("Set adbConnection")
    except Exception:
        logger.exception("Error while setting up adbConnection: ")

    #Unlocking phone, starting Snap
    try:
        startSnap(device)
        logger.info("Opened snap, generating and clicking URL to add friend")
    except Exception:
        logger.exception("Error while starting Snapchat: ")

    try:    
        device.shell(f"am start -a \"android.intent.action.VIEW\" -d \"https://snapchat.com/add/{username_input}\"")
        logger.info("Started add friend intent with URL"
        )
        phase = "clicking_confirm_add"
        click = ClickButton(phase, device)
        click.ClickNow("com.snapchat.android:id/scan_add_friend_card_button_add_friend", None)
        logger.debug("Clicked confirm add friend")
        sleep(1)

        device.shell("su -c \"am force-stop com.snapchat.android\"")
        logger.debug("Force closed snap after adding friend")

    except Exception:
        logger.exception("Error while adding user to Snapchat: ")
    logger.info("Done adding " + username_input + " to Snapchat account!")
    exit

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Not enough arguments on command line")
        exit
    elif len(sys.argv) > 2:
        print("Too many arguments on command line")    
    else:
        mainScriptAddSnap(sys.argv[1])