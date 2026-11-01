"""Kjører før alt annet. Skjermlyset er av til code.py har tegnet noe, så konsollen ikke vises."""

import board
import supervisor

supervisor.status_bar.display = False
board.DISPLAY.brightness = 0
