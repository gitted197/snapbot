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
CAMERA_CAPTURE_BUTTON_ID = "com.snapchat.android:id/camera_capture_button"
CLICK_MAX_RETRIES = 25
CLICK_RETRY_SLEEP_SECONDS = 0.20

def randomBetween(n1, n2):
    highest = max(n1, n2)
    lowest = min(n1, n2)
    logger.debug("Returned bounds %s, %s", highest, lowest)
    return randint(lowest, highest)

def _parseBounds(bounds: str):
    m = _BOUNDS_RE.search(bounds.strip())
    if not m:
        raise ValueError(f"Invalid bounds string: {bounds!r}")
    return tuple(map(int, m.groups()))

def randomCoordinatesFromBounds(bounds: str):
    x1, y1, x2, y2 = _parseBounds(bounds)
    return [randomBetween(x1, x2), randomBetween(y1, y2)]

def randomCoordinatesFromBoundsInset(bounds: str, inset_ratio: float = 0.30):
    if not 0 <= inset_ratio < 0.5:
        raise ValueError("inset_ratio must be >= 0 and < 0.5")

    x1, y1, x2, y2 = _parseBounds(bounds)
    width = x2 - x1
    height = y2 - y1

    inset_x = int(width * inset_ratio)
    inset_y = int(height * inset_ratio)

    safe_x1 = x1 + inset_x
    safe_x2 = x2 - inset_x
    safe_y1 = y1 + inset_y
    safe_y2 = y2 - inset_y

    return [randomBetween(safe_x1, safe_x2), randomBetween(safe_y1, safe_y2)]

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
        while retryCounter < CLICK_MAX_RETRIES:
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

                if resourceId == CAMERA_CAPTURE_BUTTON_ID:
                    x, y = randomCoordinatesFromBoundsInset(node.attrib["bounds"], inset_ratio=0.30)
                else:
                    x, y = randomCoordinatesFromBounds(node.attrib["bounds"])
                logger.info("Clicking on %s, %s", x, y)
                device.shell(f"input touchscreen tap {x} {y}")
                return
            except Exception as e:
                retryCounter += 1
                logger.warning(
                    "Error while clicking (%s/%s): %s",
                    retryCounter,
                    CLICK_MAX_RETRIES,
                    e,
                )
                sleep(CLICK_RETRY_SLEEP_SECONDS)

        raise RuntimeError(f"Tried too many times ({CLICK_MAX_RETRIES})")

class ClickButton:
    def __init__(self, phase, device):
        self.phase = phase
        self.device = device
        self.xmlpath = str(XML_DIR / f"{phase}.xml")

    def ClickNow(self, node, username):
        current = CurrentDump()
        current.clickButtonRandomized(self.device, node, username, self.phase, self.xmlpath)
