from ppadb.client import Client as AdbClient  # type: ignore
from time import sleep, perf_counter
import logging
from pathlib import Path
import re
import os
import subprocess

from utils.setup_logging import setup_logging

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../snapbot
XML_DIR = PROJECT_ROOT / "xml"
XML_DIR.mkdir(parents=True, exist_ok=True)

setup_logging()
logger = logging.getLogger(__name__)

class AdbAccessError(RuntimeError):
    pass


def check_adb_access():
    """Bounded CLI check: online, authorized, and able to run a shell command."""
    def run(args):
        try:
            result = subprocess.run(["adb", *args], capture_output=True, text=True, timeout=10)
        except FileNotFoundError as exc:
            raise AdbAccessError("ADB is niet geïnstalleerd of staat niet in PATH.") from exc
        except subprocess.TimeoutExpired as exc:
            raise AdbAccessError("ADB reageert niet binnen 10 seconden. Controleer de verbinding.") from exc
        if result.returncode:
            raise AdbAccessError("ADB-toegang mislukt. Controleer USB-debugging en de verbinding.")
        return result.stdout

    output = run(["devices", "-l"])
    entries = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] != "List" and not line.startswith("*"):
            entries[parts[0]] = parts[1]
    serial = os.getenv("ANDROID_SERIAL")
    if serial:
        if serial not in entries:
            raise AdbAccessError("De telefoon uit ANDROID_SERIAL is niet aangesloten.")
    else:
        if not entries:
            raise AdbAccessError("Geen telefoon gedetecteerd. Sluit de telefoon aan en schakel USB-debugging in.")
        if len(entries) != 1:
            raise AdbAccessError("Meerdere ADB-apparaten gevonden. Stel ANDROID_SERIAL in voor de juiste telefoon.")
        serial = next(iter(entries))
    status = entries[serial]
    if status == "unauthorized":
        raise AdbAccessError("Geen ADB-toestemming. Ontgrendel de telefoon en accepteer ‘USB-debugging toestaan’.")
    if status != "device":
        raise AdbAccessError("De telefoon is offline of niet beschikbaar via ADB. Controleer de USB-verbinding.")
    if run(["-s", serial, "shell", "echo", "SNAPBOT_ADB_OK"]).strip() != "SNAPBOT_ADB_OK":
        raise AdbAccessError("Telefoon gevonden, maar ADB-shelltoegang werkt niet.")
    return serial


def adbConnection():
    serial = check_adb_access()
    adb = AdbClient(host="127.0.0.1", port=5037)
    device = adb.device(serial)
    if device is None:
        raise AdbAccessError("De telefoon is na de ADB-controle niet meer beschikbaar.")
    return device


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
