import sys
import subprocess
import xml.etree.ElementTree as ET
from time import perf_counter, sleep
import re
import shlex
import logging

from utils import adbConnection, startSnap, rebootSnap, getDump, XML_DIR
from utils.clicking import ClickButton
from utils.run_control import RunControl, RunStopped, RecipientNotFound
from utils.send_feedback import success_visible, wait_for_internet, wait_for_send
from utils.recipient_ui import SEARCH_IDS, SEND_IDS, by_ids, picker_visible, unique_recipient, selection_visible
from utils.setup_logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

CAMERA_CAPTURE_BUTTON_ID = "com.snapchat.android:id/camera_capture_button"
NEXT_BUTTON_ID = "com.snapchat.android:id/send_btn"
USER_ROW_ID = "result-title"
SEARCH_FIELD_ID = "scu_search_text_field"
LAST_RECIPIENTS_ID = "select_last_recipients"
SEND_BUTTON_ID = "send_button"
BACK_TO_CAMERA_BUTTON_ID = "com.snapchat.android:id/ngs_camera_icon_container"

STEP_CAMERA = "camera"
STEP_NEXT = "next"
STEP_USER = "user"
STEP_SEND = "send"
STEP_BACK = "back"
STEP_DONE = "done"
SCREEN_DUMP_PHASE = "flow_recovery"
MAX_FLOW_ACTIONS = 20
# Prevent Snapchat heap growth across long runs; restart only between snaps.
SNAP_RESTART_INTERVAL = 200

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
    # The send button also exists before any recipient is selected.
    if picker_visible(tree):
        visible.add(STEP_USER)
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



def _wait_tree(device, predicate, description, timeout=10.0):
    started = perf_counter()
    deadline = started + timeout
    polls = 0
    while perf_counter() < deadline:
        tree = _dump_current_tree(device)
        polls += 1
        if tree is not None and predicate(tree):
            logger.debug("Ready %s after %.3fs (%s dumps)", description, perf_counter() - started, polls)
            return tree
        sleep(0.20)
    raise RuntimeError(f"Timed out waiting for {description}")


def _selection_visible(tree, username):
    return selection_visible(tree, username)


def select_recipient(device, username, use_last):
    tree = _wait_tree(device, picker_visible, "recipient picker")
    if by_ids(tree, ("send_confirmation_view", "com.snapchat.android:id/send_to_confirmation_bar")) is not None:
        # An existing confirmation panel may be empty in Compose; a nonempty
        # recipient label means this is not a clean starting picker.
        panel = by_ids(tree, ("send_confirmation_view", "com.snapchat.android:id/send_to_confirmation_bar"))
        if any(n.get("text") for n in panel.iter("node")
               if n.get("class") in ("android.widget.TextView", "javaClass")):
            raise RuntimeError("Picker already contains a selection; start from a fresh snap")

    try:
        node = unique_recipient(tree, username)
    except RuntimeError as exc:
        raise RecipientNotFound(str(exc)) from exc
    if node is not None:
        ClickButton("clicking_user", device).ClickElement(node, tree)
    elif use_last and _node_by_resource(tree, LAST_RECIPIENTS_ID) is not None:
        ClickButton("clicking_user", device).ClickNow(LAST_RECIPIENTS_ID, None, tree=tree)
    else:
        if not re.fullmatch(r"[A-Za-z0-9_. -]+", username):
            raise RecipientNotFound("Naam niet zichtbaar; zoekinvoer ondersteunt hier alleen ASCII")
        search = by_ids(tree, SEARCH_IDS)
        if _node_by_resource(tree, "clear-button") is not None:
            ClickButton("clicking_user_search", device).ClickNow("clear-button", None, tree=tree)
            tree = _wait_tree(device, picker_visible, "cleared recipient picker")
            search = by_ids(tree, SEARCH_IDS)
        ClickButton("clicking_user_search", device).ClickElement(search, tree)
        # Native picker exposes its placeholder as text; do not erase it.
        existing = search.get("text", "")
        if existing and existing not in ("Versturen naar…", "Versturen naar...", "Send To", "Send to…"):
            if len(existing) > 200:
                raise RuntimeError("Zoekveld bevat onverwacht lange tekst")
            device.shell("input keyevent KEYCODE_MOVE_END")
            device.shell("input keyevent " + " ".join(["KEYCODE_DEL"] * len(existing)))
        device.shell("input text " + shlex.quote(username.replace(" ", "%s")))
        def exact_result(t):
            field = by_ids(t, SEARCH_IDS)
            return field is not None and field.get("text") == username and unique_recipient(t, username) is not None
        try:
            tree = _wait_tree(device, exact_result, "exact search result")
        except RuntimeError as exc:
            current = _dump_current_tree(device)
            field = by_ids(current, SEARCH_IDS) if current is not None else None
            if field is not None and field.get("text") == username:
                raise RecipientNotFound(f"Geen unieke zichtbare match voor {username!r}") from exc
            raise
        ClickButton("clicking_user", device).ClickElement(unique_recipient(tree, username), tree)

    # Never repeat a recipient tap when its outcome is uncertain.
    return _wait_tree(device, lambda t: selection_visible(t, username),
                      "confirmation of the exact recipient")


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


