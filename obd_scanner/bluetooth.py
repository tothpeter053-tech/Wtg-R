"""Bluetooth device discovery and serial port resolution for ELM327 adapters."""

import logging
import subprocess
import sys

logger = logging.getLogger(__name__)

# Common Bluetooth-to-serial port prefixes by platform
_BT_PORT_PREFIXES = {
    "linux": ["/dev/rfcomm", "/dev/ttyUSB", "/dev/ttyS"],
    "darwin": ["/dev/tty.OBD", "/dev/tty.ELM", "/dev/tty.OBDII", "/dev/cu.OBD"],
    "win32": ["COM"],
}


class BluetoothDiscovery:
    """Discover and enumerate Bluetooth OBD-II (ELM327) serial ports."""

    # Default ELM327 Bluetooth credentials
    DEFAULT_PIN = "1234"
    ALT_PIN = "0000"

    # Well-known ELM327 Bluetooth device name fragments (case-insensitive)
    KNOWN_DEVICE_NAMES = ["obd", "elm327", "obdii", "vlink", "v-link", "carista"]

    def __init__(self):
        self._platform = sys.platform

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_ports(self):
        """Return a list of serial port paths likely used by BT OBD adapters.

        Returns:
            list[str]: Sorted list of candidate port strings.
        """
        import glob as _glob

        prefixes = _BT_PORT_PREFIXES.get(self._platform, [])
        ports = []
        for prefix in prefixes:
            found = sorted(_glob.glob(f"{prefix}*"))
            ports.extend(found)

        if not ports:
            logger.warning(
                "No candidate Bluetooth serial ports found on %s.", self._platform
            )
        return ports

    def scan_bluetooth_devices(self):
        """Scan for nearby Bluetooth devices and return those that look like OBD adapters.

        Uses the system ``hcitool`` on Linux / ``system_profiler`` on macOS.
        Returns an empty list on failure or unsupported platform.

        Returns:
            list[dict]: Each dict has keys ``address`` and ``name``.
        """
        try:
            if self._platform == "linux":
                return self._scan_linux()
            if self._platform == "darwin":
                return self._scan_macos()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Bluetooth scan failed: %s", exc)
        return []

    def is_obd_device(self, device_name):
        """Return True if the device name suggests an ELM327 / OBD-II adapter.

        Args:
            device_name (str): Bluetooth device name.

        Returns:
            bool: True when the name matches a known OBD adapter pattern.
        """
        lower = device_name.lower()
        return any(kw in lower for kw in self.KNOWN_DEVICE_NAMES)

    # ------------------------------------------------------------------
    # Platform helpers
    # ------------------------------------------------------------------

    def _scan_linux(self):
        result = subprocess.run(
            ["hcitool", "scan"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        devices = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("Scanning"):
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                address, name = parts
                devices.append({"address": address, "name": name})
        return devices

    def _scan_macos(self):
        result = subprocess.run(
            ["system_profiler", "SPBluetoothDataType"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        devices = []
        current_name = None
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.endswith(":") and "Address" not in line and "Services" not in line:
                current_name = line.rstrip(":")
            elif line.startswith("Address:") and current_name:
                address = line.split(":", 1)[1].strip()
                devices.append({"address": address, "name": current_name})
                current_name = None
        return devices
