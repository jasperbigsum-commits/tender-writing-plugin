"""Regression tests for evidence integrity, export state and local file handling."""
from pathlib import Path
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bidflow", ROOT / "tender-writing/skills/bid-writing/scripts/bidflow.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


class BidflowTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "tmp").mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix="bidflow-test-", dir=ROOT / "tmp")
        self.folder = Path(self.tmp.name).resolve()
        self.assertTrue(self.folder.is_relative_to((ROOT / "tmp").resolve()))
        self.project = b.initialize(self.folder / "project", "示例运维项目", "示例甲公司", "whole", "2026-12-01")

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, name, value):
        b.write_json(self.project / name, value)

    def read(self, name):
        return b.read_json(self.project / name)

    def fixture(self, reviewed=True):
        tender = self.folder / "tender.md"
        tender.write_text("示例运维项目\n投标人须具备有效服务资质。\n提供监控与故障处理方案。\n报价不得超过1000元。\n", encoding="utf-8")
        company = self.folder / "company.md"
        company.write_text("示例甲公司持有服务资质，有效期至2027年12月31日。\n", encoding="utf-8")
        s1 = b.ingest(self.project, tender, "tender")
        s2 = b.ingest(self.project, company, "company")
        requirements = [
            {"id": "R1", "category": "qualification", "text": "有效服务资质", "mandatory": True,
             "score": None, "lot": "whole", "source": {"source_id": s1["id"], "locator": "line:2", "quote": "投标人须具备有效服务资质。"}},
            {"id": "R2", "category": "technical", "text": "监控与故障处理", "mandatory": True,
             "score": 20, "lot": "whole", "source": {"source_id": s1["id"], "locator": "line:3", "quote": "提供监控与故障处理方案。"}},
            {"id": "R3", "category": "price", "text": "报价限价1000元", "mandatory": True,
             "score": None, "lot": "whole", "source": {"source_id": s1["id"], "locator": "line:4", "quote": "报价不得超过1000元。"}}
        ]
        self.save("requirements.json", requirements)
        self.save("evidence.json", [{"id": "E1", "company": "示例甲公司", "kind": "certificate",
                  "status": "verified", "valid_until": "2027-12-31",
                  "source": {"source_id": s2["id"], "locator": "line:1", "quote": "示例甲公司持有服务资质，有效期至2027年12月31日。"}}])
        self.save("outline.json", [{"id": f"C{i}", "parent_id": None, "order": i, "title": title,
                                    "requirement_ids": [f"R{i}"], "evidence_ids": ["E1"] if i == 1 else []}
                                   for i, title in enumerate(["资格证明", "运维实施方案", "报价说明"], 1)])
        self.save("responses.json", [{"requirement_id": f"R{i}", "chapter_id": f"C{i}", "status": "satisfied",
                                      "text": "测试数据中已设置响应", "evidence_ids": ["E1"] if i == 1 else []} for i in range(1, 4)])
        contents = ["示例甲公司提供服务资质证明，所示有效期至2027年12月31日。",
                    "建立每日巡检记录和故障登记台账，安排值守人员识别告警、定位原因并记录恢复结果。\n\n| 工作 | 交付 |\n| --- | --- |\n| 巡检 | 每日记录 |\n| 故障处理 | 处置台账 |",
                    "本次报价为人民币300.00元，分项为3个服务单元，每单元100.00元。"]
        self.save("draft.json", [{"chapter_id": f"C{i}", "content": content, "status": "reviewed",
                                  "requirement_ids": [f"R{i}"], "evidence_ids": ["E1"] if i == 1 else [],
                                  "field_values": {"project_name": "示例运维项目", "lot": "whole"}}
                                 for i, content in enumerate(contents, 1)])
        p = self.read("project.json")
        p["facts"].update({"budget": "1000.00", "bid_total": "300.00", "line_items": [
            {"quantity": "3", "unit_price": "100.00", "amount": "300.00", "currency": "CNY"}]})
        self.save("project.json", p)
        if reviewed:
            self.reviews()
        return s1, s2

    def reviews(self):
        for kind in b.MANUAL_CHECKS:
            b.record_review(self.project, kind, "pass", "automated-test-fixture", "模拟已完成复核，仅验证状态机，不代表真实业务核验")

    def codes(self):
        return {i["code"] for i in b.audit(self.project)["issues"]}

    def test_empty_project_never_passes(self):
        self.assertEqual(b.audit(self.project)["status"], "blocked")
        self.assertIn("NO_TENDER", self.codes())
        self.assertIn("NO_REQUIREMENTS", self.codes())

    def test_native_cli_distinguishes_blocked_from_execution_error(self):
        script = ROOT / "tender-writing/skills/bid-writing/scripts/bidflow.py"
        blocked = subprocess.run([sys.executable, str(script), "audit", "--project", str(self.project)], capture_output=True)
        self.assertEqual(blocked.returncode, 2)
        self.assertTrue((self.project / "outputs/audit.json").is_file())
        error = subprocess.run([sys.executable, str(script), "status", "--project", str(self.folder / "missing")], capture_output=True)
        self.assertEqual(error.returncode, 1)

    def test_completed_fixture_and_nine_categories(self):
        self.fixture()
        result = b.audit(self.project)
        self.assertEqual(result["status"], "checks_complete")
        self.assertEqual(result["summary"]["blocker"], 0)
        self.assertEqual(len(result["categories"]), 9)

    def test_content_change_invalidates_reviews(self):
        self.fixture()
        rows = self.read("draft.json")
        rows[1]["content"] += "\n增加巡检范围。"
        self.save("draft.json", rows)
        self.assertIn("REVIEW_REQUIRED", self.codes())

    def test_original_changed_is_blocked(self):
        s1, _ = self.fixture()
        b.inside(self.project, s1["path"]).write_text("篡改原件", encoding="utf-8")
        self.assertIn("SOURCE_CHANGED", self.codes())

    def test_extracted_changed_is_blocked(self):
        s1, _ = self.fixture()
        b.write_json(b.inside(self.project, s1["extracted_path"]), {"blocks": []})
        self.assertIn("SOURCE_CHANGED", self.codes())
        self.assertIn("QUOTE_MISMATCH", self.codes())

    def test_quote_must_exist_at_exact_locator(self):
        self.fixture()
        rows = self.read("requirements.json")
        rows[0]["source"]["locator"] = "line:3"
        self.save("requirements.json", rows)
        self.assertIn("QUOTE_MISMATCH", self.codes())

    def test_wrong_role_cannot_prove_tender_requirement(self):
        _, company = self.fixture()
        rows = self.read("requirements.json")
        rows[0]["source"]["source_id"] = company["id"]
        self.save("requirements.json", rows)
        self.assertIn("SOURCE_ROLE", self.codes())

    def test_expired_evidence(self):
        self.fixture()
        rows = self.read("evidence.json")
        rows[0]["valid_until"] = "2026-11-30"
        self.save("evidence.json", rows)
        self.assertIn("EXPIRED_EVIDENCE", self.codes())

    def test_wrong_company(self):
        self.fixture()
        rows = self.read("evidence.json")
        rows[0]["company"] = "示例乙公司"
        self.save("evidence.json", rows)
        self.assertIn("WRONG_COMPANY", self.codes())

    def test_missing_validity_is_unknown(self):
        self.fixture()
        rows = self.read("evidence.json")
        rows[0]["valid_until"] = None
        self.save("evidence.json", rows)
        self.assertIn("VALIDITY_UNKNOWN", self.codes())

    def test_missing_and_unknown_response(self):
        self.fixture()
        rows = self.read("responses.json")
        rows.pop()
        rows[0]["status"] = "unknown"
        self.save("responses.json", rows)
        self.assertIn("NO_RESPONSE", self.codes())
        self.assertIn("RESPONSE_GAP", self.codes())

    def test_mapping_does_not_replace_body(self):
        self.fixture()
        rows = self.read("draft.json")
        rows[1]["requirement_ids"] = []
        self.save("draft.json", rows)
        self.assertIn("EMPTY_RESPONSE_CHAPTER", self.codes())

    def test_wrong_lot_is_blocked(self):
        self.fixture()
        rows = self.read("requirements.json")
        rows[0]["lot"] = "different-lot"
        self.save("requirements.json", rows)
        self.assertIn("WRONG_LOT", self.codes())

    def test_placeholder_blocks_submission_but_draft_exports(self):
        self.fixture()
        rows = self.read("draft.json")
        rows[1]["content"] += "【待提供：人员名单】"
        self.save("draft.json", rows)
        self.assertIn("PLACEHOLDER", self.codes())
        with self.assertRaises(b.BidError):
            b.export_document(self.project, self.project / "outputs/final.md", "submission")
        output = b.export_document(self.project, self.project / "outputs/draft.md")
        self.assertIn("工作草稿", output.read_text(encoding="utf-8"))

    def test_price_uses_decimal_and_rounding(self):
        self.fixture()
        p = self.read("project.json")
        p["facts"].update({"bid_total": "0.31", "line_items": [{"quantity": "3", "unit_price": "0.102", "amount": "0.31"}]})
        self.save("project.json", p)
        self.assertNotIn("TOTAL_MISMATCH", self.codes())
        self.assertNotIn("LINE_AMOUNT", self.codes())

    def test_over_budget_and_wrong_total(self):
        self.fixture()
        p = self.read("project.json")
        p["facts"]["bid_total"] = "1001.00"
        self.save("project.json", p)
        self.assertIn("OVER_BUDGET", self.codes())
        self.assertIn("TOTAL_MISMATCH", self.codes())

    def test_invalid_price_and_required_price(self):
        self.fixture()
        p = self.read("project.json")
        p["facts"]["bid_total"] = "NaN"
        self.save("project.json", p)
        self.assertIn("INVALID_PRICE", self.codes())
        p["facts"]["bid_total"] = None
        self.save("project.json", p)
        self.assertIn("PRICE_REQUIRED", self.codes())

    def test_anonymous_scans_titles_and_body(self):
        self.fixture()
        p = self.read("project.json")
        p["anonymous"] = True
        self.save("project.json", p)
        self.assertIn("ANONYMOUS_IDENTITY", self.codes())

    def test_declared_field_mismatch(self):
        self.fixture()
        rows = self.read("draft.json")
        rows[1]["field_values"]["lot"] = "other"
        self.save("draft.json", rows)
        self.assertIn("FIELD_MISMATCH", self.codes())

    def test_placeholder_in_title_and_master_data(self):
        self.fixture()
        p = self.read("project.json")
        p["company"] = "【待提供：投标主体】"
        self.save("project.json", p)
        rows = self.read("outline.json")
        rows[0]["title"] = "【待确定：资格章节】"
        self.save("outline.json", rows)
        issues = b.audit(self.project)["issues"]
        targets = {i["target"] for i in issues if i["code"] == "PLACEHOLDER"}
        self.assertEqual(targets, {"company", "C1"})

    def test_anonymous_project_title_can_leak_identity(self):
        self.fixture()
        p = self.read("project.json")
        p.update({"name": "示例甲公司服务方案", "anonymous": True})
        self.save("project.json", p)
        drafts = self.read("draft.json")
        drafts[0]["content"] = "所需证明材料见对应附件，当前按要求核对有效期。"
        self.save("draft.json", drafts)
        self.assertIn("ANONYMOUS_IDENTITY", self.codes())

    def test_nonfinite_score_is_rejected(self):
        self.fixture()
        rows = self.read("requirements.json")
        rows[1]["score"] = float("inf")
        self.save("requirements.json", rows)
        with self.assertRaises(b.BidError):
            b.audit(self.project)

    def test_empty_source_review_cannot_bypass(self):
        file = self.folder / "scan.txt"
        file.write_text("", encoding="utf-8")
        source = b.ingest(self.project, file, "tender")
        with self.assertRaises(b.BidError):
            b.review_source(self.project, source["id"], "test", "不能跳过空正文")
        self.assertIn("EMPTY_SOURCE", self.codes())

    def test_paths_cannot_escape_project(self):
        with self.assertRaises(b.BidError):
            b.inside(self.project, "../private.txt")
        self.fixture()
        with self.assertRaises(b.BidError):
            b.export_document(self.project, self.folder / "outside.md")

    def test_no_overwrite_and_receipt_verifiable(self):
        self.fixture()
        output = b.export_document(self.project, self.project / "outputs/final.md", "submission")
        receipt = b.read_json(output.with_suffix(".md.receipt.json"))
        self.assertEqual(receipt["sha256"], b.digest(output.read_bytes()))
        self.assertEqual(receipt["snapshot"], b.fingerprint(self.project))
        with self.assertRaises(b.BidError):
            b.export_document(self.project, output)
        with self.assertRaises(b.BidError):
            b.initialize(self.project, "duplicate")

    def test_cycle_and_duplicate_ids(self):
        self.fixture()
        rows = self.read("outline.json")
        rows[0]["parent_id"] = "C2"
        rows[1]["parent_id"] = "C1"
        self.save("outline.json", rows)
        self.assertIn("OUTLINE_CYCLE", self.codes())
        with self.assertRaises(b.BidError):
            b.export_document(self.project, self.project / "outputs/cycle.md")
        rows.append(dict(rows[0]))
        self.save("outline.json", rows)
        with self.assertRaises(b.BidError):
            b.audit(self.project)

    def test_review_not_applicable_cannot_skip_semantics(self):
        self.fixture()
        b.record_review(self.project, "semantic", "not_applicable", "test", "不能跳过语义")
        self.assertIn("REVIEW_REQUIRED", self.codes())

    def test_library_expiry_subject_and_explicit_reuse(self):
        file = self.folder / "proof.md"
        file.write_text("示例甲公司资质资料，仅供测试。", encoding="utf-8")
        library = b.library_init(self.folder / "library", "示例甲公司")
        item = b.library_add(library, file, "certificate", "运维,资质", "2026-01-01")
        results = b.library_search(library, "运维", "2026-12-01")
        self.assertTrue(results[0]["expired"])
        source = b.library_use(self.project, library, item["id"])
        self.assertEqual(source["role"], "company")
        self.assertEqual(self.read("evidence.json"), [])
        p = self.read("project.json")
        p["company"] = "其他主体"
        self.save("project.json", p)
        with self.assertRaises(b.BidError):
            b.library_use(self.project, library, item["id"])

    def test_duplicate_import_is_idempotent(self):
        source, _ = self.fixture()
        again = b.ingest(self.project, self.folder / "tender.md", "tender")
        self.assertEqual(source["id"], again["id"])
        self.assertEqual(len(self.read("sources.json")), 2)

    def test_docx_round_trip_and_basic_format(self):
        self.fixture()
        output = b.export_document(self.project, self.project / "outputs/draft.docx")
        with zipfile.ZipFile(output) as archive:
            self.assertIn("word/document.xml", archive.namelist())
            xml = archive.read("word/document.xml").decode("utf-8")
            self.assertIn("w:tbl", xml)
            self.assertIn("w:cantSplit", xml)
        parsed = b.extract(output)
        text = "\n".join(block["text"] for block in parsed["blocks"])
        self.assertIn("资格证明", text)
        self.assertIn("处置台账", text)
        self.assertTrue(any(x["locator"].startswith("table:") for x in parsed["blocks"]))
        from docx import Document
        doc = Document(output)
        self.assertEqual(doc.styles["Title"]._element.xpath(".//w:pBdr"), [])


if __name__ == "__main__":
    unittest.main()