def send_one_snap(
    device,
    username_input: str,
    use_last: bool = False,
    camera_tree=None,
    control=None,
):
    control = control or RunControl()
    step = STEP_CAMERA
    reboot_used = False
    selection_tree = None
    send_attempted = False

    for _ in range(MAX_FLOW_ACTIONS):
        control.check()
        if step == STEP_DONE:
            camera_tree = _wait_tree(
                device, lambda t: not picker_visible(t)
                and _node_by_resource(t, CAMERA_CAPTURE_BUTTON_ID) is not None,
                "camera after completed flow", timeout=30.0)
            if send_attempted:
                return camera_tree
            # Recovery can reach Back without having sent a snap. Do not count it.
            step = STEP_CAMERA
        try:
            if step == STEP_CAMERA:
                ClickButton(STEP_PHASE[step], device).ClickNow(
                    CAMERA_CAPTURE_BUTTON_ID, None, tree=camera_tree)
                camera_tree = None  # Never reuse a tree across a tap.
            elif step == STEP_USER:
                selection_tree = select_recipient(device, username_input, use_last and not reboot_used)
            elif step == STEP_BACK:
                click_step(device, STEP_BACK, username_input)
                camera_tree = _wait_tree(
                    device, lambda t: not picker_visible(t)
                    and _node_by_resource(t, CAMERA_CAPTURE_BUTTON_ID) is not None,
                    "camera after recovery back", timeout=30.0)
                if send_attempted:
                    return camera_tree
                step = STEP_CAMERA
                continue
            elif step == STEP_SEND:
                # The confirmation dump also supplies current send-button bounds.
                if selection_tree is None or not _selection_visible(selection_tree, username_input):
                    raise RuntimeError("Recipient selection could not be confirmed before sending")
                wait_for_internet(device, control)
                # Internet recovery may have taken minutes; never use old bounds.
                selection_tree = _wait_tree(device, lambda t: selection_visible(t, username_input)
                                            and not success_visible(t), "fresh recipient confirmation before send")
                send_attempted = True
                ClickButton(STEP_PHASE[step], device).ClickNow(
                    SEND_IDS, None, tree=selection_tree,
                    guard=lambda t: _selection_visible(t, username_input))
                selection_tree = None
                feedback = wait_for_send(device, _dump_current_tree, control)
                if isinstance(feedback, str) and feedback == "retry":
                    return "retry"
                def sent_screen(t):
                    return not picker_visible(t) and (
                        _node_by_resource(t, CAMERA_CAPTURE_BUTTON_ID) is not None
                        or _node_by_resource(t, BACK_TO_CAMERA_BUTTON_ID) is not None)
                tree = feedback if feedback is not None and sent_screen(feedback) else _wait_tree(
                    device, sent_screen, "recipient picker to close after sending")
                if _node_by_resource(tree, CAMERA_CAPTURE_BUTTON_ID) is not None:
                    return tree  # Next snap can use this immediately verified camera.
                ClickButton(STEP_PHASE[STEP_BACK], device).ClickNow(
                    BACK_TO_CAMERA_BUTTON_ID, None, tree=tree)
                return _wait_tree(device, lambda t: _node_by_resource(t, CAMERA_CAPTURE_BUTTON_ID) is not None
                                  and not picker_visible(t),
                                  "return to camera after sending")
            else:
                click_step(device, step, username_input)
            step = NEXT_STEP[step]
        except (RunStopped, RecipientNotFound):
            raise
        except RuntimeError:
            if step in (STEP_USER, STEP_SEND, STEP_BACK):
                raise  # Never retry uncertain recipient selection or sending.
            camera_tree = None
            step, reboot_used = recover_after_failed_step(
                device=device, failed_step=step, username_input=username_input,
                reboot_used=reboot_used)
    raise RuntimeError("Flow recovery exceeded maximum actions for one snap")



