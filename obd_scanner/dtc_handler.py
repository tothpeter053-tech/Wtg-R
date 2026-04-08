"""DTC (Diagnostic Trouble Code) reader and cleaner."""

import logging

try:
    import obd
except ImportError:  # pragma: no cover
    obd = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# DTC category prefixes
_DTC_CATEGORY = {
    "P": "Powertrain",
    "C": "Chassis",
    "B": "Body",
    "U": "Network / Communication",
}

# Well-known generic OBD-II DTC descriptions for informational display
_KNOWN_DESCRIPTIONS = {
    "P0001": "Fuel Volume Regulator Control Circuit/Open",
    "P0011": "Camshaft Position A - Timing Over-Advanced / System Performance (Bank 1)",
    "P0016": "Crankshaft Position - Camshaft Position Correlation (Bank 1, Sensor A)",
    "P0030": "HO2S Heater Control Circuit (Bank 1, Sensor 1)",
    "P0100": "Mass or Volume Air Flow Circuit Malfunction",
    "P0101": "Mass or Volume Air Flow Circuit Range/Performance Problem",
    "P0102": "Mass or Volume Air Flow Circuit Low Input",
    "P0103": "Mass or Volume Air Flow Circuit High Input",
    "P0110": "Intake Air Temperature Circuit Malfunction",
    "P0115": "Engine Coolant Temperature Circuit Malfunction",
    "P0120": "Throttle/Pedal Position Sensor/Switch A Circuit Malfunction",
    "P0130": "O2 Sensor Circuit Malfunction (Bank 1, Sensor 1)",
    "P0171": "System Too Lean (Bank 1)",
    "P0172": "System Too Rich (Bank 1)",
    "P0174": "System Too Lean (Bank 2)",
    "P0175": "System Too Rich (Bank 2)",
    "P0200": "Injector Circuit Malfunction",
    "P0300": "Random/Multiple Cylinder Misfire Detected",
    "P0301": "Cylinder 1 Misfire Detected",
    "P0302": "Cylinder 2 Misfire Detected",
    "P0303": "Cylinder 3 Misfire Detected",
    "P0304": "Cylinder 4 Misfire Detected",
    "P0305": "Cylinder 5 Misfire Detected",
    "P0306": "Cylinder 6 Misfire Detected",
    "P0320": "Ignition/Distributor Engine Speed Input Circuit Malfunction",
    "P0325": "Knock Sensor 1 Circuit Malfunction (Bank 1 or Single Sensor)",
    "P0335": "Crankshaft Position Sensor A Circuit Malfunction",
    "P0340": "Camshaft Position Sensor A Circuit Malfunction (Bank 1 or Single Sensor)",
    "P0400": "Exhaust Gas Recirculation Flow Malfunction",
    "P0420": "Catalyst System Efficiency Below Threshold (Bank 1)",
    "P0430": "Catalyst System Efficiency Below Threshold (Bank 2)",
    "P0440": "Evaporative Emission Control System Malfunction",
    "P0442": "Evaporative Emission Control System Leak Detected (Small Leak)",
    "P0446": "Evaporative Emission Control System Vent Control Circuit Malfunction",
    "P0455": "Evaporative Emission Control System Leak Detected (Large Leak)",
    "P0500": "Vehicle Speed Sensor Malfunction",
    "P0505": "Idle Control System Malfunction",
    "P0600": "Serial Communication Link Malfunction",
    "P0700": "Transmission Control System Malfunction",
    "P0741": "Torque Converter Clutch Circuit Performance or Stuck Off",
}


class DTCReadError(Exception):
    """Raised when DTCs cannot be retrieved."""


class DTCClearError(Exception):
    """Raised when DTCs cannot be cleared."""


