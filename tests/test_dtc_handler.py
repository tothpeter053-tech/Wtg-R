"""Tests for DTCHandler."""

import importlib
import unittest
from unittest.mock import MagicMock, patch


def _make_scanner_with_dtcs(dtc_list=None, null=False):
    mock_scanner = MagicMock()
    mock_response = MagicMock()
    mock_response.is_null.return_value = null
    mock_response.value = dtc_list or []
    mock_scanner.query.return_value = mock_response
    return mock_scanner


def _load_dtc_handler(scanner, null=False, dtc_list=None):
    mock_obd = MagicMock()
    mock_obd.commands.GET_DTC = MagicMock(name="GET_DTC")
    mock_obd.commands.GET_CURRENT_DTC = MagicMock(name="GET_CURRENT_DTC")
    mock_obd.commands.FREEZE_DTC = MagicMock(name="FREEZE_DTC")
    mock_obd.commands.CLEAR_DTC = MagicMock(name="CLEAR_DTC")

    mock_resp = MagicMock()
    mock_resp.is_null.return_value = null
    mock_resp.value = dtc_list or []
    scanner.query.return_value = mock_resp

    with patch.dict("sys.modules", {"obd": mock_obd}):
        import obd_scanner.dtc_handler as dh_mod
        importlib.reload(dh_mod)
        handler = dh_mod.DTCHandler(scanner)
    return handler, dh_mod


class TestDTCHandlerDescribe(unittest.TestCase):
    def _get_handler(self):
        scanner = MagicMock()
        handler, _ = _load_dtc_handler(scanner)
        return handler

    def test_known_code(self):
        handler = self._get_handler()
        desc = handler.describe("P0300")
        self.assertIn("Misfire", desc)

    def test_unknown_code(self):
        handler = self._get_handler()
        desc = handler.describe("P9999")
        self.assertIn("Unknown", desc)

    def test_case_insensitive(self):
        handler = self._get_handler()
        desc_upper = handler.describe("P0300")
        desc_lower = handler.describe("p0300")
        self.assertEqual(desc_upper, desc_lower)


class TestDTCHandlerCategory(unittest.TestCase):
    def _get_handler(self):
        scanner = MagicMock()
        handler, _ = _load_dtc_handler(scanner)
        return handler

    def test_powertrain(self):
        self.assertEqual(self._get_handler().category("P0300"), "Powertrain")

    def test_body(self):
        self.assertEqual(self._get_handler().category("B1234"), "Body")

    def test_chassis(self):
        self.assertEqual(self._get_handler().category("C0000"), "Chassis")

    def test_network(self):
        self.assertEqual(self._get_handler().category("U0100"), "Network / Communication")

    def test_unknown(self):
        self.assertEqual(self._get_handler().category(""), "Unknown")


class TestDTCHandlerRead(unittest.TestCase):
    def test_read_dtcs_returns_list(self):
        scanner = MagicMock()
        handler, dh_mod = _load_dtc_handler(
            scanner,
            dtc_list=[("P0300", "Random/Multiple Cylinder Misfire Detected")],
        )
        dtcs = handler.read_dtcs()
        self.assertEqual(len(dtcs), 1)
        self.assertEqual(dtcs[0]["code"], "P0300")
        self.assertEqual(dtcs[0]["category"], "Powertrain")

    def test_read_dtcs_null_raises(self):
        scanner = MagicMock()
        handler, dh_mod = _load_dtc_handler(scanner, null=True)
        with self.assertRaises(dh_mod.DTCReadError):
            handler.read_dtcs()

    def test_read_empty_returns_empty_list(self):
        scanner = MagicMock()
        handler, _ = _load_dtc_handler(scanner, dtc_list=[])
        dtcs = handler.read_dtcs()
        self.assertEqual(dtcs, [])


class TestDTCHandlerClear(unittest.TestCase):
    def test_clear_success(self):
        scanner = MagicMock()
        mock_resp = MagicMock()
        mock_resp.is_null.return_value = False
        scanner.query.return_value = mock_resp

        mock_obd = MagicMock()
        mock_obd.commands.CLEAR_DTC = MagicMock()
        with patch.dict("sys.modules", {"obd": mock_obd}):
            import obd_scanner.dtc_handler as dh_mod
            importlib.reload(dh_mod)
            handler = dh_mod.DTCHandler(scanner)
            result = handler.clear_dtcs()
        self.assertTrue(result)

    def test_clear_null_raises(self):
        scanner = MagicMock()
        mock_resp = MagicMock()
        mock_resp.is_null.return_value = True
        scanner.query.return_value = mock_resp

        mock_obd = MagicMock()
        mock_obd.commands.CLEAR_DTC = MagicMock()
        with patch.dict("sys.modules", {"obd": mock_obd}):
            import obd_scanner.dtc_handler as dh_mod
            importlib.reload(dh_mod)
            handler = dh_mod.DTCHandler(scanner)
            with self.assertRaises(dh_mod.DTCClearError):
                handler.clear_dtcs()


if __name__ == "__main__":
    unittest.main()