def _restart_snap_between_batches(device):
    """Restart the app only after the preceding snap completed its UI flow."""
    try:
        device.shell("input keyevent KEYCODE_WAKEUP")
        device.shell("am force-stop com.snapchat.android")
        sleep(0.5)
        output = device.shell("monkey -p com.snapchat.android -c android.intent.category.LAUNCHER 1")
        if any(marker in str(output).lower() for marker in ("monkey aborted", "no activities found", "error:")):
            raise RuntimeError("Snapchat could not be launched")
    except Exception as exc:
        raise RuntimeError("Preventieve Snapchat-herstart mislukt; voortgang blijft behouden in de log") from exc
    return _wait_tree(device, lambda t: not picker_visible(t)
                      and _node_by_resource(t, CAMERA_CAPTURE_BUTTON_ID) is not None,
                      "camera after preventive Snapchat restart", timeout=30.0)

def mainScript(username_input: str, points_input_raw, control=None) -> tuple[int, float]:
    control = control or RunControl()
    logger.debug("Function mainScript received username=%s", username_input)

    try:
        points_input = int(points_input_raw)
    except Exception as e:
        logger.exception("Error while parsing points to int")
        raise ValueError("Points must be an integer") from e

    if points_input <= 0:
        raise ValueError("Aantal snaps moet groter dan nul zijn")
    control.total = points_input

    # Start ADB daemon (best-effort)
    try:
        subprocess.run(["adb", "devices"], check=False)
    except Exception:
        logger.info("Could not start adb daemon")

    # Connecting to phone
    device = adbConnection()
    logger.debug("Connected to adb device")

    # Unlocking phone, starting Snap
    startSnap(device)
    logger.info("Opened snap, start sending pictures")

    camera_tree = None
    pointscounter = 0
    snaps_since_restart = 0
    send_started = perf_counter()

    try:
        while pointscounter < points_input:
            control.check()
            wait_for_internet(device, control)
            if snaps_since_restart >= SNAP_RESTART_INTERVAL:
                logger.info("Preventive Snapchat restart after %s/%s completed snaps", pointscounter, points_input)
                camera_tree = None  # Invalidate every pre-restart screen.
                camera_tree = _restart_snap_between_batches(device)
                snaps_since_restart = 0
                logger.info("Snapchat camera ready; continuing at snap %s", pointscounter + 1)
            try:
                camera_tree = send_one_snap(device, username_input,
                                            use_last=snaps_since_restart > 0, camera_tree=camera_tree,
                                            control=control)
            except RecipientNotFound as exc:
                wait_for_internet(device, control)
                control.request("username", f"{exc}. Geef een andere zichtbare naam met !snapnaam <naam>, of !snapstop.")
                while True:
                    replacement = control.poll()
                    if replacement:
                        username_input = replacement.strip()
                        break
                    sleep(0.25)
                control.resume("Nieuwe ontvangernaam ontvangen; resterende snaps worden naar deze naam gestuurd.")
                camera_tree = _restart_snap_between_batches(device)
                snaps_since_restart = 0
                continue
            if isinstance(camera_tree, str) and camera_tree == "retry":
                wait_for_internet(device, control)
                camera_tree = _restart_snap_between_batches(device)
                snaps_since_restart = 0
                continue
            pointscounter += 1
            control.completed = pointscounter
            control.emit("progress", "Snap bevestigd")
            snaps_since_restart += 1

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
