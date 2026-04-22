import sys
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
import json
from pathlib import Path
from time import perf_counter
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


def send_one_snap(
    device,
    username_input: str,
    timing_profile: ScreenTimingProfile,
) -> None:
    step = STEP_CAMERA
    reboot_used = False

    for _ in range(MAX_FLOW_ACTIONS):
        if step == STEP_DONE:
            return

        try:
            click_started = perf_counter()
            click_step(device, step, username_input)
            timing_profile.record_clickable_time(step, perf_counter() - click_started)

            # No fixed sleep here. The next iteration immediately tries the next
            # click. If that screen is not ready yet, ClickButton polls until the
            # target element exists and clicks at the first safe moment.
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

    timing_profile = ScreenTimingProfile.load()
    logger.info("Loaded screen timing profile: %s", timing_profile.describe())

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

            send_one_snap(device, username_input, timing_profile)
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
