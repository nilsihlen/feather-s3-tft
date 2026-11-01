"""Navneoppslag for innloggingssiden som åpner seg selv på telefonen.

Telefonen sjekker om nettet har internett ved å hente en kjent adresse. Svarer kortet
på alle oppslag med sin egen adresse, havner sjekken hos kortet, og telefonen viser
oppsettsiden som en innloggingsside.

Virker både i CircuitPython og CPython, slik at den kan testes på PC-en.
"""

_HEADER = 12
_TYPE_A = 1
_TTL_ANSWER = b"\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x1e\x00\x04"


def dns_reply(query, address):
    """Svar på ett DNS-spørsmål, eller None når det ikke er et vanlig spørsmål.

    `address` er IPv4 som fire byte. Bare A-oppslag får svar. Telefonen faller da
    tilbake på IPv4 når den spør etter AAAA.
    """
    query = bytes(query)
    if len(query) <= _HEADER or query[2] & 0x80:
        return None
    end = _HEADER
    while end < len(query) and query[end]:
        end += query[end] + 1
    end += 1
    if end + 4 > len(query):
        return None
    answers = 1 if query[end] << 8 | query[end + 1] == _TYPE_A else 0
    reply = (
        query[:2]
        + b"\x81\x80\x00\x01"
        + bytes((0, answers))
        + b"\x00\x00\x00\x00"
        + query[_HEADER : end + 4]
    )
    if answers:
        reply += _TTL_ANSWER + bytes(address)
    return reply
