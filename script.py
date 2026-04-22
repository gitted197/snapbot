import sys
import subprocess
import xml.etree.ElementTree as ET
from time import sleep, perf_counter
import logging

from utils import adbConnection, startSnap, rebootSnap, getDump, XML_DIR
from utils.clicking import ClickButton
from utils.setup_logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

CAMERA_CAPTURE_BUTTON_ID = "com.snapchat.android:id/camera_capture_button"
NEXT_BUTTON_ID = "com.snapchat.android:id/send_btn"
USER_ROW_ID = "com.snapchat.android:id/send_to_user"
SEND_BUTTON_ID = "com.snapchat.android:id/send_to_send_button"
BACK_TO_CAMERA_BUTTON_ID = "com.snapchat.android:id/ngs_camera_icon_container"

STEP_CAMERA = "camera"
STEP_NEXT = "next"
STEP_USER = "user"
STEP_SEND = "send"
STEP_BACK = "back"
STEP_DONE = "done"
SCREEN_DUMP_PHASE = "flow_recovery"
MAX_FLOW_ACTIONS = 20

STEP_PHASE = {
    STEP_CAMERA: "clicking_camera",
    STEP_NEXT: "clicking_next",
    STEP_USER: "clicking_user",
    STEP_SEND: "clicking_send",
    STEP_BACK: "back_to_camera",
}

STEP_RESOURCE_ID = {
    STEP_CAMERA: CAMERA_CAPTURE_BUTTON_ID,
    STEP_NEXT: NEXT_BUTTON_ID,
    STEP_USER: USER_ROW_ID,
    STEP_SEND: SEND_BUTTON_ID,
    STEP_BACK: BACK_TO_CAMERA_BUTTON_ID,
}

NEXT_STEP = {
    STEP_CAMERA: STEP_NEXT,
    STEP_NEXT: STEP_USER,
    STEP_USER: STEP_SEND,
    STEP_SEND: STEP_BACK,
    STEP_BACK: STEP_DONE,
}


def formatDuration(seconds: float) -> str:
    seconds_int = int(round(seconds))
    minutes, seconds = divmod(seconds_int, 60)
    hours, minutes = divmod(minutes, 60)

    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _node_by_resource(tree: ET.ElementTree, resource_id: str):
    return tree.find(f'.//node[@resource-id="{resource_id}"]')


def _node_by_text(tree: ET.ElementTree, text: str):
    return tree.find(f'.//node[@text="{text}"]')


def _dump_current_tree(device) -> ET.ElementTree | None:
    try:
        getDump(device, SCREEN_DUMP_PHASE)
        return ET.parse(str(XML_DIR / f"{SCREEN_DUMP_PHASE}.xml"))
    except Exception:
        logger.exception("Could not dump current screen for flow recovery")
        return None


def detect_visible_steps(device, username_input: str) -> set[str]:
    tree = _dump_current_tree(device)
    if tree is None:
        return set()

    visible: set[str] = set()

    if _node_by_resource(tree, CAMERA_CAPTURE_BUTTON_ID) is not None:
        visible.add(STEP_CAMERA)
    if _node_by_resource(tree, NEXT_BUTTON_ID) is not None:
        visible.add(STEP_NEXT)
    if username_input and _node_by_text(tree, username_input) is not None:
        visible.add(STEP_USER)
    elif _node_by_resource(tree, USER_ROW_ID) is not None:
        visible.add(STEP_USER)
    if _node_by_resource(tree, SEND_BUTTON_ID) is not None:
        visible.add(STEP_SEND)
    if _node_by_resource(tree, BACK_TO_CAMERA_BUTTON_ID) is not None:
        visible.add(STEP_BACK)

    return visible


def _first_visible(visible: set[str], *steps: str) -> str | None:
    for step in steps:
        if step in visible:
            return step
    return None


