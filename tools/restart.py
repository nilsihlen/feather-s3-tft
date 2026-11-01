"""Starter programmet på kortet på nytt over serieporten. Auto-reload er av."""

import sys
import time

import serial
from serial.tools import list_ports

ADAFRUIT_VID = 0x239A

ports = [p.device for p in list_ports.comports() if p.vid == ADAFRUIT_VID]
if not ports:
    sys.exit("Fant ikke kortet. Trykk RST for å starte det på nytt.")

port = serial.Serial(ports[0], 115200, timeout=0.2)
port.dtr = True
port.write(b"\x03")
time.sleep(0.8)
port.write(b"\x03")
time.sleep(1)
port.write(b"\r")
time.sleep(0.8)
port.write(b"\x04")
time.sleep(0.5)
port.close()
print("Startet på nytt på", ports[0])
