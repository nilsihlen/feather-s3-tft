import pathlib
import struct
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

import captive  # noqa: E402
import netconfig  # noqa: E402

ADDRESS = bytes((192, 168, 4, 1))


def query(name, qtype=1, flags=0x0100):
    question = b"".join(
        bytes((len(part),)) + part.encode() for part in name.split(".")
    )
    return (
        struct.pack(">HHHHHH", 0x1234, flags, 1, 0, 0, 0)
        + question
        + b"\x00"
        + struct.pack(">HH", qtype, 1)
    )


class DnsTests(unittest.TestCase):
    def test_answers_probe_host_with_own_address(self):
        q = query("captive.apple.com")
        reply = captive.dns_reply(q, ADDRESS)
        self.assertEqual(reply[:2], q[:2])
        self.assertEqual(reply[2:4], b"\x81\x80")
        self.assertEqual(struct.unpack(">H", reply[6:8])[0], 1)
        self.assertEqual(reply[12:len(q)], q[12:])
        self.assertEqual(reply[-4:], ADDRESS)

    def test_aaaa_gets_empty_answer(self):
        reply = captive.dns_reply(query("captive.apple.com", qtype=28), ADDRESS)
        self.assertEqual(struct.unpack(">H", reply[6:8])[0], 0)
        self.assertNotIn(ADDRESS, reply)

    def test_ignores_responses_and_garbage(self):
        self.assertIsNone(captive.dns_reply(query("a.no", flags=0x8180), ADDRESS))
        self.assertIsNone(captive.dns_reply(b"\x00" * 8, ADDRESS))
        self.assertIsNone(captive.dns_reply(query("a.no")[:15], ADDRESS))

    def test_accepts_bytearray_from_socket_buffer(self):
        reply = captive.dns_reply(bytearray(query("a.no")), ADDRESS)
        self.assertEqual(reply[-4:], ADDRESS)


class SetupPasswordTests(unittest.TestCase):
    UID = bytes.fromhex("42CEA423CD06")

    def test_is_stable_for_the_board(self):
        self.assertEqual(netconfig.setup_password(self.UID), netconfig.setup_password(self.UID))

    def test_differs_between_boards(self):
        other = bytes.fromhex("42CEA423CD07")
        self.assertNotEqual(netconfig.setup_password(self.UID), netconfig.setup_password(other))

    def test_is_valid_wpa_password_without_confusing_characters(self):
        password = netconfig.setup_password(self.UID)
        self.assertEqual(len(password), 8)
        self.assertFalse(set(password) & set("il1o0"))


if __name__ == "__main__":
    unittest.main()
