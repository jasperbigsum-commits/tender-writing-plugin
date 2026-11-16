"""Business regressions discovered by the first bounded RSI batch."""
import unittest
from unittest.mock import patch
from docx import Document

import test_bidflow as fixture_support

b = fixture_support.b


class RsiRegressions(unittest.TestCase):
    def setUp(self):
        self.case = fixture_support.BidflowTests(methodName="runTest")
        self.case.setUp()
        self.project = self.case.project
        self.case.fixture()

    def tearDown(self):
        self.case.tearDown()

    def add_container(self):
        outline = self.case.read("outline.json")
        for chapter in outline:
            chapter["parent_id"] = "VOLUME"
        outline.insert(0, {"id": "VOLUME", "parent_id": None, "order": 1,
                           "title": "投标响应", "requirement_ids": [], "evidence_ids": []})
        self.case.save("outline.json", outline)
        self.case.reviews()
        self.assertEqual(b.audit(self.project)["status"], "checks_complete")

    def test_submission_markdown_container_has_no_invented_placeholder(self):
        self.add_container()
        output = b.export_document(self.project, self.project / "outputs/container.md", "submission")
        text = output.read_text(encoding="utf-8")
        self.assertIn("投标响应", text)
        self.assertNotIn("【待填写正文】", text)

    def test_submission_docx_container_has_no_invented_placeholder(self):
        self.add_container()
        output = b.export_document(self.project, self.project / "outputs/container.docx", "submission")
        text = "\n".join(p.text for p in Document(output).paragraphs)
        self.assertIn("投标响应", text)
        self.assertNotIn("【待填写正文】", text)

    def test_draft_missing_leaf_keeps_placeholder_and_blocks_submission(self):
        rows = [row for row in self.case.read("draft.json") if row["chapter_id"] != "C2"]
        self.case.save("draft.json", rows)
        self.case.reviews()
        self.assertEqual(b.audit(self.project)["status"], "blocked")
        with self.assertRaises(b.BidError):
            b.export_document(self.project, self.project / "outputs/missing-final.md", "submission")
        output = b.export_document(self.project, self.project / "outputs/missing-draft.md", "draft")
        self.assertIn("【待填写正文】", output.read_text(encoding="utf-8"))

    def test_submission_rejects_content_changed_after_audit(self):
        original_audit = b.audit
        output = self.project / "outputs/changed-after-audit.md"

        def audited_then_changed(root):
            result = original_audit(root)
            drafts = self.case.read("draft.json")
            drafts[0]["content"] = "未经复核的新承诺"
            self.case.save("draft.json", drafts)
            return result

        with patch.object(b, "audit", side_effect=audited_then_changed):
            with self.assertRaises(b.BidError):
                b.export_document(self.project, output, "submission")
        self.assertFalse(output.exists())
        self.assertFalse(output.with_suffix(".md.receipt.json").exists())

    def test_submission_rejects_review_revoked_after_audit(self):
        original_audit = b.audit
        output = self.project / "outputs/revoked-review.md"

        def audited_then_revoked(root):
            result = original_audit(root)
            records = self.case.read("reviews.json")
            records[0]["status"] = "issue"
            self.case.save("reviews.json", records)
            return result

        with patch.object(b, "audit", side_effect=audited_then_revoked):
            with self.assertRaises(b.BidError):
                b.export_document(self.project, output, "submission")
        self.assertFalse(output.exists())

    def test_submission_rejects_changes_during_docx_generation(self):
        original_writer = b.write_docx
        output = self.project / "outputs/changed-during-render.docx"

        def generated_then_changed(*args):
            original_writer(*args)
            p = self.case.read("project.json")
            p["facts"]["bid_total"] = "999.00"
            self.case.save("project.json", p)

        with patch.object(b, "write_docx", side_effect=generated_then_changed):
            with self.assertRaises(b.BidError):
                b.export_document(self.project, output, "submission")
        self.assertFalse(output.exists())
        self.assertFalse(output.with_suffix(".docx.receipt.json").exists())

    def test_receipt_failure_does_not_leave_a_final_document(self):
        original_writer = b.write_json
        output = self.project / "outputs/failed-receipt.md"

        def fail_receipt(path, value):
            if path.name.endswith(".receipt.json"):
                raise OSError("injected receipt failure")
            return original_writer(path, value)

        with patch.object(b, "write_json", side_effect=fail_receipt):
            with self.assertRaises(OSError):
                b.export_document(self.project, output, "submission")
        self.assertFalse(output.exists())
        self.assertFalse(output.with_suffix(".md.receipt.json").exists())

    def test_late_existing_output_is_preserved(self):
        original_writer = b.write_json
        output = self.project / "outputs/concurrent.md"

        def competing_output(path, value):
            if path.name.endswith(".receipt.json"):
                output.write_text("另一个导出任务的文件", encoding="utf-8")
            return original_writer(path, value)

        with patch.object(b, "write_json", side_effect=competing_output):
            with self.assertRaises((b.BidError, FileExistsError)):
                b.export_document(self.project, output, "submission")
        self.assertEqual(output.read_text(encoding="utf-8"), "另一个导出任务的文件")
        self.assertFalse(output.with_suffix(".md.receipt.json").exists())

    def test_rollback_preserves_a_concurrently_replaced_receipt(self):
        original_copy = b.shutil.copyfileobj
        output = self.project / "outputs/replaced-receipt.md"
        receipt = output.with_suffix(".md.receipt.json")
        calls = 0

        def copy_then_replacement(source, target):
            nonlocal calls
            calls += 1
            if calls == 2:
                replacement = receipt.with_suffix(".replacement")
                replacement.write_text("另一个任务原子替换的回执", encoding="utf-8")
                replacement.replace(receipt)
                raise OSError("injected copy failure")
            return original_copy(source, target)

        with patch.object(b.shutil, "copyfileobj", side_effect=copy_then_replacement):
            with self.assertRaises(OSError):
                b.export_document(self.project, output, "submission")
        self.assertFalse(output.exists())
        self.assertTrue(receipt.exists(), "回滚不得删除后来者替换的文件")
        self.assertEqual(receipt.read_text(encoding="utf-8"), "另一个任务原子替换的回执")


if __name__ == "__main__":
    unittest.main()
