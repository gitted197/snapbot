"""Use observed Snapchat feedback rather than camera return as send evidence."""
import re
import subprocess
from time import perf_counter, sleep

SUCCESS_TEXT = "Snap verstuurd!"


def success_visible(tree):
    return tree is not None and any(
        n.get("package") == "com.snapchat.android" and n.get("text") == SUCCESS_TEXT
        for n in tree.iter("node"))


def parse_connectivity(output):
    match = re.search(r"Active default network:\s*(\S+)", output, re.I)
    if not match:
        return None
    value = match.group(1)
    if value.lower() in ("none", "null", "-1", "0"):
        return False
    if not value.isdigit():
        return None
    # Limit interpretation to the live network list, not historical logs.
    live = output.split("Current Networks:", 1)
    if len(live) != 2:
        return None
    blocks = re.split(r"(?=NetworkAgentInfo\s*\{)", live[1])
    for block in blocks:
        if not block.startswith("NetworkAgentInfo"):
            continue
        header = block.splitlines()[0]
        if re.search(r"network\s*\{\s*" + re.escape(value) + r"\s*\}", header):
            caps = re.search(r"Capabilities:\s*([^\]\n}]*)", block)
            if not caps:
                return None
            return bool(re.search(r"\bINTERNET\b", caps.group(1)) and re.search(r"\bVALIDATED\b", caps.group(1)))
    return None


def phone_online(device):
    try:
        result = subprocess.run(["adb", "-s", device.serial, "shell", "dumpsys", "connectivity"],
                                capture_output=True, text=True, timeout=5)
        return parse_connectivity(result.stdout) if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def wait_for_internet(device, control):
    control.check()
    status = phone_online(device)
    if status is not False:
        # Unknown formats never become a false claim of working internet.
        # The mandatory Snapchat success check still protects the counter.
        return
    control.request("network", "Telefoon heeft geen gevalideerde internetverbinding. Run gepauzeerd; herstel internet. Automatisch verder na herstel, of !snapstop.")
    while True:
        control.check()
        if phone_online(device) is True:
            control.resume("Internet op de telefoon hersteld; run gaat verder.")
            return
        sleep(2)


def wait_for_send(device, dump_tree, control, timeout=10):
    deadline = perf_counter() + timeout
    paused = False
    while True:
        control.check()
        tree = dump_tree(device)
        if success_visible(tree):
            if paused:
                control.resume("Snapchat meldt alsnog ‘Snap verstuurd!’; huidige snap bevestigd.")
            return tree
        if not paused and perf_counter() >= deadline:
            control.request("send", "Verzending niet bevestigd. Teller blijft staan; geen nieuwe snaps. Herstel internet en wacht. Als je de status zelf gecontroleerd hebt: !snapverder verzonden of !snapverder opnieuw. Stoppen: !snapstop.")
            paused = True
        if paused:
            choice = control.poll()
            if choice == "verzonden":
                control.resume("Gebruiker bevestigt de huidige snap als verzonden.")
                return tree
            if choice == "opnieuw":
                control.resume("Gebruiker kiest opnieuw proberen; controleer de Snapchat-wachtrij om dubbel verzenden te voorkomen.")
                return "retry"
        sleep(0.10 if not paused else 0.25)
