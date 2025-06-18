import re
from random import randint
import xml.etree.ElementTree as ET
from time import sleep
from utils import getDump, rebootSnap
import logging
from utils.setup_logging import setLog

logger = logging.getLogger(__name__)

# Helper function to get random number between 2 numbers
def randomBetween(n1, n2):
    try:
        highest = max(n1, n2)
    except Exception:
        logger.exception("Error while setting random bound x")
    try:
        lowest = min(n1, n2)
    except Exception:
        logger.exception("Error while setting random bound y")
    logger.debug("Returned bounds " + str(highest) + ", " + str(lowest))
    return randint(lowest, highest);

# Helper function to extract a string like: "[956,662][1044,750]" to
# random coordinates that are within these bounds [939,851]
def randomCoordinatesFromBounds(bounds):
    try:
        matches = re.search('\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
        logger.debug("Found bounds in XML")
    except Exception:
        logger.exception("Error while finding bounds in XML")
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

    def getSnapNode(self, resourceId):
                xpath = './/node[@content-desc="{id}"]'.format(id=resourceId)
                return self.tree.find(xpath)

    # Click a button randomized on bounds.
    # Resource id must be full including namespace 
    def clickButtonRandomized(self, device, resourceId, username_input, phase, xmlpath):

        retryCounter = 0
        while retryCounter < 5:
            try:
                getDump(device, phase)
            except Exception:
                logger.exception("Error while getting XML dump: ")
            self.tree = ET.parse(xmlpath)
            if resourceId != "Snapcode button":
                try:
                    node = self.getNode(resourceId, username_input)
                except Exception:
                    logger.exception("Error getting node from XML: ")
            else:
                node = self.getSnapNode(resourceId)

            try:
                if node is None:
                    raise Exception(resourceId + " not found")

                if "bounds" not in node.attrib:
                    raise Exception("Bounds not found")
                
                #if resourceId == "com.snapchat.android:id/ngs_camera_icon_container":
                #    x, y = randomCoordinatesFromBounds("[432,2164][647,2164]")
                #if resourceId == "com.snapchat.android:id/send_to_send_button":
                #    x, y = randomCoordinatesFromBounds("[947,2154][1056,2160]")
                #else:
                #    x, y = randomCoordinatesFromBounds(node.attrib["bounds"])
                x, y = randomCoordinatesFromBounds(node.attrib["bounds"])
                logger.info("Clicking on " + str(x) + ", " + str(y))
                device.shell(f"input touchscreen tap {x} {y}")
                break
            except Exception as e:
                logger.warning("Error while clicking. Could be while getting XML, bounds, random x/y, etc.")
                print(str(e))
                retryCounter += 1
                sleep(3)
                if retryCounter == 4:
                    logger.error("Tried to find the button 5 times. Script is stopping now.")
                    raise RuntimeError("Tried too many times")

class ClickButton:
    def __init__(self, phase, device):
        self.phase = phase
        self.xmlpath = 'xml/' + phase + '.xml'
        self.device = device

    def ClickNow(self, node, username):
        self.node = node
        self.username = username
        current = CurrentDump(self.xmlpath)
        current.clickButtonRandomized(self.device, self.node, self.username, self.phase, self.xmlpath)