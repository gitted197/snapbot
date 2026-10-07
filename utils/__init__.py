from ppadb.client import Client as AdbClient  # type: ignore
from time import sleep, perf_counter
import logging
from pathlib import Path
import re

from utils.setup_logging import setup_logging

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../snapbot
XML_DIR = PROJECT_ROOT / "xml"
XML_DIR.mkdir(parents=True, exist_ok=True)

setup_logging()
logger = logging.getLogger(__name__)

def adbConnection():
    adb = AdbClient(host="127.0.0.1", port=5037)
    logger.debug("Set AdbClient")

    devices = adb.devices()
    logger.debug("Listed adb devices")

    if not devices:
        raise RuntimeError("No adb devices connected")
    return devices[0]

def checkInt(points_input):
    try:
        return int(points_input)
    except ValueError as e:
        raise ValueError("Please enter a number.") from e

def startSnap(device):
    try:
        device.shell("input keyevent KEYCODE_WAKEUP")
        device.shell("am force-stop com.snapchat.android")
        sleep(1)
        device.shell("monkey -p com.snapchat.android -c android.intent.category.LAUNCHER 1")
        sleep(1)
        logger.debug("Succesfuly opened snap")
    except Exception:
        logger.exception("Error while starting snap:")

def rebootSnap(device):
    try:
        device.shell("am force-stop com.snapchat.android")
        sleep(1)
        device.shell("monkey -p com.snapchat.android -c android.intent.category.LAUNCHER 1")
        sleep(1)
        logger.debug("Succesfuly opened snap")
    except Exception:
        logger.exception("Error while rebooting snap:")

def getDump(device, phase):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", phase):
        raise ValueError("Invalid XML dump phase")
    started = perf_counter()
    remote = f"/sdcard/{phase}.xml"
    local = XML_DIR / f"{phase}.xml"
    # Invalidate both copies before acquisition; failed dumps cannot reuse XML.
    local.unlink(missing_ok=True)
    try:
        output = device.shell(f"rm -f {remote} && uiautomator dump {remote}")
        if "dumped to:" not in str(output).lower():
            raise RuntimeError(f"uiautomator did not confirm a new dump: {output}")
        result = device.pull(remote, str(local))
        if result is False or not local.is_file() or local.stat().st_size == 0:
            raise RuntimeError("XML dump transfer failed")
        logger.debug("XML dump %s took %.3fs", phase, perf_counter() - started)
    except Exception as exc:
        local.unlink(missing_ok=True)
        raise RuntimeError(f"Could not acquire fresh XML dump for {phase}") from exc
