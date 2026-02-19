import re
from random import randint
import xml.etree.ElementTree as ET
from time import sleep
import logging

from utils import getDump
from utils.setup_logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

_BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")

def randomBetween(n1, n2):
    highest = max(n1, n2)
    lowest = min(n1, n2)
    return randint(lowest, highest)

def randomCoordinatesFromBounds(bounds: str):
    m = _BOUNDS_RE.search(bounds.strip())
    if not m:
        raise ValueError(f"Invalid bounds string: {bounds!r}")
    x1, y1, x2, y2 = map(int, m.groups())
    return [randomBetween(x1, x2), randomBetween(y1, y2)]

class CurrentDump:
    def __init__(self, xmlpath):
        self.tree = ET.parse(xmlpath)

    def getNode(self, resourceId, username_input):
        if username_input is not None:
            xpath = './/node[@text="{user}"]'.format(user=username_input)
            return self.tree.find(xpath)
        xpath = './/node[@resource-id="{id}"]'.format(id=resourceId)
        return self.tree.find(xpath)

    def clickButtonRandomized(self, device, resourceId, username_input, phase, xmlpath):
        retryCounter = 0
        while retryCounter < 10:
            getDump(device, phase)
            self.tree = ET.parse(xmlpath)
            node = self.getNode(resourceId, username_input)
            try:
                if node is None:
                    raise RuntimeError(resourceId + " not found")
                if "bounds" not in node.attrib:
                    raise RuntimeError("Bounds not found")

                if resourceId == "com.snapchat.android:id/send_btn_layout":
                    x, y = randomCoordinatesFromBounds("[850,2180][1046,2278]")
                elif resourceId == "com.snapchat.android:id/ngs_camera_icon_container":
                    x, y = randomCoordinatesFromBounds("[432,2164][647,2164]")
                else:
                    x, y = randomCoordinatesFromBounds(node.attrib["bounds"])

                logger.info("Clicking on %s, %s", x, y)
                device.shell(f"input touchscreen tap {x} {y}")
                return
            except Exception as e:
                logger.warning("Click retry (%s/10): %s", retryCounter + 1, e)
                retryCounter += 1
                sleep(0.5)

        raise RuntimeError("Tried to find the button 10 times. Script is stopping now.")
