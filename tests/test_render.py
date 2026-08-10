import unittest

from isokinetic_report.models import GaugeConfig
from isokinetic_report.render import VISUAL_BAND_KEYS, _angle, _visual_segment_angles


class GaugeRenderingTests(unittest.TestCase):
    def test_visual_bands_are_equal_and_symmetric(self):
        segments = _visual_segment_angles()
        widths = [theta2 - theta1 for theta1, theta2 in segments]
        self.assertEqual(VISUAL_BAND_KEYS, tuple(reversed(VISUAL_BAND_KEYS)))
        self.assertTrue(all(abs(width - widths[0]) < 1e-9 for width in widths))
        self.assertAlmostEqual((segments[3][0] + segments[3][1]) / 2, 90.0)

    def test_pointer_still_uses_real_ratio_scale(self):
        config = GaugeConfig(1, "髋关节屈伸", 0.3, 0.5, 0.55, 0.6, 0.7, 0.75, 0.85, 1.3, "测试", True)
        self.assertAlmostEqual(_angle(0.3, config), 200.0)
        self.assertAlmostEqual(_angle(0.8, config), 90.0)
        self.assertAlmostEqual(_angle(1.3, config), -20.0)


if __name__ == "__main__":
    unittest.main()
