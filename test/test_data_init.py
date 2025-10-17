import os
import shutil
import sys
import unittest

import chromadb

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.data_init.initializer import init_vector_db


class TestDataInit(unittest.TestCase):
    def setUp(self):
        self.project_root = os.path.dirname(os.path.abspath(__file__))
        self.repo_root = os.path.dirname(self.project_root)
        self.data_dir = os.path.join(self.repo_root, "data")
        self.persist_dir = os.path.join(self.repo_root, ".chroma_test")
        if os.path.exists(self.persist_dir):
            shutil.rmtree(self.persist_dir)

    def tearDown(self):
        if os.path.exists(self.persist_dir):
            shutil.rmtree(self.persist_dir)

    def test_init_creates_collection_and_adds_docs(self):
        summary = init_vector_db(data_dir=self.data_dir, persist_dir=self.persist_dir, reset=True)
        self.assertEqual(summary["collection"], "knowledge_base")
        self.assertGreater(summary["total_chunks"], 0)
        self.assertIn("processed_files", summary)
        self.assertGreater(len(summary["processed_files"]), 0)

        # Inspect collection directly
        client = chromadb.PersistentClient(path=self.persist_dir)
        col = client.get_or_create_collection("knowledge_base")
        # Core entries
        core = col.get(where={"kb_type": "core"})
        self.assertGreater(len(core.get("ids", [])), 0)
        m = core.get("metadatas", [])[0]
        self.assertIn("source_name", m)
        self.assertEqual(m.get("kb_type"), "core")

        # Regional entries
        regional = col.get(where={"kb_type": "regional"})
        self.assertGreater(len(regional.get("ids", [])), 0)
        rm = regional.get("metadatas", [])[0]
        self.assertIn("province", rm)
        self.assertEqual(rm.get("kb_type"), "regional")


if __name__ == "__main__":
    unittest.main()