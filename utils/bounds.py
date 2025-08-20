import re
from random import randint
import xml.etree.ElementTree as ET
from time import sleep
from utils import getDump
import logging
from utils.setup_logging import setLog

logger = logging.getLogger(__name__)
logger = setLog(logger)

# Helper function to get random number between 2 numbers
def randomBetween(n1, n2):
    highest = max(n1, n2)
    lowest = min(n1, n2)
    return randint(lowest, highest);

# Helper function to extract a string like: "[956,662][1044,750]" to
# random coordinates that are within these bounds [939,851]
def randomCoordinatesFromBounds(bounds):
    matches = re.search('\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
    return [
        randomBetween(int(matches[1]), int(matches[3])),
        randomBetween(int(matches[2]), int(matches[4])),
    ]

class CurrentDump:
    # Initialize current XML tree
    def __init__(self, xmlpath):
        self.tree = ET.parse(xmlpath)

    def getNode(self, resourceId, username_input):
            if username_input != None:
                xpath = './/node[@text="{user}"]'.format(user=username_input)
                return self.tree.find(xpath)
            else:
                xpath = './/node[@resource-id="{id}"]'.format(id=resourceId)
                return self.tree.find(xpath)

    # Click a button randomized on bounds.
    # Resource id must be full including namespace 
    def clickButtonRandomized(self, device, resourceId, username_input, phase, xmlpath):

        retryCounter = 0
        while retryCounter < 10:
            getDump(device, phase)
            self.tree = ET.parse(xmlpath)
            node = self.getNode(resourceId, username_input)
            try:
                if node is None:
                    raise Exception(resourceId + " not found")

                if "bounds" not in node.attrib:
                    raise Exception("Bounds not found")
                
                if resourceId == "com.snapchat.android:id/send_btn_layout":
                    x, y = randomCoordinatesFromBounds("[850,2180][1046,2278]")
                elif resourceId == "com.snapchat.android:id/ngs_camera_icon_container":
                    x, y = randomCoordinatesFromBounds("[432,2164][647,2164]")
                else:
                    x, y = randomCoordinatesFromBounds(node.attrib["bounds"])
                print("Clicking on", x, y)
                device.shell(f"input touchscreen tap {x} {y}")
                break
            except Exception as e:
                print(str(e))
                retryCounter += 1
                sleep(0.5)
                if retryCounter == 10:
                    print("Tried to find the button 5 times. Script is stopping now.")
                    exit()
                continue



    # retryCounter = 0
    # while retryCounter < 5:
    #     current = CurrentDump("xml/snap_open.xml")
    #     node = current.getNode("com.snapchat.android:id/camera_mode_dropdown")
    #     if (node is None):
    #         retryCounter += retryCounter + 1
    #         sleep(1)
    #         continue
    #     # Do yo thang honey




