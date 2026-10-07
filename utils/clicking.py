import re
from random import randint
import xml.etree.ElementTree as ET
from time import sleep, perf_counter
import logging

from utils import getDump
from utils.setup_logging import setup_logging
from utils import XML_DIR

setup_logging()
logger = logging.getLogger(__name__)

_BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
CAMERA_CAPTURE_BUTTON_ID = "com.snapchat.android:id/camera_capture_button"
CLICK_TIMEOUT_SECONDS = 10.0
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
        # Iterate instead of interpolating names into XPath (quotes are valid).
        matches = [node for node in self.tree.iter("node")
                   if node.get("resource-id") == resourceId
                   and (username_input is None or node.get("text") == username_input)]
        if len(matches) > 1:
            raise RuntimeError(f"Ambiguous selector: {resourceId!r}, {username_input!r}")
        return matches[0] if matches else None

    def getSnapNode(self, resourceId):
        xpath = './/node[@content-desc="{id}"]'.format(id=resourceId)
        return self.tree.find(xpath)

    def clickButtonRandomized(self, device, resourceId, username_input, phase, xmlpath, tree=None, guard=None):
        started = perf_counter()
        deadline = started + CLICK_TIMEOUT_SECONDS
        attempts = 0
        last_error = None
        while True:
            attempts += 1
            try:
                if tree is None:
                    getDump(device, phase)
                    self.tree = ET.parse(xmlpath)
                else:
                    # Only reuse the immediately preceding verified screen.
                    self.tree = tree
                node = (self.getSnapNode(resourceId) if resourceId == "Snapcode button"
                        else self.getNode(resourceId, username_input))
                if node is None or node.get("enabled", "true") != "true":
                    raise RuntimeError(f"{resourceId} not ready")
                bounds = node.get("bounds", "")
                x1, y1, x2, y2 = _parseBounds(bounds)
                if x2 <= x1 or y2 <= y1:
                    raise RuntimeError(f"{resourceId} has empty bounds")
                x, y = randomCoordinatesFromBoundsInset(bounds, inset_ratio=0.30)
            except Exception as exc:
                last_error = exc
                tree = None
                if perf_counter() >= deadline:
                    raise RuntimeError(f"Timed out waiting for {resourceId}: {last_error}") from exc
                logger.debug("Waiting for %s: %s", resourceId, exc)
                sleep(CLICK_RETRY_SLEEP_SECONDS)
                continue

            if guard is not None and not guard(self.tree):
                raise RuntimeError(f"Precondition no longer holds for {resourceId}")
            # A shell failure might happen after Android receives the tap.
            # Never repeat an uncertain tap in this polling loop.
            ready_seconds = perf_counter() - started
            logger.info("Clicking %s on %s, %s (ready %.3fs, dumps/polls %s)",
                        resourceId, x, y, ready_seconds, attempts)
            tap_started = perf_counter()
            try:
                device.shell(f"input touchscreen tap {x} {y}")
            except Exception as exc:
                raise RuntimeError(f"Tap outcome uncertain for {resourceId}") from exc
            logger.debug("Tap %s took %.3fs", resourceId, perf_counter() - tap_started)
            return

class ClickButton:
    def __init__(self, phase, device):
        self.phase = phase
        self.device = device
        self.xmlpath = str(XML_DIR / f"{phase}.xml")

    def ClickNow(self, node, username, tree=None, guard=None):
        current = CurrentDump()
        current.clickButtonRandomized(self.device, node, username, self.phase, self.xmlpath, tree=tree, guard=guard)
