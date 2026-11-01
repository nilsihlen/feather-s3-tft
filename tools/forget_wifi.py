"""Sletter lagret wifi fra kortet, så det går rett til QR-koden ved neste oppstart.

Bruk: python tools/forget_wifi.py
Skriver aldri ut passordet. Kortet starter på nytt og viser oppsettet.
"""

import sys
import time

import serial
from serial.tools import list_ports

ADAFRUIT_VID = 0x239A
NVM_BYTES = 110


def open_port(timeout_s=25):
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        ports = [p.device for p in list_ports.comports() if p.vid == ADAFRUIT_VID]
        if ports:
            try:
                port = serial.Serial(ports[0], 115200, timeout=0.2)
                port.dtr = True
                return port
            except serial.SerialException:
                pass
        time.sleep(0.5)
    sys.exit("Fant ikke kortet. Er det koblet til PC-en med en datakabel?")


def read_for(port, seconds, until=None):
    end = time.monotonic() + seconds
    data = b""
    while time.monotonic() < end:
        data += port.read(2000)
        if until and until in data:
            break
    return data


def main():
    port = open_port()
    port.write(b"\x03")
    time.sleep(0.8)
    port.write(b"\x03")
    time.sleep(1.2)
    port.read(4000)
    port.write(b"\r")
    time.sleep(1)
    port.read(2000)

    commands = (
        "import microcontroller, netconfig",
        "microcontroller.nvm[0:%d] = b'\\xff' * %d" % (NVM_BYTES, NVM_BYTES),
        "print('ETTER', netconfig.load())",
    )
    for command in commands:
        port.write(command.encode() + b"\r")
        time.sleep(0.5)
    if b"ETTER None" not in read_for(port, 3, b"ETTER None"):
        sys.exit("Klarte ikke å bekrefte at wifi er slettet. Kortet er ikke startet på nytt.")

    port.write(b"microcontroller.reset()\r")
    time.sleep(1)
    port.close()

    port = open_port()
    if b"oppsett:" in read_for(port, 25, b"oppsett:"):
        print("Wifi er slettet, og kortet viser QR-koden.")
    else:
        print("Wifi er slettet, men oppsettet ble ikke bekreftet. Sjekk skjermen.")
    port.close()


main()
