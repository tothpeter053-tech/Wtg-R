"""Tests for OBDScanner connection management."""

import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from obd_scanner.scanner import ConnectionError, OBDScanner


def _make_mock_obd_module(status_value):
    """Return a mock ``obd`` module with a canned connection status."""
    mock_obd = MagicMock()
    mock_obd.OBDStatus.CAR_CONNECTED = "car_connected"
    mock_obd.OBDStatus.ELM_CONNECTED = "elm_connected"
    mock_obd.OBDStatus.NOT_CONNECTED = "not_connected"

    mock_conn = MagicMock()
    mock_conn.status.return_value = status_value
    mock_obd.OBD.return_value = mock_conn
    return mock_obd, mock_conn


class TestOBDScannerConnect(unittest.TestCase):
    def test_connect_car_connected(self):
        mock_obd, mock_conn = _make_mock_obd_module("car_connected")
        with patch.dict("sys.modules", {"obd": mock_obd}):
            import importlib
            import obd_scanner.scanner as scanner_mod
            importlib.reload(scanner_mod)

            scanner = scanner_mod.OBDScanner(port="/dev/rfcomm0", retries=1)
            scanner.connect()
            self.assertTrue(scanner.is_connected())

    def test_connect_raises_after_retries(self):
        mock_obd, mock_conn = _make_mock_obd_module("not_connected")
        with patch.dict("sys.modules", {"obd": mock_obd}):
            import importlib
            import obd_scanner.scanner as scanner_mod
            importlib.reload(scanner_mod)

            scanner = scanner_mod.OBDScanner(port="/dev/rfcomm0", retries=2)
            with self.assertRaises(scanner_mod.ConnectionError):
                with patch("time.sleep"):  # skip real sleep
                    scanner.connect()

    def test_disconnect_clears_connection(self):
        mock_obd, mock_conn = _make_mock_obd_module("car_connected")
        with patch.dict("sys.modules", {"obd": mock_obd}):
            import importlib
            import obd_scanner.scanner as scanner_mod
            importlib.reload(scanner_mod)

            scanner = scanner_mod.OBDScanner(retries=1)
            scanner.connect()
            scanner.disconnect()
            self.assertIsNone(scanner._connection)

    def test_context_manager(self):
        mock_obd, mock_conn = _make_mock_obd_module("car_connected")
        with patch.dict("sys.modules", {"obd": mock_obd}):
            import importlib
            import obd_scanner.scanner as scanner_mod
            importlib.reload(scanner_mod)

            with scanner_mod.OBDScanner(retries=1) as scanner:
                self.assertTrue(scanner.is_connected())
            self.assertIsNone(scanner._connection)

    def test_require_connection_raises_when_not_connected(self):
        mock_obd, _ = _make_mock_obd_module("not_connected")
        with patch.dict("sys.modules", {"obd": mock_obd}):
            import importlib
            import obd_scanner.scanner as scanner_mod
            importlib.reload(scanner_mod)

            scanner = scanner_mod.OBDScanner()
            with self.assertRaises(scanner_mod.ConnectionError):
                scanner._require_connection()


if __name__ == "__main__":
    unittest.main()
