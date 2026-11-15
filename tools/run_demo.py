"""Run a synthetic end-to-end local fixture, without model calls or review bypasses."""
import argparse
import importlib.util
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "tender-writing"
spec = importlib.util.spec_from_file_location("bidflow", PLUGIN / "skills/bid-writing/scripts/bidflow.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


def run(destination):
    project = b.initialize(destination, "示例运维项目", "示例甲公司", "whole", "2026-12-01")
    tender = b.ingest(project, PLUGIN / "examples/tender.md", "tender")
    company = b.ingest(project, PLUGIN / "examples/company.md", "company")
    blocks = b.read_json(project / tender["extracted_path"])["blocks"]
    clauses = [(row["locator"], row["text"]) for row in blocks if row["text"].startswith(("投标人须", "技术方案须", "服务报价", "投标文件应"))]
    titles = ["资格与证明材料", "运维实施方案", "服务报价", "编制要求响应"]
    categories = ["qualification", "technical", "price", "format"]
    evidence_block = next(row for row in b.read_json(project / company["extracted_path"])["blocks"] if row["text"].startswith("示例甲公司持有"))
    requirements, outline, responses, drafts = [], [], [], []
    contents = [
        "示例甲公司提供示例运维服务资质，有效期至2027年12月31日。此处使用的证明为插件验收样本。",
        "服务按巡检、告警处置和恢复验证组织。每日检查服务可用性并填写巡检记录；发现告警后登记影响范围、分析原因，按处理步骤恢复并核对结果。交付巡检记录、故障台账和服务总结。\n\n| 工作内容 | 交付材料 |\n| --- | --- |\n| 每日巡检 | 巡检记录 |\n| 告警处置 | 故障台账 |\n| 恢复验证 | 验证结果 |",
        "服务总价为人民币500.00元。报价分为5个服务单元，每个单元100.00元，合计500.00元。",
        "本文件使用分级标题组织正文，按要求逐项提供响应。当前为工作草稿，后续按最终附件与版式核验结果更新。"
    ]
    for i, (locator, text) in enumerate(clauses, 1):
        rid, cid = f"R{i:04d}", f"C{i:04d}"
        eids = ["E0001"] if i == 1 else []
        requirements.append({"id": rid, "category": categories[i - 1], "text": text,
                             "mandatory": True, "score": None, "lot": "whole",
                             "source": {"source_id": tender["id"], "locator": locator, "quote": text}})
        outline.append({"id": cid, "parent_id": None, "order": i, "title": titles[i - 1], "requirement_ids": [rid], "evidence_ids": eids})
        responses.append({"requirement_id": rid, "status": "satisfied", "chapter_id": cid,
                          "evidence_ids": eids, "text": "此人工构造样本设置了对应正文；尚未登记最终专项核验。"})
        drafts.append({"chapter_id": cid, "content": contents[i - 1], "status": "draft",
                       "requirement_ids": [rid], "evidence_ids": eids,
                       "field_values": {"project_name": "示例运维项目", "lot": "whole"}})
    for name, rows in (("requirements", requirements), ("outline", outline), ("responses", responses), ("draft", drafts)):
        b.write_json(project / f"{name}.json", rows)
    b.write_json(project / "evidence.json", [{"id": "E0001", "company": "示例甲公司", "kind": "certificate",
        "status": "verified", "valid_until": "2027-12-31", "claims": ["人工构造的示例资质"],
        "source": {"source_id": company["id"], "locator": evidence_block["locator"], "quote": evidence_block["text"]}}])
    metadata = b.read_json(project / "project.json")
    metadata["facts"].update({"budget": "1000.00", "bid_total": "500.00", "line_items": [{"quantity": "5", "unit_price": "100.00", "amount": "500.00"}]})
    b.write_json(project / "project.json", metadata)
    result = b.audit(project)
    b.write_json(project / "outputs/audit.json", result)
    (project / "outputs/audit.md").write_text(b.markdown_report(result), encoding="utf-8")
    (project / "outputs/response-matrix.md").write_text(b.response_matrix(project), encoding="utf-8")
    b.export_document(project, project / "outputs/示例投标文件_草稿.docx")
    b.export_document(project, project / "outputs/示例投标文件_草稿.md")
    print(json.dumps({"project": str(project), "audit": result["status"], "summary": result["summary"],
                      "note": "预期保留8个复核阻断项；没有替代实际复核，不是真实投标成品。"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "tmp/demo"))
    run(Path(parser.parse_args().out).resolve())
