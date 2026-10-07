import sys
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
import json
from pathlib import Path
from time import perf_counter, sleep
import re
import shlex
import logging

from utils import adbConnection, startSnap, rebootSnap, getDump, XML_DIR
from utils.clicking import ClickButton
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

# Fast-safe timing:
# Do not wait for the historical maximum. Each next click actively polls the
# target element and clicks as soon as that element exists in the UI dump.
# These values only tune diagnostics; they are not fixed sleep delays.
TIMING_PROFILE_PATH = XML_DIR / "screen_wait_profile.json"
TIMING_EWMA_ALPHA = 0.25

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


@dataclass
class ScreenTimingProfile:
    """Stores timing diagnostics without using them as fixed sleep delays."""

    path: Path = TIMING_PROFILE_PATH
    fastest_clickable_seconds: dict[str, float] = field(default_factory=dict)
    slowest_clickable_seconds: dict[str, float] = field(default_factory=dict)
    average_clickable_seconds: dict[str, float] = field(default_factory=dict)
    samples_seen: dict[str, int] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path = TIMING_PROFILE_PATH) -> "ScreenTimingProfile":
        if not path.exists():
            return cls(path=path)

        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            logger.exception("Could not load screen timing profile; starting fresh")
            return cls(path=path)

        profile = cls(path=path)

        # Backward compatibility with the previous max-wait profile. The old max
        # values are kept only as diagnostics; they are not used as sleeps.
        old_max = {
            str(step): float(seconds)
            for step, seconds in data.get("max_load_seconds", {}).items()
        }

        profile.fastest_clickable_seconds = {
            str(step): float(seconds)
            for step, seconds in data.get("fastest_clickable_seconds", {}).items()
        }
        profile.slowest_clickable_seconds = {
            str(step): float(seconds)
            for step, seconds in data.get("slowest_clickable_seconds", old_max).items()
        }
        profile.average_clickable_seconds = {
            str(step): float(seconds)
            for step, seconds in data.get("average_clickable_seconds", {}).items()
        }
        profile.samples_seen = {
            str(step): int(count)
            for step, count in data.get("samples_seen", {}).items()
        }
        return profile

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": 3,
                "mode": "click_as_soon_as_target_is_visible",
                "fastest_clickable_seconds": self.fastest_clickable_seconds,
                "slowest_clickable_seconds": self.slowest_clickable_seconds,
                "average_clickable_seconds": self.average_clickable_seconds,
                "samples_seen": self.samples_seen,
            }
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, sort_keys=True)
        except Exception:
            logger.exception("Could not save screen timing profile")

    def record_clickable_time(self, step: str, elapsed_seconds: float) -> None:
        if elapsed_seconds <= 0:
            return

        elapsed_seconds = round(elapsed_seconds, 3)
        previous_fastest = self.fastest_clickable_seconds.get(step)
        previous_slowest = self.slowest_clickable_seconds.get(step)
        previous_average = self.average_clickable_seconds.get(step)
        previous_samples = self.samples_seen.get(step, 0)

        new_fastest = previous_fastest is None or elapsed_seconds < previous_fastest
        new_slowest = previous_slowest is None or elapsed_seconds > previous_slowest

        if new_fastest:
            self.fastest_clickable_seconds[step] = elapsed_seconds
        if new_slowest:
            self.slowest_clickable_seconds[step] = elapsed_seconds

        if previous_average is None:
            self.average_clickable_seconds[step] = elapsed_seconds
        else:
            self.average_clickable_seconds[step] = round(
                previous_average + TIMING_EWMA_ALPHA * (elapsed_seconds - previous_average),
                3,
            )

        self.samples_seen[step] = previous_samples + 1

        if new_fastest:
            logger.info(
                "New fastest safe clickable time for %s: %.3fs.",
                step,
                elapsed_seconds,
            )
        else:
            logger.debug(
                "Clickable time for %s: %.3fs. Fastest: %.3fs. Average: %.3fs.",
                step,
                elapsed_seconds,
                self.fastest_clickable_seconds.get(step, elapsed_seconds),
                self.average_clickable_seconds.get(step, elapsed_seconds),
            )

        # Save on meaningful boundaries; final save also happens after the run.
        if new_fastest or new_slowest or self.samples_seen[step] <= 3:
            self.save()

    def describe(self) -> str:
        steps = sorted(
            set(self.fastest_clickable_seconds)
            | set(self.average_clickable_seconds)
            | set(self.slowest_clickable_seconds)
        )
        if not steps:
            return "no measured clickable timings yet"

        parts = []
        for step in steps:
            fastest = self.fastest_clickable_seconds.get(step, 0.0)
            average = self.average_clickable_seconds.get(step, 0.0)
            slowest = self.slowest_clickable_seconds.get(step, 0.0)
            samples = self.samples_seen.get(step, 0)
            parts.append(
                f"{step}: fastest={fastest:.3f}s, avg={average:.3f}s, "
                f"slowest={slowest:.3f}s, samples={samples}"
            )
        return "; ".join(parts)


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
    # The send button also exists before any recipient is selected.
    if _node_by_resource(tree, SEARCH_FIELD_ID) is not None:
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
    # A matching name in the confirmation panel or a selected/checked
    # recipient is evidence; an enabled send button alone is not.
    panel = _node_by_resource(tree, "send_confirmation_view")
    if panel is not None:
        for node in panel.iter("node"):
            if username in (node.get("text"), node.get("content-desc")):
                return True
    for node in tree.iter("node"):
        rid = node.get("resource-id", "")
        if rid in (USER_ROW_ID, LAST_RECIPIENTS_ID) or rid.startswith("select_recipients_friends_"):
            if node.get("selected") == "true" or node.get("checked") == "true":
                return True
    return False


