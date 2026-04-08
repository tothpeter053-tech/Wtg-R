"""Live sensor / PID data reader."""

import logging

try:
    import obd
except ImportError:  # pragma: no cover
    obd = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Human-readable labels for the most common OBD-II PIDs
COMMON_PIDS = [
    "RPM",
    "SPEED",
    "COOLANT_TEMP",
    "ENGINE_LOAD",
    "THROTTLE_POS",
    "INTAKE_TEMP",
    "MAF",
    "SHORT_FUEL_TRIM_1",
    "LONG_FUEL_TRIM_1",
    "FUEL_PRESSURE",
    "INTAKE_PRESSURE",
    "TIMING_ADVANCE",
    "O2_B1S1",
    "O2_B1S2",
    "BAROMETRIC_PRESSURE",
    "AMBIENT_AIR_TEMP",
    "FUEL_LEVEL",
    "RUN_TIME",
    "DISTANCE_SINCE_DTC_CLEAR",
    "CONTROL_MODULE_VOLTAGE",
]


class SensorReadError(Exception):
    """Raised when a sensor value cannot be retrieved."""


class SensorReader:
    """Read live sensor data from the vehicle ECU via an :class:`~obd_scanner.scanner.OBDScanner`.

    Args:
        scanner (OBDScanner): An already-connected :class:`~obd_scanner.scanner.OBDScanner` instance.
    """

    def __init__(self, scanner):
        self._scanner = scanner

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read(self, pid_name):
        """Read a single sensor by PID name.

        Args:
            pid_name (str): OBD-II PID name, e.g. ``"RPM"`` or ``"SPEED"``.

        Returns:
            dict: ``{"pid": str, "value": ..., "unit": str | None, "raw": OBDResponse}``

        Raises:
            SensorReadError: When the PID is unknown or the vehicle returns no data.
        """
        if obd is None:
            raise ImportError("python-obd is not installed. Run: pip install obd")

        command = self._resolve_command(pid_name)
        response = self._scanner.query(command)

        if response.is_null():
            raise SensorReadError(
                f"No data returned for PID {pid_name!r}. "
                "The vehicle may not support this sensor."
            )

        value = response.value
        unit = str(value.u) if hasattr(value, "u") else None
        magnitude = value.magnitude if hasattr(value, "magnitude") else value

        logger.debug("Read %s = %s %s", pid_name, magnitude, unit or "")
        return {
            "pid": pid_name,
            "value": magnitude,
            "unit": unit,
            "raw": response,
        }

    def read_all(self, pids=None):
        """Read multiple sensors.

        Args:
            pids (list[str] | None): List of PID names. Defaults to :data:`COMMON_PIDS`.

        Returns:
            list[dict]: List of sensor result dicts (same format as :meth:`read`).
                Failed reads are included with ``"error"`` key instead of ``"value"``.
        """
        if pids is None:
            pids = COMMON_PIDS

        results = []
        for pid in pids:
            try:
                result = self.read(pid)
            except (SensorReadError, KeyError, Exception) as exc:  # noqa: BLE001
                logger.warning("Could not read %s: %s", pid, exc)
                result = {"pid": pid, "error": str(exc)}
            results.append(result)
        return results

    def supported_pids(self):
        """Return the PID names supported by the connected vehicle.

        Returns:
            list[str]: Sorted list of supported PID name strings.
        """
        commands = self._scanner.supported_commands()
        return sorted(cmd.name for cmd in commands if cmd.name)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_command(self, pid_name):
        """Resolve a PID name string to an obd.commands object.

        Args:
            pid_name (str): PID name (case-insensitive).

        Returns:
            obd.OBDCommand: The command object.

        Raises:
            SensorReadError: When the PID name is not recognised.
        """
        upper = pid_name.upper()
        if not hasattr(obd.commands, upper):
            raise SensorReadError(
                f"Unknown PID {pid_name!r}. "
                "Use supported_pids() to see available sensors."
            )
        return getattr(obd.commands, upper)
