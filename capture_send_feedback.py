"""Capture brief Snapchat send-feedback banners without sending automatically."""
import argparse
from datetime import datetime
import json
from pathlib import Path
from time import perf_counter
import xml.etree.ElementTree as ET
import zipfile

from utils import adbConnection, getDump, XML_DIR


def text_nodes(root):
    return [dict(node.attrib) for node in root.iter("node")
            if node.get("text") or node.get("content-desc")]


def capture(device, folder, seconds):
    phase = "capture_send_feedback"
    records = []
    started = perf_counter()
    interrupted = False
    try:
        while perf_counter() - started < seconds:
            index = len(records)
            before = perf_counter()
            record = {"index": index, "start_seconds": round(before - started, 4)}
            try:
                getDump(device, phase)
                data = (XML_DIR / f"{phase}.xml").read_bytes()
                root = ET.fromstring(data)
                filename = f"frame-{index:04d}.xml"
                (folder / filename).write_bytes(data)
                record.update(file=filename, text_nodes=text_nodes(root))
            except Exception as exc:
                record["error"] = str(exc)
            record["end_seconds"] = round(perf_counter() - started, 4)
            records.append(record)
    except KeyboardInterrupt:
        interrupted = True
    (folder / "timeline.json").write_text(
        json.dumps({"duration_seconds": perf_counter() - started,
                    "interrupted": interrupted, "frames": records},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    # Keep all frames, including identical ones: absence and duration matter.
    lines, previous = [], set()
    for record in records:
        if "error" in record:
            lines.append(f"{record['start_seconds']:.3f}s ERROR {record['error']}")
            continue
        current = {(n.get("resource-id", ""), n.get("text", ""),
                    n.get("content-desc", ""), n.get("package", ""))
                   for n in record["text_nodes"]}
        for rid, text, desc, package in sorted(current - previous):
            lines.append(f"{record['start_seconds']:.3f}s NEW id={rid!r} text={text!r} desc={desc!r} package={package!r}")
        previous = current
    (folder / "changes.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", choices=("success", "failure"), required=True)
    parser.add_argument("--seconds", type=float, default=12)
    args = parser.parse_args()
    if not 2 <= args.seconds <= 60:
        parser.error("seconds must be between 2 and 60")
    device = adbConnection()  # Initialize the persistent service before capture.
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    folder = Path(__file__).resolve().parent / "diagnostics" / f"feedback-{args.label}-{stamp}"
    folder.mkdir(parents=True)
    # Baseline also warms up the first dump, before the short-lived banner.
    getDump(device, "capture_send_feedback")
    (folder / "baseline.xml").write_bytes((XML_DIR / "capture_send_feedback.xml").read_bytes())
    (folder / "run.json").write_text(json.dumps({"label": args.label,
                                               "seconds": args.seconds,
                                               "device_serial": device.serial}), encoding="utf-8")
    print("Zet Snapchat op de ontvangerlijst met één testontvanger geselecteerd.")
    input("Druk Enter; tik daarna direct handmatig op Versturen op de telefoon. ")
    print("Opname actief — tik nu op Versturen. Wacht tot de opname klaar is.", flush=True)
    records = capture(device, folder, args.seconds)
    archive = folder.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for file in sorted(folder.iterdir()):
            output.write(file, arcname=file.name)
    good = sum("file" in r for r in records)
    elapsed = records[-1]["end_seconds"] if records else 0
    print(f"Klaar: {good} XML-dumps in {elapsed:.2f}s; {len(records) - good} fouten.")
    print(f"Upload dit bestand: {archive}")
    print("Als de balk niet in XML voorkomt, bewijst deze opname geen succes of fout.")
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main())
