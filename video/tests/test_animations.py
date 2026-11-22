import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import animations as an


class AnimationsTest(unittest.TestCase):
    def test_trace_partiel_et_fond_transparent(self):
        image = Image.new("RGBA", (100, 100))
        an.tracer(image, [(10, 50), (50, 50), (90, 50)], .5, largeur=4)
        self.assertEqual(image.getpixel((40, 50))[3], 255)
        self.assertEqual(image.getpixel((75, 50))[3], 0)
        self.assertEqual(image.getpixel((10, 10))[3], 0)

    def test_tap_transitoire(self):
        image = Image.new("RGBA", (200, 200))
        an.tap(image, (100, 100), 0)
        an.tap(image, (100, 100), 1)
        self.assertIsNone(image.getbbox())
        an.tap(image, (100, 100), .5)
        self.assertGreater(image.getpixel((100, 100))[3], 0)
        self.assertLess(image.getpixel((100, 100))[3], 255)

    def test_progression_bornee(self):
        self.assertEqual(an.progression(0, 1, 2), 0)
        self.assertEqual(an.progression(2, 1, 2), .5)
        self.assertEqual(an.progression(4, 1, 2), 1)
