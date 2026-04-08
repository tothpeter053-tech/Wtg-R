"""Tests for bluetooth discovery module."""

import sys
import unittest
from unittest.mock import MagicMock, patch

from obd_scanner.bluetooth import BluetoothDiscovery


class TestBluetoothDiscovery(unittest.TestCase):
    def setUp(self):
        self.discovery = BluetoothDiscovery()

    # ------------------------------------------------------------------
    # is_obd_device
    # ------------------------------------------------------------------

    def test_is_obd_device_elm327(self):
        self.assertTrue(self.discovery.is_obd_device("ELM327 Bluetooth"))

    def test_is_obd_device_obd(self):
        self.assertTrue(self.discovery.is_obd_device("OBD2 Scanner"))

    def test_is_obd_device_obdii_lowercase(self):
        self.assertTrue(self.discovery.is_obd_device("obdii adapter"))

    def test_is_obd_device_vlink(self):
        self.assertTrue(self.discovery.is_obd_device("V-LINK"))

    def test_is_obd_device_unrelated(self):
        self.assertFalse(self.discovery.is_obd_device("AirPods Pro"))

    def test_is_obd_device_empty(self):
        self.assertFalse(self.discovery.is_obd_device(""))

    # ------------------------------------------------------------------
    # list_ports — Linux
    # ------------------------------------------------------------------

    def test_list_ports_linux(self):
        self.discovery._platform = "linux"
        with patch("glob.glob") as mock_glob:
            mock_glob.side_effect = lambda p: [p.replace("*", "0")] if "rfcomm" in p else []
            ports = self.discovery.list_ports()
        self.assertIn("/dev/rfcomm0", ports)

    def test_list_ports_no_match(self):
        self.discovery._platform = "linux"
        with patch("glob.glob", return_value=[]):
            ports = self.discovery.list_ports()
        self.assertEqual(ports, [])

    def test_list_ports_unknown_platform(self):
        self.discovery._platform = "freebsd"
        ports = self.discovery.list_ports()
        self.assertEqual(ports, [])

    # ------------------------------------------------------------------
    # scan_bluetooth_devices — graceful failure
    # ------------------------------------------------------------------

    def test_scan_returns_empty_on_exception(self):
        self.discovery._platform = "linux"
        with patch("subprocess.run", side_effect=FileNotFoundError("hcitool not found")):
            result = self.discovery.scan_bluetooth_devices()
        self.assertEqual(result, [])

    def test_scan_returns_empty_on_unsupported_platform(self):
        self.discovery._platform = "win32"
        result = self.discovery.scan_bluetooth_devices()
        self.assertEqual(result, [])

    # ------------------------------------------------------------------
    # _scan_linux parsing
    # ------------------------------------------------------------------

    def test_scan_linux_parses_output(self):
        self.discovery._platform = "linux"
        fake_output = "Scanning ...\n\t00:1A:7D:DA:71:13\tELM327 v1.5\n\t11:22:33:44:55:66\tSome Phone\n"
        mock_result = MagicMock()
        mock_result.stdout = fake_output
        with patch("subprocess.run", return_value=mock_result):
            devices = self.discovery._scan_linux()
        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0]["name"], "ELM327 v1.5")


if __name__ == "__main__":
    unittest.main()
