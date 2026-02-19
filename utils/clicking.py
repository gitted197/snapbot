import re
from random import randint
import xml.etree.ElementTree as ET
from time import sleep
import logging

from utils import getDump
from utils.setup_logging import setup_logging
from utils import XML_DIR

setup_logging()
logger = logging.getLogger(__name__)

_BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")

def randomBetween(n1, n2):
    highest = max(n1, n2)
    lowest = min(n1, n2)
    logger.debug("Returned bounds %s, %s", highest, lowest)
    return randint(lowest, highest)

def randomCoordinatesFromBounds(bounds: str):
    m = _BOUNDS_RE.search(bounds.strip())
    if not m:
        raise ValueError(f"Invalid bounds string: {bounds!r}")
    x1, y1, x2, y2 = map(int, m.groups())
    return [randomBetween(x1, x2), randomBetween(y1, y2)]

class CurrentDump:
    def __init__(self):
        self.tree = None

    def getNode(self, resourceId, username_input):
        if username_input is not None:
            xpath = './/node[@text="{user}"]'.format(user=username_input)
            return self.tree.find(xpath)
        xpath = './/node[@resource-id="{id}"]'.format(id=resourceId)
        return self.tree.find(xpath)

    def getSnapNode(self, resourceId):
        xpath = './/node[@content-desc="{id}"]'.format(id=resourceId)
        return self.tree.find(xpath)

    def clickButtonRandomized(self, device, resourceId, username_input, phase, xmlpath):
        retryCounter = 0
        while retryCounter < 5:
            try:
                getDump(device, phase)
            except Exception:
                logger.exception("Error while getting XML dump:")

            self.tree = ET.parse(xmlpath)

            node = self.getNode(resourceId, username_input) if resourceId != "Snapcode button" else self.getSnapNode(resourceId)

            try:
                if node is None:
                    raise RuntimeError(resourceId + " not found")
                if "bounds" not in node.attrib:
                    raise RuntimeError("Bounds not found")

                x, y = randomCoordinatesFromBounds(node.attrib["bounds"])
                logger.info("Clicking on %s, %s", x, y)
                device.shell(f"input touchscreen tap {x} {y}")
                return
            except Exception as e:
                retryCounter += 1
                logger.warning("Error while clicking (%s/5): %s", retryCounter, e)
                sleep(3)

        raise RuntimeError("Tried too many times")

class ClickButton:
    def __init__(self, phase, device):
        self.phase = phase
        self.device = device
        self.xmlpath = str(XML_DIR / f"{phase}.xml")

    def ClickNow(self, node, username):
        current = CurrentDump()
        current.clickButtonRandomized(self.device, node, username, self.phase, self.xmlpath)
