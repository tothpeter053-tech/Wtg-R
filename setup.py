"""Setup configuration for obd-scanner."""

from setuptools import find_packages, setup

setup(
    name="obd-scanner",
    version="0.1.0",
    description="OBD-II scanner: Bluetooth sensor reader and DTC error code cleaner",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    packages=find_packages(exclude=["tests*"]),
    python_requires=">=3.8",
    install_requires=[
        "obd>=0.7.1",
        "pyserial>=3.5",
        "click>=8.1.7",
    ],
    entry_points={
        "console_scripts": [
            "obd-scanner=obd_scanner.cli:cli",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Embedded Systems",
        "Topic :: System :: Hardware :: Hardware Drivers",
    ],
)
