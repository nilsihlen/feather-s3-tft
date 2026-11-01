import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from guard import Guarded  # noqa: E402


class FakeScreen:
    def __init__(self):
        self.fail = False
        self.calls = []

    def show(self, data):
        if self.fail:
            raise ValueError("tegnefeil")
        self.calls.append(("show", data))

    def show_stale(self, text):
        self.calls.append(("show_stale", text))

    def show_age(self, text):
        self.calls.append(("show_age", text))

    def activate(self):
        self.calls.append(("activate",))


class GuardedTest(unittest.TestCase):
    def setUp(self):
        self.screen = FakeScreen()
        self.errors = []
        self.guard = Guarded(self.screen, lambda name, exc: self.errors.append(name))

    def test_passes_through_when_ok(self):
        self.guard.show(1)
        self.assertEqual(self.screen.calls, [("show", 1)])
        self.assertFalse(self.guard.broken)

    def test_error_is_caught_and_reported_once(self):
        self.screen.fail = True
        self.assertIsNone(self.guard.show(1))
        self.guard.show(2)
        self.assertEqual(self.errors, ["show"])
        self.assertTrue(self.guard.broken)

    def test_other_drawing_skipped_while_broken(self):
        self.screen.fail = True
        self.guard.show(1)
        self.guard.show_age("ny om 5 s")
        self.assertEqual(self.screen.calls, [])

    def test_recovers_and_restores_screen(self):
        self.screen.fail = True
        self.guard.show(1)
        self.screen.fail = False
        self.guard.show(2)
        self.assertFalse(self.guard.broken)
        self.assertEqual(self.screen.calls, [("show", 2), ("activate",)])
        self.guard.show_age("ok")
        self.assertEqual(self.screen.calls[-1], ("show_age", "ok"))

    def test_failing_fallback_does_not_raise(self):
        def bad(name, exc):
            raise RuntimeError("også feil")

        guard = Guarded(self.screen, bad)
        self.screen.fail = True
        guard.show(1)
        self.assertTrue(guard.broken)


if __name__ == "__main__":
    unittest.main()
