import sys
import subprocess
from time import sleep
import logging

from utils import adbConnection, startSnap, rebootSnap
from utils.clicking import ClickButton
from utils.setup_logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

def mainScript(username_input: str, points_input_raw) -> int:
    logger.debug("Function mainScript received username=%s", username_input)

    try:
        points_input = int(points_input_raw)
    except Exception as e:
        logger.exception("Error while parsing points to int")
        raise ValueError("Points must be an integer") from e

    # Start ADB daemon (best-effort)
    try:
        subprocess.run(["adb", "devices"], check=False)
    except Exception:
        logger.info("Could not start adb daemon")

    # Connecting to phone
    device = adbConnection()
    logger.debug("Connected to adb device")

    # Unlocking phone, starting Snap
    startSnap(device)
    logger.info("Opened snap, start sending pictures")

    pointscounter = 0

    try:
        while pointscounter < points_input:
            if pointscounter % 10 == 0 and pointscounter != 0:
                rebootSnap(device)
                logger.info("Rebooted Snap. Counter: %s", pointscounter)

            # clicking steps
            ClickButton("clicking_camera", device).ClickNow("com.snapchat.android:id/camera_capture_button", None)
            sleep(1)

            ClickButton("clicking_next", device).ClickNow("com.snapchat.android:id/send_btn", None)
            sleep(0.25)

            ClickButton("clicking_user", device).ClickNow("com.snapchat.android:id/send_to_user", username_input)
            sleep(0.25)

            ClickButton("clicking_send", device).ClickNow("com.snapchat.android:id/send_to_send_button", None)
            sleep(0.25)

            ClickButton("back_to_camera", device).ClickNow("com.snapchat.android:id/ngs_camera_icon_container", None)

            pointscounter += 1
            
            # Keep a counter after each successful send
            logger.debug("Sent %s picture(s)", pointscounter)

            # Every 5 snaps, log progress at INFO level
            if pointscounter % 1 == 0:
                logger.info("Progress: %s/%s snaps sent", pointscounter, points_input)
            logger.debug("Sent %s picture(s)", pointscounter)

    except RuntimeError:
        rebootSnap(device)
        logger.debug("Too many clicking errors. Now rebooting snap.")
    except Exception:
        logger.exception("Error while in sending snaps loop")
        raise

    logger.info("Done sending %s snaps!", points_input)
    return pointscounter

def main(argv) -> int:
    if len(argv) != 3:
        print("Usage: python script.py <username> <points>")
        return 2
    mainScript(argv[1], argv[2])
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
