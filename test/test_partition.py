import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.rag.partition import build_partition_filters


class TestPartitionFilters(unittest.TestCase):
    def test_with_province(self):
        filters = build_partition_filters("四川")
        self.assertEqual(len(filters), 3)
        self.assertEqual(filters[0]["name"], "core")
        self.assertEqual(filters[0]["where"], {"kb_type": "core"})
        self.assertEqual(filters[1]["name"], "target_region")
        self.assertEqual(filters[1]["where"], {"province": "四川"})
        self.assertEqual(filters[2]["name"], "other_regions")
        self.assertEqual(filters[2]["where"], {"kb_type": "regional"})
        self.assertEqual(filters[2]["exclude_province"], "四川")

    def test_without_province(self):
        filters = build_partition_filters(None)
        self.assertEqual(len(filters), 2)
        self.assertEqual(filters[0]["name"], "core")
        self.assertEqual(filters[0]["where"], {"kb_type": "core"})
        self.assertEqual(filters[1]["name"], "others")
        self.assertEqual(filters[1]["where"], {"kb_type": "regional"})


if __name__ == "__main__":
    unittest.main()