def select_recipient(device, username, use_last):
    tree = _wait_tree(device, lambda t: _node_by_resource(t, SEARCH_FIELD_ID) is not None,
                      "recipient picker")
    if _selection_visible(tree, username):
        raise RuntimeError("Picker already contains a selection; start from a fresh snap")
    if use_last and _node_by_resource(tree, LAST_RECIPIENTS_ID) is not None:
        ClickButton("clicking_user", device).ClickNow(LAST_RECIPIENTS_ID, None, tree=tree)
        # An uncertain click must not be followed by another recipient click.
        return _wait_tree(device, lambda t: _selection_visible(t, username),
                   "recipient selection confirmation; capture a post-selection XML dump if this fails")

    if not re.fullmatch(r"[A-Za-z0-9_. -]+", username):
        raise RuntimeError("ADB text input supports ASCII letters, digits, spaces, _, . and - here")
    if _node_by_resource(tree, "clear-button") is not None:
        ClickButton("clicking_user_search", device).ClickNow("clear-button", None, tree=tree)
        tree = None
    ClickButton("clicking_user_search", device).ClickNow(SEARCH_FIELD_ID, None, tree=tree)
    device.shell("input text " + shlex.quote(username.replace(" ", "%s")))
    def exact_result(t):
        field = _node_by_resource(t, SEARCH_FIELD_ID)
        return (field is not None and field.get("text") == username
                and any(n.get("resource-id") == USER_ROW_ID and n.get("text") == username
                        for n in t.iter("node")))
    tree = _wait_tree(device, exact_result, "exact search result")
    ClickButton("clicking_user", device).ClickNow(USER_ROW_ID, username, tree=tree)
    return _wait_tree(device, lambda t: _selection_visible(t, username),
               "recipient selection confirmation; capture a post-selection XML dump if this fails")


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
    timing_profile: ScreenTimingProfile,
    use_last: bool = False,
    camera_tree=None,
):
    step = STEP_CAMERA
    reboot_used = False
    selection_tree = None

    for _ in range(MAX_FLOW_ACTIONS):
        try:
            started = perf_counter()
            if step == STEP_CAMERA:
                ClickButton(STEP_PHASE[step], device).ClickNow(
                    CAMERA_CAPTURE_BUTTON_ID, None, tree=camera_tree)
                camera_tree = None  # Never reuse a tree across a tap.
            elif step == STEP_USER:
                selection_tree = select_recipient(device, username_input, use_last and not reboot_used)
            elif step == STEP_SEND:
                # The confirmation dump also supplies current send-button bounds.
                if selection_tree is None or not _selection_visible(selection_tree, username_input):
                    raise RuntimeError("Recipient selection could not be confirmed before sending")
                ClickButton(STEP_PHASE[step], device).ClickNow(
                    SEND_BUTTON_ID, None, tree=selection_tree,
                    guard=lambda t: _selection_visible(t, username_input))
                selection_tree = None
                tree = _wait_tree(device, lambda t: _node_by_resource(t, SEARCH_FIELD_ID) is None
                                  and (_node_by_resource(t, CAMERA_CAPTURE_BUTTON_ID) is not None
                                       or _node_by_resource(t, BACK_TO_CAMERA_BUTTON_ID) is not None),
                                  "recipient picker to close after sending")
                timing_profile.record_clickable_time(step, perf_counter() - started)
                if _node_by_resource(tree, CAMERA_CAPTURE_BUTTON_ID) is not None:
                    return tree  # Next snap can use this immediately verified camera.
                ClickButton(STEP_PHASE[STEP_BACK], device).ClickNow(
                    BACK_TO_CAMERA_BUTTON_ID, None, tree=tree)
                return _wait_tree(device, lambda t: _node_by_resource(t, CAMERA_CAPTURE_BUTTON_ID) is not None
                                  and _node_by_resource(t, SEARCH_FIELD_ID) is None,
                                  "return to camera after sending")
            else:
                click_step(device, step, username_input)
            timing_profile.record_clickable_time(step, perf_counter() - started)
            step = NEXT_STEP[step]
        except RuntimeError:
            if step in (STEP_USER, STEP_SEND, STEP_BACK):
                raise  # Never retry uncertain recipient selection or sending.
            camera_tree = None
            step, reboot_used = recover_after_failed_step(
                device=device, failed_step=step, username_input=username_input,
                reboot_used=reboot_used)
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

    timing_profile = ScreenTimingProfile.load()
    logger.info("Loaded screen timing profile: %s", timing_profile.describe())

    # Unlocking phone, starting Snap
    startSnap(device)
    logger.info("Opened snap, start sending pictures")

    camera_tree = None
    pointscounter = 0
    send_started = perf_counter()

    try:
        while pointscounter < points_input:
            camera_tree = send_one_snap(device, username_input, timing_profile,
                                        use_last=pointscounter > 0, camera_tree=camera_tree)
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
    timing_profile.save()
    logger.info("Final screen timing profile: %s", timing_profile.describe())
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
