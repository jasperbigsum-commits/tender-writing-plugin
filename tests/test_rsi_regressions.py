"""Business regressions discovered by the first bounded RSI batch."""
import unittest
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


if __name__ == "__main__":
    unittest.main()
