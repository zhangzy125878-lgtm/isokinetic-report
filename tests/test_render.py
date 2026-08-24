import unittest

from isokinetic_report.models import GaugeConfig
from isokinetic_report.render import VISUAL_BAND_KEYS, _angle, _page_layout, _visual_segment_angles


class GaugeRenderingTests(unittest.TestCase):
    def test_visual_bands_are_equal_and_symmetric(self):
        segments = _visual_segment_angles()
        widths = [theta2 - theta1 for theta1, theta2 in segments]
        self.assertEqual(VISUAL_BAND_KEYS, tuple(reversed(VISUAL_BAND_KEYS)))
        self.assertTrue(all(abs(width - widths[0]) < 1e-9 for width in widths))
        self.assertAlmostEqual((segments[3][0] + segments[3][1]) / 2, 90.0)

    def test_pointer_uses_real_threshold_intervals(self):
        config = GaugeConfig(1, "髋关节屈伸", 0.3, 0.5, 0.55, 0.6, 0.7, 0.75, 0.85, 1.3, "测试", True)
        segments = _visual_segment_angles()
        self.assertAlmostEqual(_angle(0.3, config), 200.0)
        self.assertAlmostEqual(_angle(0.6, config), segments[3][1])
        self.assertAlmostEqual(_angle(0.65, config), 90.0)
        self.assertAlmostEqual(_angle(0.7, config), segments[3][0])
        self.assertAlmostEqual(_angle(1.3, config), -20.0)

    def test_known_normal_ratios_land_in_green_band(self):
        config = GaugeConfig(1, "髋关节屈伸", 0.3, 0.5, 0.55, 0.6, 0.7, 0.75, 0.85, 1.3, "测试", True)
        green_low_angle, green_high_angle = _visual_segment_angles()[3]
        for ratio in (0.61, 0.68):
            self.assertLess(green_low_angle, _angle(ratio, config))
            self.assertLess(_angle(ratio, config), green_high_angle)
        self.assertLess(_angle(0.75, config), green_low_angle)

    def test_partial_pages_use_full_width_last_panel_and_crop(self):
        three_panels, weakness_y, crop_bottom, font_size = _page_layout(3)
        self.assertEqual(len(three_panels), 3)
        self.assertGreater(three_panels[-1][2], 0.8)
        self.assertGreater(weakness_y, 0.025)
        self.assertGreater(crop_bottom, 0)
        self.assertGreater(font_size, 7.5)


if __name__ == "__main__":
    unittest.main()