class DTCHandler:
    """Read and clear Diagnostic Trouble Codes via an :class:`~obd_scanner.scanner.OBDScanner`.

    Args:
        scanner (OBDScanner): An already-connected :class:`~obd_scanner.scanner.OBDScanner` instance.
    """

    def __init__(self, scanner):
        self._scanner = scanner

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read_dtcs(self):
        """Read current (confirmed) DTCs stored in the ECU.

        Returns:
            list[dict]: Each dict has keys:
                - ``code`` (str): DTC code, e.g. ``"P0300"``.
                - ``description`` (str): Human-readable description.
                - ``category`` (str): Code category (Powertrain, Body, …).
                - ``raw`` (tuple): Raw (code, description) tuple from python-obd.

        Raises:
            DTCReadError: When the ECU returns an error or no response.
        """
        return self._read_dtc_command("GET_DTC")

    def read_pending_dtcs(self):
        """Read pending (not yet confirmed) DTCs.

        Returns:
            list[dict]: Same format as :meth:`read_dtcs`.

        Raises:
            DTCReadError: When the ECU returns an error or no response.
        """
        return self._read_dtc_command("GET_CURRENT_DTC")

    def read_freeze_dtcs(self):
        """Read freeze-frame DTCs (codes stored when MIL turned on).

        Returns:
            list[dict]: Same format as :meth:`read_dtcs`.

        Raises:
            DTCReadError: When the ECU returns an error or no response.
        """
        return self._read_dtc_command("FREEZE_DTC")

    def clear_dtcs(self):
        """Clear all stored DTCs and reset the MIL (Check Engine Light).

        .. warning::
            This command erases all fault codes and freeze-frame data.
            Use with caution — only clear codes after diagnosing the root cause.

        Returns:
            bool: ``True`` when the clear command was accepted by the ECU.

        Raises:
            DTCClearError: When the ECU rejects the clear command.
        """
        if obd is None:
            raise ImportError("python-obd is not installed. Run: pip install obd")

        logger.info("Sending CLEAR_DTC command …")
        response = self._scanner.query(obd.commands.CLEAR_DTC)
        if response.is_null():
            raise DTCClearError(
                "ECU did not acknowledge the CLEAR_DTC command. "
                "Ensure the ignition is on and the engine is accessible."
            )
        logger.info("DTCs cleared successfully.")
        return True

    def describe(self, code):
        """Return a human-readable description for a DTC code.

        Looks up the bundled description table first, then falls back to
        the python-obd description if available.

        Args:
            code (str): DTC code string, e.g. ``"P0300"``.

        Returns:
            str: Description text, or ``"Unknown code"`` when not found.
        """
        upper = code.upper()
        return _KNOWN_DESCRIPTIONS.get(upper, "Unknown code — consult vehicle service manual.")

    def category(self, code):
        """Return the DTC category name for the given code.

        Args:
            code (str): DTC code string.

        Returns:
            str: Category name (e.g. ``"Powertrain"``), or ``"Unknown"``.
        """
        if code:
            return _DTC_CATEGORY.get(code[0].upper(), "Unknown")
        return "Unknown"

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _read_dtc_command(self, command_name):
        if obd is None:
            raise ImportError("python-obd is not installed. Run: pip install obd")

        if not hasattr(obd.commands, command_name):
            raise DTCReadError(f"OBD command {command_name!r} is not available.")

        command = getattr(obd.commands, command_name)
        response = self._scanner.query(command)

        if response.is_null():
            raise DTCReadError(
                f"No response received for {command_name}. "
                "Ensure the ignition is on."
            )

        dtcs = []
        for raw_entry in response.value:
            code = raw_entry[0] if isinstance(raw_entry, (list, tuple)) else str(raw_entry)
            description = (
                raw_entry[1]
                if isinstance(raw_entry, (list, tuple)) and len(raw_entry) > 1
                else ""
            )
            # Prefer our richer description table
            description = _KNOWN_DESCRIPTIONS.get(code.upper(), description) or "No description available."
            dtcs.append(
                {
                    "code": code,
                    "description": description,
                    "category": self.category(code),
                    "raw": raw_entry,
                }
            )

        logger.info("Read %d DTC(s) via %s.", len(dtcs), command_name)
        return dtcs
