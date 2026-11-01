"""Wifi-oppsettet: lagring på kortet og tolking av skjemaet fra telefonen.

Koden får ikke skrive til CIRCUITPY mens USB er koblet til, så nett og passord
ligger i microcontroller.nvm. De overlever omstart og nye programfiler.
"""

_MAGIC = b"WIFI1"
_HEADER = len(_MAGIC) + 2
MAX_SSID = 32
MAX_PASSWORD = 63
# Uten tegn som er lette å forveksle, siden passordet også kan tastes inn for hånd.
_PASSWORD_CHARS = "abcdefghjkmnpqrstuvwxyz23456789"
_PASSWORD_LEN = 8


def setup_password(uid):
    """Passordet til kortets eget oppsettnett, ikke til noe annet nett.

    Det står på skjermen under oppsettet og er likt ved hver oppstart, så telefonen
    kobler seg til igjen uten ny skanning hvis første forsøk feiler.
    """
    value = 0
    for byte in uid:
        value = (value * 257 + byte) % 2147483647
    out = ""
    for _ in range(_PASSWORD_LEN):
        value = (value * 48271) % 2147483647
        out += _PASSWORD_CHARS[value % len(_PASSWORD_CHARS)]
    return out


def encode(ssid, password):
    ssid_bytes = ssid.encode("utf-8")
    password_bytes = password.encode("utf-8")
    if not 1 <= len(ssid_bytes) <= MAX_SSID:
        raise ValueError("ugyldig nettnavn")
    if len(password_bytes) > MAX_PASSWORD:
        raise ValueError("for langt passord")
    return (
        _MAGIC
        + bytes((len(ssid_bytes), len(password_bytes)))
        + ssid_bytes
        + password_bytes
    )


def decode(data):
    """Returnerer (ssid, passord), eller None når ingenting er lagret."""
    if bytes(data[: len(_MAGIC)]) != _MAGIC:
        return None
    ssid_len = data[len(_MAGIC)]
    password_len = data[len(_MAGIC) + 1]
    if not 1 <= ssid_len <= MAX_SSID or password_len > MAX_PASSWORD:
        return None
    end = _HEADER + ssid_len
    return (
        bytes(data[_HEADER:end]).decode("utf-8"),
        bytes(data[end:end + password_len]).decode("utf-8"),
    )


def load():
    import microcontroller

    return decode(microcontroller.nvm[0 : _HEADER + MAX_SSID + MAX_PASSWORD])


def save(ssid, password):
    import microcontroller

    data = encode(ssid, password)
    # Hele området overskrives, så et lengre, gammelt passord ikke blir liggende igjen.
    size = _HEADER + MAX_SSID + MAX_PASSWORD
    microcontroller.nvm[0:size] = data + b"\xff" * (size - len(data))


def _unquote(raw):
    """URL-dekoding som bevarer æøå og spesialtegn i passord."""
    out = bytearray()
    i = 0
    while i < len(raw):
        char = raw[i]
        if char == 0x2B:  # +
            out.append(0x20)
        elif char == 0x25 and i + 2 < len(raw):  # %
            out.append(int(bytes(raw[i + 1 : i + 3]), 16))
            i += 2
        else:
            out.append(char)
        i += 1
    return bytes(out).decode("utf-8")


def parse_form(body):
    """application/x-www-form-urlencoded til dict."""
    fields = {}
    for pair in bytes(body).split(b"&"):
        if b"=" in pair:
            key, value = pair.split(b"=", 1)
            fields[_unquote(key)] = _unquote(value)
    return fields


def escape(text):
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
