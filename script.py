import sys
from utils import adbConnection, startSnap, rebootSnap
from utils.clicking import ClickButton
from time import sleep
from utils.clicking import ClickButton
import logging
from utils.setup_logging import setLog
import subprocess

logger = logging.getLogger(__name__)
logger = setLog(logger)

def mainScript(sys1, sys2):
    #Username to variable
    try:
        username_input = sys1
        logger.debug("Function mainScript received: " + username_input)
    except Exception:
        logger.exception("Error while setting username in mainScript:")

    #Points to variable
    while True:
        try:
            points_input = int(sys2)
            logger.debug("Set points to int in mainScript function")
            break
        except Exception:
            logger.exception("Error while setting points to int in mainScript:")
            continue
    
    #Start ADB
    try:
        subprocess.run(['adb', 'devices'])
    except Exception:
        logger.exception("Failed to start adb daemon")
            
    #Connecting to phone
    try:
        device = adbConnection()
        logger.debug(device)
        logger.debug("Set adbConnection")
    except Exception:
        logger.exception("Error while setting up adbConnection: ")

    #Unlocking phone, starting Snap
    try:
        startSnap(device)
        logger.info("Opened snap, start sending pictures")
    except Exception:
        logger.exception("Error while starting Snapchat: ")

    global pointscounter
    pointscounter = 0
    try:
        while pointscounter < points_input:
            # try:
            #     if pointscounter % 5 == 0:
            #         logger.debug("Pointscounter dividable by 5. Restarting Snap")
            #         rebootSnap(device)
            #         pointsstr = str(pointscounter)
            #         logger.info("Rebooted Snap. Counter: " + pointsstr)
                
                #Setting phase, to then find the bounds for that phase and clicking them on a random location
                phase = "clicking_camera"
                click = ClickButton(phase, device)
                click.ClickNow("com.snapchat.android:id/camera_capture_button", None)
                logger.debug("Clicked camera button, now sleeping, then looking for send to")
                sleep(1)

                phase = "clicking_next"
                click = ClickButton(phase, device)
                click.ClickNow("com.snapchat.android:id/send_btn", None)
                logger.debug("In user menu. Finding and clicking " + username_input + " now.")
                sleep(0.25)

                phase = "clicking_user"
                click = ClickButton(phase, device)
                click.ClickNow("com.snapchat.android:id/send_to_user", username_input)
                logger.debug("Clicked " + username_input + " . Now clicking send.")
                sleep(2)

                phase = "clicking_send"
                click = ClickButton(phase, device)
                click.ClickNow("com.snapchat.android:id/send_to_send_button", None)
                logger.debug("Clicked send. Going back to camera.")
                sleep(0.25)

                phase = "back_to_camera"
                click = ClickButton(phase, device)
                click.ClickNow("com.snapchat.android:id/ngs_camera_icon_container", None)
                logger.debug("Clicked back to camera. Starting next cycle.")

                pointscounter += 1 
                logger.debug("Sent " + str(pointscounter) + " picture(s)")
    except RuntimeError:
        logger.debug("Too many clicking errors. Now rebooting snap.")
        rebootSnap(device)
    #except Exception as e:
        #logger.exception("Error while in sending snaps loop: " + str(e))
    #logger.info("Done sending " + str(points_input) + " snaps!")
    #exit

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Not enough arguments on command line")
        exit
    elif len(sys.argv) > 3:
        print("Too many arguments on command line")    
    else:
        mainScript(sys.argv[1], sys.argv[2])