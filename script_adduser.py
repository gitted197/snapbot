import sys
from time import sleep
import logging

from utils import adbConnection, startSnap
from utils.clicking import ClickButton
from utils.setup_logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

def mainScriptAddSnap(username_input: str) -> int:
    logger.debug("Function mainScriptAddSnap received username=%s", username_input)

    device = adbConnection()
    logger.debug("Connected to adb device")

    startSnap(device)
    logger.info("Opened snap, generating and clicking URL to add friend")

    try:
        device.shell(
            f'am start -a "android.intent.action.VIEW" -d "https://snapchat.com/add/{username_input}"'
        )
        logger.info("Started add friend intent with URL")

        ClickButton("clicking_confirm_add", device).ClickNow(
            "com.snapchat.android:id/scan_add_friend_card_button_add_friend", None
        )
        logger.debug("Clicked confirm add friend")
        sleep(1)

        device.shell('su -c "am force-stop com.snapchat.android"')
        logger.debug("Force closed snap after adding friend")
    except Exception:
        logger.exception("Error while adding user to Snapchat")
        return 1

    logger.info("Done adding %s to Snapchat account!", username_input)
    return 0

def main(argv) -> int:
    if len(argv) != 2:
        print("Usage: python script_adduser.py <username>")
        return 2
    return mainScriptAddSnap(argv[1])

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
