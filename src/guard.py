"""Feilfangst rundt tegning: en tegnefeil skal aldri stoppe henteløkka."""


class Guarded:
    """Pakker inn et objekt slik at feil i metodene fanges og logges.

    Første feil kaller `on_error(navn, feil)`, som viser reservetekst. Mens det er feil,
    hoppes tegning over. Når en av `recover`-metodene lykkes igjen, kalles `restore`
    på objektet, så det vanlige bildet kommer tilbake.
    """

    def __init__(self, target, on_error, recover=("show", "show_stale"), restore="activate"):
        self._target = target
        self._on_error = on_error
        self._recover = recover
        self._restore = restore
        self.broken = False

    def __getattr__(self, name):
        method = getattr(self._target, name)
        if not callable(method):
            return method

        def call(*args):
            if self.broken and name not in self._recover:
                return None
            try:
                result = method(*args)
            except Exception as exc:
                print("tegning feilet:", name, repr(exc))
                if not self.broken:
                    self.broken = True
                    try:
                        self._on_error(name, exc)
                    except Exception as inner:
                        print("reservetekst feilet:", repr(inner))
                return None
            if self.broken and name in self._recover:
                self.broken = False
                try:
                    getattr(self._target, self._restore)()
                except Exception as exc:
                    print("gjenoppretting feilet:", repr(exc))
                    self.broken = True
            return result

        return call
