import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.geo.region import extract_province


class TestRegionExtract(unittest.TestCase):
    def test_extract_sichuan(self):
        self.assertEqual(extract_province("四川出台稳外资行动实施方案"), "四川")

    def test_extract_liaoning(self):
        self.assertEqual(extract_province("辽宁优化营商环境，支持民企参与政府采购"), "辽宁")

    def test_extract_guangxi_autonomous_region(self):
        self.assertEqual(extract_province("在广西壮族自治区开展试点工作"), "广西")

    def test_extract_beijing_city(self):
        self.assertEqual(extract_province("北京市发布政府采购新规"), "北京")

    def test_no_province(self):
        self.assertIsNone(extract_province("中央发文推动政府采购制度改革"))


if __name__ == "__main__":
    unittest.main()