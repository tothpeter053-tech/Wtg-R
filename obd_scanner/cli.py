"""Click-based command-line interface for the OBD scanner."""

import logging
import sys

import click

from .bluetooth import BluetoothDiscovery
from .dtc_handler import DTCClearError, DTCHandler, DTCReadError
from .scanner import ConnectionError, OBDScanner
from .sensor_reader import COMMON_PIDS, SensorReadError, SensorReader

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    format="%(levelname)s: %(message)s",
    level=logging.WARNING,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared options
# ---------------------------------------------------------------------------

_port_option = click.option(
    "--port",
    "-p",
    default=None,
    show_default=True,
    help="Serial port for the ELM327 adapter (e.g. /dev/rfcomm0 or COM3). "
    "Auto-detected when omitted.",
)

_baud_option = click.option(
    "--baudrate",
    "-b",
    default=None,
    type=int,
    show_default=True,
    help="Baud rate. Auto-detected when omitted.",
)

_verbose_option = click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable verbose debug output.",
)


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(package_name="obd-scanner")
def cli():
    """OBD Scanner — read sensors, view error codes, and clear the Check Engine Light via Bluetooth."""


# ---------------------------------------------------------------------------
# bluetooth subcommands
# ---------------------------------------------------------------------------


@cli.group("bluetooth")
def bluetooth_group():
    """Bluetooth device discovery utilities."""


@bluetooth_group.command("scan")
def bt_scan():
    """Scan for nearby Bluetooth OBD-II adapters."""
    discovery = BluetoothDiscovery()
    click.echo("Scanning for Bluetooth devices …")
    devices = discovery.scan_bluetooth_devices()
    if not devices:
        click.echo("No Bluetooth devices found (or scan not supported on this platform).")
        return
    obd_devices = [d for d in devices if discovery.is_obd_device(d["name"])]
    others = [d for d in devices if not discovery.is_obd_device(d["name"])]
    if obd_devices:
        click.echo(f"\nFound {len(obd_devices)} OBD-II adapter(s):")
        for dev in obd_devices:
            click.echo(f"  ✔  {dev['address']}  {dev['name']}")
    click.echo(f"\n{len(others)} other device(s) found (not OBD adapters).")


@bluetooth_group.command("ports")
def bt_ports():
    """List candidate Bluetooth serial ports on this system."""
    discovery = BluetoothDiscovery()
    ports = discovery.list_ports()
    if ports:
        click.echo("Candidate Bluetooth serial ports:")
        for p in ports:
            click.echo(f"  {p}")
    else:
        click.echo("No candidate Bluetooth serial ports found.")


# ---------------------------------------------------------------------------
# sensors command
# ---------------------------------------------------------------------------


@cli.command("sensors")
@_port_option
@_baud_option
@_verbose_option
@click.option(
    "--pid",
    multiple=True,
    default=None,
    help="PID name(s) to read (repeatable). Reads all common PIDs when omitted.",
)
@click.option(
    "--list-supported",
    is_flag=True,
    default=False,
    help="List all PIDs supported by the connected vehicle and exit.",
)
def sensors_cmd(port, baudrate, verbose, pid, list_supported):
    """Read live sensor values from the vehicle ECU."""
    _apply_verbosity(verbose)
    scanner = OBDScanner(port=port, baudrate=baudrate)
    try:
        with scanner:
            reader = SensorReader(scanner)
            if list_supported:
                supported = reader.supported_pids()
                click.echo(f"Supported PIDs ({len(supported)}):")
                for name in supported:
                    click.echo(f"  {name}")
                return

            pids_to_read = list(pid) if pid else COMMON_PIDS
            click.echo(f"Reading {len(pids_to_read)} sensor(s) …\n")
            results = reader.read_all(pids_to_read)
            _print_sensor_table(results)

    except (ConnectionError, ImportError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# dtc subcommands
# ---------------------------------------------------------------------------


@cli.group("dtc")
def dtc_group():
    """Diagnostic Trouble Code (error code) commands."""


@dtc_group.command("read")
@_port_option
@_baud_option
@_verbose_option
@click.option(
    "--pending",
    is_flag=True,
    default=False,
    help="Read pending (not yet confirmed) DTCs instead of confirmed codes.",
)
@click.option(
    "--freeze",
    is_flag=True,
    default=False,
    help="Read freeze-frame DTCs.",
)
def dtc_read(port, baudrate, verbose, pending, freeze):
    """Read stored Diagnostic Trouble Codes from the ECU."""
    _apply_verbosity(verbose)
    scanner = OBDScanner(port=port, baudrate=baudrate)
    try:
        with scanner:
            handler = DTCHandler(scanner)
            if pending:
                dtcs = handler.read_pending_dtcs()
                label = "Pending DTCs"
            elif freeze:
                dtcs = handler.read_freeze_dtcs()
                label = "Freeze-Frame DTCs"
            else:
                dtcs = handler.read_dtcs()
                label = "Confirmed DTCs"

            if not dtcs:
                click.echo(f"✔  No {label.lower()} found.")
                return
            click.echo(f"{label} ({len(dtcs)} found):\n")
            _print_dtc_table(dtcs)

    except (DTCReadError, ConnectionError, ImportError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


@dtc_group.command("clear")
@_port_option
@_baud_option
@_verbose_option
@click.option(
    "--yes",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt.",
)
def dtc_clear(port, baudrate, verbose, yes):
    """Clear all stored DTCs and reset the Check Engine Light.

    \b
    WARNING: This erases all fault codes and freeze-frame data.
    Only clear codes after diagnosing and fixing the underlying issue.
    """
    _apply_verbosity(verbose)
    if not yes:
        click.confirm(
            "⚠  This will erase all DTCs and reset the Check Engine Light. Continue?",
            abort=True,
        )
    scanner = OBDScanner(port=port, baudrate=baudrate)
    try:
        with scanner:
            handler = DTCHandler(scanner)
            handler.clear_dtcs()
            click.echo("✔  All DTCs cleared and Check Engine Light reset.")

    except (DTCClearError, ConnectionError, ImportError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _print_sensor_table(results):
    col_pid = max((len(r["pid"]) for r in results), default=10)
    col_val = 15
    col_unit = 10
    header = f"{'PID':<{col_pid}}  {'VALUE':>{col_val}}  {'UNIT':<{col_unit}}"
    click.echo(header)
    click.echo("-" * len(header))
    for r in results:
        if "error" in r:
            click.echo(f"{r['pid']:<{col_pid}}  {'N/A':>{col_val}}  {'':>{col_unit}}  ← {r['error']}")
        else:
            value = f"{r['value']:.2f}" if isinstance(r["value"], float) else str(r["value"])
            unit = r["unit"] or ""
            click.echo(f"{r['pid']:<{col_pid}}  {value:>{col_val}}  {unit:<{col_unit}}")


def _print_dtc_table(dtcs):
    for dtc in dtcs:
        click.echo(f"  [{dtc['category']}]  {dtc['code']}  —  {dtc['description']}")


def _apply_verbosity(verbose):
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