def choose_recovery_step(failed_step: str, visible: set[str]) -> str | None:
    """Pick the best next action based on the current visible screen."""
    if failed_step == STEP_CAMERA:
        return _first_visible(visible, STEP_NEXT, STEP_USER, STEP_SEND, STEP_BACK, STEP_CAMERA)

    if failed_step == STEP_NEXT:
        return _first_visible(visible, STEP_USER, STEP_SEND, STEP_BACK, STEP_CAMERA, STEP_NEXT)

    if failed_step == STEP_USER:
        return _first_visible(visible, STEP_SEND, STEP_BACK, STEP_CAMERA, STEP_NEXT, STEP_USER)

    if failed_step == STEP_SEND:
        if STEP_CAMERA in visible:
            return STEP_DONE
        return _first_visible(visible, STEP_BACK, STEP_SEND, STEP_USER, STEP_NEXT, STEP_CAMERA)

    if failed_step == STEP_BACK:
        if STEP_CAMERA in visible:
            return STEP_DONE
        return _first_visible(visible, STEP_BACK, STEP_SEND, STEP_USER, STEP_NEXT, STEP_CAMERA)

    return None


def click_step(device, step: str, username_input: str) -> None:
    phase = STEP_PHASE[step]
    resource_id = STEP_RESOURCE_ID[step]

    if step == STEP_USER:
        ClickButton(phase, device).ClickNow(resource_id, username_input)
    else:
        ClickButton(phase, device).ClickNow(resource_id, None)


def recover_after_failed_step(
    device,
    failed_step: str,
    username_input: str,
    reboot_used: bool,
) -> tuple[str, bool]:
    visible = detect_visible_steps(device, username_input)
    logger.warning(
        "Step %s failed. Visible recovery steps: %s",
        failed_step,
        ", ".join(sorted(visible)) if visible else "none",
    )

    recovery_step = choose_recovery_step(failed_step, visible)
    if recovery_step is not None:
        return recovery_step, reboot_used

    if reboot_used:
        raise RuntimeError(
            f"Could not recover after {failed_step}; Snapchat was already rebooted once for this snap."
        )

    logger.warning("No known screen detected after %s failed; rebooting Snapchat once.", failed_step)
    rebootSnap(device)
    return STEP_CAMERA, True


def send_one_snap(device, username_input: str) -> None:
    step = STEP_CAMERA
    reboot_used = False

    for _ in range(MAX_FLOW_ACTIONS):
        if step == STEP_DONE:
            return

        try:
            click_step(device, step, username_input)

            if step == STEP_CAMERA:
                sleep(1)
            elif step in {STEP_NEXT, STEP_USER, STEP_SEND}:
                sleep(0.25)

            step = NEXT_STEP[step]

        except RuntimeError:
            step, reboot_used = recover_after_failed_step(
                device=device,
                failed_step=step,
                username_input=username_input,
                reboot_used=reboot_used,
            )

    raise RuntimeError("Flow recovery exceeded maximum actions for one snap")


def mainScript(username_input: str, points_input_raw) -> tuple[int, float]:
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

    wait_profile = ScreenWaitProfile.load()
    logger.info("Loaded screen wait profile: %s", wait_profile.describe())

    # Unlocking phone, starting Snap
    startSnap(device)
    logger.info("Opened snap, start sending pictures")

    pointscounter = 0
    send_started = perf_counter()

    try:
        while pointscounter < points_input:
            if pointscounter % 10 == 0 and pointscounter != 0:
                rebootSnap(device)
                logger.info("Scheduled Snapchat reboot. Counter: %s", pointscounter)

            send_one_snap(device, username_input)
            pointscounter += 1

            logger.info("Progress: %s/%s snaps sent", pointscounter, points_input)

    except Exception:
        logger.exception(
            "Error while in sending snaps loop after %s/%s snaps",
            pointscounter,
            points_input,
        )
        raise

    elapsed_seconds = perf_counter() - send_started
    logger.info(
        "Done sending %s/%s snaps in %s!",
        pointscounter,
        points_input,
        formatDuration(elapsed_seconds),
    )
    return pointscounter, elapsed_seconds



def main(argv) -> int:
    if len(argv) != 3:
        print("Usage: python script.py <username> <points>")
        return 2
    mainScript(argv[1], argv[2])
    return 0



if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
