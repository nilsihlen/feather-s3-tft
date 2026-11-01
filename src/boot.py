"""Kjører før alt annet. Skjermlyset er av til code.py har tegnet noe, så konsollen ikke vises."""

import board
import supervisor

supervisor.status_bar.display = False
board.DISPLAY.brightness = 0

# Ruller tilbake en oppdatering som ikke har kvittert. Feil her skal aldri hindre oppstart.
try:
    import updater

    updater.boot_check()
except Exception as exc:
    print("boot_check feilet:", repr(exc))
