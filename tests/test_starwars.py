import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

import starwars  # noqa: E402


class QuoteTests(unittest.TestCase):
    def test_ascii_only_for_terminalio_font(self):
        # Skjermfonten har bare ASCII, så æøå og typografiske tegn ville blitt bokser.
        for quote in starwars.QUOTES:
            self.assertTrue(all(32 <= ord(char) < 127 for char in quote), quote)

    def test_fits_one_scroll(self):
        for quote in starwars.QUOTES:
            self.assertLessEqual(len(quote), 60, quote)

    def test_nonempty_and_unique(self):
        self.assertTrue(all(quote.strip() for quote in starwars.QUOTES))
        self.assertEqual(len(set(starwars.QUOTES)), len(starwars.QUOTES))


if __name__ == "__main__":
    unittest.main()
