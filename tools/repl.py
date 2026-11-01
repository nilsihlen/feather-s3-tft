"""Kjører kode på kortet over serieporten, linje for linje, og leser svaret til `SLUTT` kommer."""

import re, sys, time
import serial
from serial.tools import list_ports

def port_name():
    end = time.time() + 30
    while time.time() < end:
        ports = [p.device for p in list_ports.comports() if p.vid == 0x239A]
        if ports:
            return ports[0]
        time.sleep(0.5)
    sys.exit("fant ikke kortet")

def clean(data):
    return re.sub(r"\x1b\][^\x1b]*\x1b\\", "", data.decode("utf-8", "replace"))

def repl():
    p = serial.Serial(port_name(), 115200, timeout=0.2)
    p.dtr = True
    p.write(b"\x03"); time.sleep(0.5); p.write(b"\x03"); time.sleep(1.2)
    p.write(b"\r"); time.sleep(1); p.read(8192)
    return p

def run(p, code, timeout=90):
    p.write(b"\x05"); time.sleep(0.3)
    for line in code.split("\n"):
        p.write(line.encode() + b"\r"); time.sleep(0.06); p.read(4096)
    p.write(b"\x04")
    end = time.time() + timeout; t = b""
    while time.time() < end:
        t += p.read(8192)
        if b"SLUTT" in t:
            break
    text = clean(t)
    return "\n".join(l for l in text.splitlines() if not l.startswith("==="))

def hard_reset(p):
    p.write(b"\x05"); time.sleep(0.3)
    p.write(b"import microcontroller\rmicrocontroller.reset()\r\x04")
    time.sleep(0.5)
    try:
        p.close()
    except Exception:
        pass
    time.sleep(6)
