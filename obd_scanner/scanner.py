"""OBD connection management (wraps python-obd for ELM327 adapters)."""

import logging
import time

try:
    import obd
    from obd import OBDStatus
except ImportError:  # pragma: no cover
    obd = None  # type: ignore[assignment]
    OBDStatus = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Default baud rates tried in order when auto-detecting
_BAUD_RATES = [38400, 9600, 57600, 115200]
# Seconds to wait between connection retries
_RETRY_DELAY = 2


class ConnectionError(Exception):
    """Raised when the OBD adapter cannot be reached."""


class OBDScanner:
    """Manage the OBD-II connection to an ELM327 adapter over Bluetooth serial.

    Args:
        port (str | None): Serial port path (e.g. ``/dev/rfcomm0`` or ``COM3``).
            Pass ``None`` to let python-obd auto-detect.
        baudrate (int | None): Baud rate. ``None`` enables auto-detection.
        fast (bool): Enable fast OBD querying (skips slow init checks).
        timeout (float): Per-command timeout in seconds.
        retries (int): Number of reconnection attempts on failure.
    """

    def __init__(
        self,
        port=None,
        baudrate=None,
        fast=True,
        timeout=10.0,
        retries=3,
    ):
        self.port = port
        self.baudrate = baudrate
        self.fast = fast
        self.timeout = timeout
        self.retries = retries
        self._connection = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self):
        """Open the OBD connection.

        Raises:
            ConnectionError: When the adapter is not found or not ready.
        """
        if obd is None:
            raise ImportError(
                "python-obd is not installed. Run: pip install obd"
            )

        last_exc = None
        for attempt in range(1, self.retries + 1):
            logger.info(
                "Connecting to OBD adapter (attempt %d/%d) …", attempt, self.retries
            )
            try:
                conn = obd.OBD(
                    portstr=self.port,
                    baudrate=self.baudrate,
                    fast=self.fast,
                    timeout=self.timeout,
                )
                if conn.status() == OBDStatus.CAR_CONNECTED:
                    self._connection = conn
                    logger.info("Connected to vehicle ECU.")
                    return
                if conn.status() == OBDStatus.ELM_CONNECTED:
                    self._connection = conn
                    logger.warning(
                        "ELM327 adapter found but engine may be off (ELM_CONNECTED)."
                    )
                    return
                conn.close()
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.debug("Connection attempt %d failed: %s", attempt, exc)

            if attempt < self.retries:
                logger.info("Retrying in %s s …", _RETRY_DELAY)
                time.sleep(_RETRY_DELAY)

        raise ConnectionError(
            f"Could not connect to OBD adapter on port={self.port!r}."
            + (f" Last error: {last_exc}" if last_exc else "")
        )

    def disconnect(self):
        """Close the OBD connection if open."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            logger.info("OBD connection closed.")

    def is_connected(self):
        """Return True when a live OBD connection is open.

        Returns:
            bool: Connection state.
        """
        if self._connection is None:
            return False
        status = self._connection.status()
        return status in (OBDStatus.CAR_CONNECTED, OBDStatus.ELM_CONNECTED)

    # ------------------------------------------------------------------
    # Low-level query helpers
    # ------------------------------------------------------------------

    def query(self, command):
        """Send a single OBD command and return the response.

        Args:
            command: An ``obd.commands`` command object.

        Returns:
            obd.OBDResponse: The response from the adapter.

        Raises:
            ConnectionError: When not connected.
        """
        self._require_connection()
        response = self._connection.query(command)
        logger.debug("Query %s → %s", command.name, response.value)
        return response

    def supported_commands(self):
        """Return the set of OBD commands supported by the connected vehicle.

        Returns:
            set: Supported ``obd.commands`` objects.

        Raises:
            ConnectionError: When not connected.
        """
        self._require_connection()
        return self._connection.supported_commands

    def status(self):
        """Return the raw ``OBDStatus`` enum value.

        Returns:
            OBDStatus | None: Status, or None when not connected.
        """
        if self._connection is None:
            return None
        return self._connection.status()

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_connection(self):
        if not self.is_connected():
            raise ConnectionError(
                "Not connected. Call connect() first or use OBDScanner as a context manager."
            )
