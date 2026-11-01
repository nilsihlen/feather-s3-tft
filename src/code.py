"""Starter app.py. Sone 0: endres aldri over nett.

En feil som stopper app.py, også en syntaksfeil i en ny versjon, gir omstart, så
updater.boot_check() i boot.py kan telle og rulle tilbake.
"""

import time

import microcontroller

try:
    import app  # noqa: F401
except Exception as exc:
    print("app feilet:", repr(exc))
    time.sleep(10)
    microcontroller.reset()
