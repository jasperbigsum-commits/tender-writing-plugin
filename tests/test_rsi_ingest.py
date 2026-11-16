"""Source recovery and immutable ingestion regressions for RSI round three."""
import unittest
from unittest.mock import patch

import test_bidflow as fixture_support

b = fixture_support.b


class RsiIngestRegressions(unittest.TestCase):
    def setUp(self):
        self.case = fixture_support.BidflowTests(methodName="runTest")
        self.case.setUp()
        self.project = self.case.project
        self.source, _ = self.case.fixture()

    def tearDown(self):
        self.case.tearDown()

    def test_reimport_restores_corrupted_original_and_invalidates_reviews(self):
        stored = b.inside(self.project, self.source["path"])
        stored.write_text("损坏的副本", encoding="utf-8")
        self.assertIn("SOURCE_CHANGED", self.case.codes())
        restored = b.ingest(self.project, self.case.folder / "tender.md", "tender")
        self.assertEqual(restored["id"], self.source["id"])
        self.assertEqual(b.digest(stored.read_bytes()), self.source["sha256"])
        self.assertNotIn("SOURCE_CHANGED", self.case.codes())
        self.assertIn("REVIEW_REQUIRED", self.case.codes())
        self.assertIsNone(restored["review"])
        self.case.reviews()
        self.assertEqual(b.audit(self.project)["status"], "checks_complete")

    def test_reimport_rebuilds_missing_or_changed_extraction(self):
        stored = b.inside(self.project, self.source["extracted_path"])
        for damage in ("missing", "changed"):
            with self.subTest(damage=damage):
                if damage == "missing":
                    stored.unlink()
                else:
                    b.write_json(stored, {"blocks": [{"locator": "line:1", "text": "错误抽取"}]})
                restored = b.ingest(self.project, self.case.folder / "tender.md", "tender")
                self.assertEqual(restored["id"], self.source["id"])
                self.assertNotIn("SOURCE_CHANGED", self.case.codes())
                self.assertIn("REVIEW_REQUIRED", self.case.codes())
                self.assertEqual(len(self.case.read("sources.json")), 2)

    def test_intact_reimport_preserves_current_review_snapshot(self):
        before = b.fingerprint(self.project)
        again = b.ingest(self.project, self.case.folder / "tender.md", "tender")
        self.assertEqual(again, self.source)
        self.assertEqual(before, b.fingerprint(self.project))
        self.assertEqual(b.audit(self.project)["status"], "checks_complete")

    def test_repair_keeps_corrupt_copy_as_project_local_history(self):
        stored = b.inside(self.project, self.source["path"])
        corrupted = "留待排查的损坏副本".encode("utf-8")
        stored.write_bytes(corrupted)
        restored = b.ingest(self.project, self.case.folder / "tender.md", "tender")
        backup_relative = restored["repairs"][-1]["backups"]["path"]
        backup = b.inside(self.project, backup_relative)
        self.assertEqual(backup.read_bytes(), corrupted)
        self.assertTrue(backup.is_relative_to(self.project / "sources/repair-history"))

    def test_interrupted_repair_remains_blocked_and_resumes_on_reimport(self):
        stored = b.inside(self.project, self.source["path"])
        stored.write_text("损坏的副本", encoding="utf-8")
        original_write = b.write_bytes

        def interrupt_restore(path, value):
            if path == stored:
                raise OSError("injected restore interruption")
            return original_write(path, value)

        with patch.object(b, "write_bytes", side_effect=interrupt_restore):
            with self.assertRaises(OSError):
                b.ingest(self.project, self.case.folder / "tender.md", "tender")
        self.assertIn("SOURCE_REPAIR_PENDING", self.case.codes())
        self.assertIn("REVIEW_REQUIRED", self.case.codes())
        restored = b.ingest(self.project, self.case.folder / "tender.md", "tender")
        self.assertFalse(restored["repair_pending"])
        self.assertNotIn("SOURCE_REPAIR_PENDING", self.case.codes())
        self.assertNotIn("SOURCE_CHANGED", self.case.codes())
        self.assertIn("REVIEW_REQUIRED", self.case.codes())

    def test_project_import_parses_the_archived_snapshot(self):
        incoming = self.case.folder / "changing.md"
        incoming.write_text("导入起点的内容", encoding="utf-8")
        original_data = incoming.read_bytes()
        original_extract = b.extract

        def change_input_then_parse(path):
            incoming.write_text("解析时被外部修改的内容", encoding="utf-8")
            return original_extract(path)

        with patch.object(b, "extract", side_effect=change_input_then_parse):
            source = b.ingest(self.project, incoming, "tender")
        archived = b.inside(self.project, source["path"]).read_bytes()
        extracted = b.read_json(b.inside(self.project, source["extracted_path"]))
        self.assertEqual(archived, original_data)
        self.assertEqual(extracted["blocks"][0]["text"], "导入起点的内容")

    def test_library_import_hash_and_extraction_share_one_snapshot(self):
        incoming = self.case.folder / "library-changing.md"
        incoming.write_text("原始资料库版本", encoding="utf-8")
        original_data = incoming.read_bytes()
        library = b.library_init(self.case.folder / "library", "示例甲公司")
        original_extract = b.extract

        def change_input_then_parse(path):
            incoming.write_text("解析时变更的资料", encoding="utf-8")
            return original_extract(path)

        with patch.object(b, "extract", side_effect=change_input_then_parse):
            item = b.library_add(library, incoming, "module")
        archived = b.inside(library, item["path"]).read_bytes()
        extracted = b.read_json(library / "extracted" / f"{item['id']}.json")
        self.assertEqual(archived, original_data)
        self.assertEqual(b.digest(archived), item["sha256"])
        self.assertEqual(extracted["blocks"][0]["text"], "原始资料库版本")


if __name__ == "__main__":
    unittest.main()
