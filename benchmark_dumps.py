"""Compare stationary-screen dumps without selecting or sending snaps."""
import argparse
import os
import statistics
import xml.etree.ElementTree as ET
from time import perf_counter

from utils import adbConnection, getDump, XML_DIR
from utils.recipient_ui import SEARCH_IDS, SEND_IDS, by_ids, picker_visible, recipient_matches, selection_visible


def signature(tree, username):
    result = (picker_visible(tree), by_ids(tree, SEND_IDS) is not None,
              any(n.get("resource-id") == "com.snapchat.android:id/camera_capture_button" for n in tree.iter("node")))
    if username:
        result += (len(recipient_matches(tree, username)), selection_visible(tree, username))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--username", help="Exact displayed name, for selector comparison")
    args = parser.parse_args()
    if not 1 <= args.samples <= 20:
        parser.error("samples must be between 1 and 20")
    os.environ["SNAPBOT_XML_BACKEND"] = "adb"
    device = adbConnection()
    signatures = {}
    timings = {}
    for backend in ("adb", "uiautomator2"):
        os.environ["SNAPBOT_XML_BACKEND"] = backend
        # Warmup includes first service initialization, excluded from samples.
        getDump(device, "benchmark")
        times, signs = [], []
        for _ in range(args.samples):
            started = perf_counter()
            getDump(device, "benchmark")
            tree = ET.parse(XML_DIR / "benchmark.xml")
            times.append(perf_counter() - started)
            signs.append(signature(tree, args.username))
        signatures[backend] = signs
        timings[backend] = statistics.median(times)
        print(f"{backend}: median {timings[backend]:.3f}s, range {min(times):.3f}-{max(times):.3f}s")
    stable = all(s == signatures["adb"][0] for values in signatures.values() for s in values)
    if not signatures["adb"][0][0] and not signatures["adb"][0][2]:
        print("No recognized picker or camera screen. Repeat on the intended Snapchat screen.")
        return 1
    print("Selector comparison: " + ("MATCH" if stable else "DIFFERENT — do not enable for a run yet"))
    if stable:
        print(f"Dump-time ratio: {timings['adb'] / max(timings['uiautomator2'], 0.000001):.2f}x")
        print("This measures this screen only. Also test selected-recipient and camera screens.")
    return 0 if stable else 1


if __name__ == "__main__":
    raise SystemExit(main())
