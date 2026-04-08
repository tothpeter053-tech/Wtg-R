"""Tests for SensorReader."""

import unittest
from unittest.mock import MagicMock

from obd_scanner.sensor_reader import SensorReadError, SensorReader


def _make_scanner(query_value=None, null=False):
    """Return a mock OBDScanner configured with a canned query response."""
    mock_scanner = MagicMock()
    mock_response = MagicMock()
    mock_response.is_null.return_value = null

    if query_value is not None:
        mock_val = MagicMock()
        mock_val.magnitude = query_value
        mock_val.u = "rpm"
        mock_response.value = mock_val
    else:
        mock_response.value = None

    mock_scanner.query.return_value = mock_response
    return mock_scanner


class TestSensorReaderResolveCommand(unittest.TestCase):
    def _make_reader_with_mock_obd(self, pid_exists=True):
        import sys
        mock_obd = MagicMock()
        if pid_exists:
            setattr(mock_obd.commands, "RPM", MagicMock(name="RPM"))
        else:
            # Make hasattr return False for unknown PID
            del mock_obd.commands.UNKNOWN_PID

        import importlib
        import unittest.mock as mock

        scanner = _make_scanner(query_value=750.0)
        with mock.patch.dict("sys.modules", {"obd": mock_obd}):
            import obd_scanner.sensor_reader as sr_mod
            importlib.reload(sr_mod)
            reader = sr_mod.SensorReader(scanner)
        return reader, mock_obd, sr_mod

    def test_resolve_known_command(self):
        import sys
        from unittest.mock import patch, MagicMock
        import importlib

        mock_obd = MagicMock()
        mock_cmd = MagicMock(name="RPM")
        mock_obd.commands.RPM = mock_cmd

        scanner = _make_scanner(query_value=750.0)
        with patch.dict("sys.modules", {"obd": mock_obd}):
            import obd_scanner.sensor_reader as sr_mod
            importlib.reload(sr_mod)
            reader = sr_mod.SensorReader(scanner)
            cmd = reader._resolve_command("RPM")
            self.assertEqual(cmd, mock_cmd)

    def test_resolve_unknown_command_raises(self):
        import importlib
        from unittest.mock import patch, MagicMock

        mock_obd = MagicMock()
        # Make commands a spec-restricted mock so hasattr returns False for unknown attrs
        mock_commands = MagicMock(spec=["RPM"])  # only RPM exists
        mock_obd.commands = mock_commands

        scanner = _make_scanner()
        with patch.dict("sys.modules", {"obd": mock_obd}):
            import obd_scanner.sensor_reader as sr_mod
            importlib.reload(sr_mod)
            reader = sr_mod.SensorReader(scanner)
            with self.assertRaises(sr_mod.SensorReadError):
                reader._resolve_command("NONEXISTENT_PID")


class TestSensorReaderRead(unittest.TestCase):
    def _reload_with_mock(self, query_value, null=False):
        import importlib
        from unittest.mock import patch, MagicMock

        mock_obd = MagicMock()
        mock_cmd = MagicMock(name="RPM")
        mock_obd.commands.RPM = mock_cmd

        scanner = _make_scanner(query_value=query_value, null=null)
        with patch.dict("sys.modules", {"obd": mock_obd}):
            import obd_scanner.sensor_reader as sr_mod
            importlib.reload(sr_mod)
            reader = sr_mod.SensorReader(scanner)
        return reader, sr_mod

    def test_read_returns_dict(self):
        reader, sr_mod = self._reload_with_mock(750.0)
        result = reader.read("RPM")
        self.assertIn("pid", result)
        self.assertIn("value", result)
        self.assertEqual(result["pid"], "RPM")
        self.assertEqual(result["value"], 750.0)

    def test_read_null_response_raises(self):
        reader, sr_mod = self._reload_with_mock(None, null=True)
        with self.assertRaises(sr_mod.SensorReadError):
            reader.read("RPM")

    def test_read_all_collects_errors(self):
        reader, sr_mod = self._reload_with_mock(None, null=True)
        results = reader.read_all(["RPM"])
        self.assertEqual(len(results), 1)
        self.assertIn("error", results[0])


if __name__ == "__main__":
    unittest.main()
