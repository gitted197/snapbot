"""Persistent uiautomator2 hierarchy service; taps use the shared ADB flow."""
import xml.etree.ElementTree as ET

_sessions = {}


def _serial(device):
    serial = getattr(device, "serial", None)
    if not isinstance(serial, str) or not serial:
        raise RuntimeError("Geen apparaatserial beschikbaar voor de snelle XML-verbinding")
    return serial


def prepare_ui(device):
    serial = _serial(device)
    if serial in _sessions:
        return
    try:
        import uiautomator2 as u2
    except ImportError as exc:
        raise RuntimeError("Installeer de snelle backend: python -m pip install -r requirements.txt") from exc
    try:
        session = u2.connect(serial)
        # Small idle window instead of waiting seconds for all animations.
        session.jsonrpc.setConfigurator({"waitForIdleTimeout": 100, "waitForSelectorTimeout": 0})
    except Exception as exc:
        raise RuntimeError("UI-verbinding kon niet starten; controleer ADB, USB-debugging en de uiautomator2-installatie") from exc
    _sessions[serial] = session


def dump_xml(device):
    serial = _serial(device)
    prepare_ui(device)
    try:
        xml = _sessions[serial].dump_hierarchy(compressed=False, pretty=False, max_depth=100)
        root = ET.fromstring(xml)
        if root.tag != "hierarchy" or not any(True for _ in root.iter("node")):
            raise RuntimeError("Snelle backend gaf een leeg scherm terug")
        return xml
    except Exception as exc:
        # Reconnect on the next poll; never return cached screen contents.
        _sessions.pop(serial, None)
        raise RuntimeError("Kon geen verse XML ophalen via uiautomator2") from exc
