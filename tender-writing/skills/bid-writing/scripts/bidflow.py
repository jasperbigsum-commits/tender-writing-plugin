#!/usr/bin/env python3
"""Local, evidence-linked bid workspace. No network calls or model API keys."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from difflib import SequenceMatcher
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import tempfile
from uuid import uuid4
import zipfile

VERSION = "0.1.0"
STATE_FILES = ("project.json", "sources.json", "requirements.json", "evidence.json",
               "outline.json", "responses.json", "draft.json")
CATEGORIES = ("coverage", "qualification", "consistency", "response", "scoring",
              "format", "price", "traceability", "similarity")
MANUAL_CHECKS = ("semantic", "format", "signature", "similarity")
SOURCE_ROLES = ("tender", "amendment", "company", "history", "bid")
REQ_CATEGORIES = ("qualification", "technical", "commercial", "format", "price",
                  "submission", "scoring")
PLACEHOLDER = re.compile(r"【待[^】]*】|\{\{[^}]+\}\}|\b(?:TODO|TBD|XXX)\b", re.I)


class BidError(Exception):
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def write_json(path, value):
    """Atomic replace in the same directory; do not leave half-written state."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     suffix=".tmp", delete=False, newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        tmp = Path(stream.name)
    try:
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise BidError(f"无法读取 JSON {path}: {exc}") from exc


def inside(root, relative):
    """Resolve persisted paths and reject absolute paths, traversal and symlinks out."""
    path = (Path(root) / relative).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise BidError(f"路径超出项目目录: {relative}")
    return path


def project_dir(path):
    path = Path(path).resolve()
    if not (path / "project.json").is_file():
        raise BidError(f"项目不存在，请先 init: {path}")
    return path


def initialize(path, name, company="", lot="", as_of=None):
    path = Path(path).resolve()
    if not name.strip():
        raise BidError("项目名称不能为空")
    if path.exists() and any(path.iterdir()):
        raise BidError("项目目录非空；请使用新的目录，避免覆盖已有文件")
    check_date(as_of or date.today().isoformat())
    path.mkdir(parents=True, exist_ok=True)
    write_json(path / "project.json", {
        "schema_version": "1.0", "id": str(uuid4()), "name": name,
        "company": company, "lot": lot, "as_of_date": as_of or date.today().isoformat(),
        "created_at": now(), "facts": {"tender_number": "", "currency": "CNY",
        "budget": None, "bid_total": None, "line_items": []},
        "anonymous": False, "identity_terms": [],
        "format": {"font": "宋体", "font_size_pt": 12, "margin_cm": 2.5}
    })
    for filename in STATE_FILES[1:]:
        write_json(path / filename, [])
    write_json(path / "reviews.json", [])
    return path


def check_date(value):
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError()
        return parsed
    except (ValueError, TypeError) as exc:
        raise BidError(f"日期须为 YYYY-MM-DD: {value}") from exc


def extract(path):
    path = Path(path)
    suffix = path.suffix.lower()
    warnings = []
    blocks = []
    if suffix in (".txt", ".md"):
        try:
            content = path.read_text(encoding="utf-8-sig")
        except UnicodeError as exc:
            raise BidError("文本文件须为 UTF-8，请先转换编码") from exc
        blocks = [{"locator": f"line:{i}", "text": text.strip()}
                  for i, text in enumerate(content.splitlines(), 1) if text.strip()]
    elif suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise BidError("PDF 解析需要 pypdf；请安装插件 requirements.txt") from exc
        reader = PdfReader(path)
        if reader.is_encrypted:
            raise BidError("加密 PDF 请先提供有权解密的可读副本")
        for i, page in enumerate(reader.pages, 1):
            text = (page.extract_text() or "").strip()
            blocks.append({"locator": f"page:{i}", "text": text})
            if not text:
                warnings.append(f"第 {i} 页无文本层，需 OCR 并逐页核对")
        warnings.append("PDF 文本顺序、表格、图示和扫描图像需对照原页核对")
    elif suffix == ".docx":
        try:
            from docx import Document
            from docx.table import Table
            from docx.text.paragraph import Paragraph
        except ImportError as exc:
            raise BidError("Word 解析需要 python-docx；请安装插件 requirements.txt") from exc
        doc = Document(path)
        p_count = t_count = 0
        for child in doc.element.body:
            tag = child.tag.rsplit("}", 1)[-1]
            if tag == "p":
                p_count += 1
                text = Paragraph(child, doc).text.strip()
                if text:
                    blocks.append({"locator": f"paragraph:{p_count}", "text": text})
            elif tag == "tbl":
                t_count += 1
                for r, row in enumerate(Table(child, doc).rows, 1):
                    blocks.append({"locator": f"table:{t_count}:row:{r}",
                                   "text": " | ".join(c.text for c in row.cells)})
        # Word paragraph numbers are extraction anchors, never physical page numbers.
        xml = doc.element.xml
        if any(token in xml for token in ("<w:ins ", "<w:del ", "<w:txbxContent", "<w:drawing", "<w:object")):
            warnings.append("检测到修订、文本框、图像或嵌入对象，须查看原件补充识别")
        if any(s.header.paragraphs[0].text or s.footer.paragraphs[0].text for s in doc.sections):
            warnings.append("存在页眉页脚；当前正文抽取未包含这些内容，须核对原件")
        warnings.append("Word 表格结构、合并单元格和分页需查看原件核对")
    else:
        raise BidError("支持 UTF-8 TXT/Markdown、DOCX、带文本层 PDF；旧 DOC/图片请先转换或 OCR")
    if not any(block["text"].strip() for block in blocks):
        warnings.append("未提取到正文，禁止据此生成完整性结论")
    return {"format": suffix[1:], "blocks": blocks, "warnings": warnings}


def ingest(root, file, role):
    root = project_dir(root)
    file = Path(file).resolve(strict=True)
    if not file.is_file() or file.stat().st_size > 100 * 1024 * 1024:
        raise BidError("请输入不超过 100 MiB 的单个文件；大文件请按有序分卷导入")
    if role not in SOURCE_ROLES:
        raise BidError("未知资料用途")
    data = file.read_bytes()
    sources = read_json(root / "sources.json")
    file_hash = digest(data)
    existing = next((s for s in sources if s["sha256"] == file_hash and s["role"] == role), None)
    if existing:
        return existing
    # Parse before copying or registering so unsupported/corrupt files leave no record.
    extracted = extract(file)
    source_id = f"S{max([int(s['id'][1:]) for s in sources] or [0]) + 1:04d}"
    original = f"sources/originals/{source_id}{file.suffix.lower()}"
    extracted_path = f"sources/extracted/{source_id}.json"
    extracted.update({"source_id": source_id, "original_name": file.name})
    target = inside(root, original)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    write_json(inside(root, extracted_path), extracted)
    source = {"id": source_id, "name": file.name, "role": role, "path": original,
              "sha256": file_hash, "extracted_path": extracted_path,
              "extracted_sha256": digest(inside(root, extracted_path).read_bytes()),
              "imported_at": now(), "review": None}
    sources.append(source)
    write_json(root / "sources.json", sources)
    return source


def library_init(path, company):
    path = Path(path).resolve()
    if not company.strip():
        raise BidError("企业名称不能为空")
    if path.exists() and any(path.iterdir()):
        raise BidError("资料库目录非空，请使用新的目录")
    write_json(path / "library.json", {"schema_version": "1.0", "company": company, "items": []})
    return path


def load_library(path):
    path = Path(path).resolve()
    data = read_json(path / "library.json")
    if not isinstance(data, dict) or data.get("schema_version") != "1.0" or not isinstance(data.get("company"), str) or not isinstance(data.get("items"), list):
        raise BidError("企业资料库格式错误")
    return path, data


def library_add(path, file, kind, tags="", valid_until=None):
    path, data = load_library(path)
    if valid_until:
        check_date(valid_until)
    file = Path(file).resolve(strict=True)
    if not file.is_file() or file.stat().st_size > 100 * 1024 * 1024:
        raise BidError("请输入不超过 100 MiB 的文件")
    file_hash = digest(file.read_bytes())
    existing = next((item for item in data["items"] if item["sha256"] == file_hash), None)
    if existing:
        return existing
    extracted = extract(file)
    item_id = f"L{len(data['items']) + 1:04d}"
    relative = f"originals/{item_id}{file.suffix.lower()}"
    target = inside(path, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(file.read_bytes())
    write_json(path / "extracted" / f"{item_id}.json", extracted)
    item = {"id": item_id, "name": file.name, "company": data["company"], "kind": kind,
            "tags": [t.strip() for t in tags.split(",") if t.strip()], "valid_until": valid_until,
            "sha256": file_hash, "path": relative, "imported_at": now(),
            "note": "入库不代表当前项目可用；复用时须核对主体、范围、有效期和原文"}
    data["items"].append(item)
    write_json(path / "library.json", data)
    return item


def library_search(path, query="", as_of=None):
    _, data = load_library(path)
    when = check_date(as_of or date.today().isoformat())
    terms = query.casefold().split()
    results = []
    for item in data["items"]:
        text = " ".join([item["name"], item["kind"], *item["tags"]]).casefold()
        if not terms or all(t in text for t in terms):
            results.append({**item, "expired": bool(item.get("valid_until") and check_date(item["valid_until"]) < when)})
    return results


def library_use(root, library, item_id):
    root = project_dir(root)
    path, data = load_library(library)
    if data["company"] != read_json(root / "project.json")["company"]:
        raise BidError("企业资料库主体与投标主体不一致")
    item = next((i for i in data["items"] if i["id"] == item_id), None)
    if not item:
        raise BidError("资料条目不存在")
    file = inside(path, item["path"])
    if digest(file.read_bytes()) != item["sha256"]:
        raise BidError("资料库原件已变化，请核对版本后重新入库")
    return ingest(root, file, "history" if item["kind"] == "module" else "company")


def load_state(root):
    state = {name: read_json(root / name) for name in STATE_FILES}
    validate_shape(state)
    return state


def validate_shape(state):
    project = state["project.json"]
    if not isinstance(project, dict) or project.get("schema_version") != "1.0":
        raise BidError("project.json 须为 schema_version=1.0 的对象")
    for key in ("name", "company", "lot", "as_of_date"):
        if not isinstance(project.get(key), str):
            raise BidError(f"project.{key} 须为字符串")
    check_date(project["as_of_date"])
    if not isinstance(project.get("facts"), dict) or not isinstance(project.get("format"), dict):
        raise BidError("project.facts 和 project.format 须为对象")
    if not isinstance(project.get("anonymous"), bool):
        raise BidError("project.anonymous 须为布尔值")
    if not isinstance(project.get("identity_terms"), list) or any(not isinstance(t, str) or not t.strip() for t in project["identity_terms"]):
        raise BidError("project.identity_terms 须为非空字符串数组")
    identities = {
        "sources.json": "id", "requirements.json": "id", "evidence.json": "id",
        "outline.json": "id", "responses.json": "requirement_id", "draft.json": "chapter_id"
    }
    for name, field in identities.items():
        rows = state[name]
        if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
            raise BidError(f"{name} 须为对象数组")
        ids = [r.get(field) for r in rows]
        if any(not isinstance(i, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", i) for i in ids):
            raise BidError(f"{name} 的 {field} 须为字母数字下划线或连字符组成的非空标识")
        if len(ids) != len(set(ids)):
            raise BidError(f"{name} 出现重复 {field}")
    for req in state["requirements.json"]:
        if req.get("category") not in REQ_CATEGORIES or not isinstance(req.get("mandatory"), bool):
            raise BidError(f"要求 {req['id']} 的 category/mandatory 无效")
        if not isinstance(req.get("text"), str) or not req["text"].strip():
            raise BidError(f"要求 {req['id']} 缺少正文")
        if not isinstance(req.get("lot"), str):
            raise BidError(f"要求 {req['id']} 的 lot 须为字符串")
        score = req.get("score")
        if score is not None and (isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or score < 0):
            raise BidError(f"要求 {req['id']} 的 score 无效")
    for name in ("outline.json", "responses.json", "draft.json"):
        for row in state[name]:
            for field in ("requirement_ids", "evidence_ids"):
                if field in row and (not isinstance(row[field], list) or any(not isinstance(i, str) for i in row[field])):
                    raise BidError(f"{name} 的 {field} 须为字符串数组")
    for row in state["outline.json"]:
        if not isinstance(row.get("title"), str) or not row["title"].strip():
            raise BidError(f"章节 {row['id']} 缺少标题")
        if row.get("parent_id") is not None and not isinstance(row["parent_id"], str):
            raise BidError(f"章节 {row['id']} 的 parent_id 无效")
        if isinstance(row.get("order"), bool) or not isinstance(row.get("order"), int):
            raise BidError(f"章节 {row['id']} 的 order 须为整数")
    for row in state["responses.json"]:
        if row.get("status") not in ("satisfied", "partial", "deviation", "missing", "unknown"):
            raise BidError(f"响应 {row['requirement_id']} 的 status 无效")
        if not isinstance(row.get("text"), str) or not isinstance(row.get("chapter_id"), str):
            raise BidError(f"响应 {row['requirement_id']} 缺少 text/chapter_id")
    for row in state["draft.json"]:
        if not isinstance(row.get("content"), str) or row.get("status") not in ("draft", "reviewed"):
            raise BidError(f"正文 {row['chapter_id']} 缺少 content 或有效 status")
    for source in state["sources.json"]:
        if source.get("role") not in SOURCE_ROLES:
            raise BidError(f"资料 {source['id']} 的 role 无效")
        for key in ("path", "extracted_path", "sha256", "extracted_sha256"):
            if not isinstance(source.get(key), str) or not source[key]:
                raise BidError(f"资料 {source['id']} 缺少 {key}")
    for evidence in state["evidence.json"]:
        if evidence.get("status") not in ("verified", "unverified"):
            raise BidError(f"证据 {evidence['id']} 的 status 无效")
        if not isinstance(evidence.get("company"), str) or not isinstance(evidence.get("kind"), str):
            raise BidError(f"证据 {evidence['id']} 缺少 company/kind")
        if evidence.get("valid_until") is not None:
            check_date(evidence["valid_until"])


def fingerprint(root, state=None):
    state = state or load_state(root)
    files = {}
    for source in state["sources.json"]:
        for key in ("path", "extracted_path"):
            path = inside(root, source[key])
            files[source[key]] = digest(path.read_bytes()) if path.is_file() else "missing"
    return digest(canonical({"state": state, "files": files}))


def source_snapshot(root, source):
    return digest(canonical({key: digest(inside(root, source[key]).read_bytes())
                             for key in ("path", "extracted_path")}))


def review_source(root, source_id, reviewer, note):
    root = project_dir(root)
    sources = read_json(root / "sources.json")
    source = next((s for s in sources if s["id"] == source_id), None)
    if not source:
        raise BidError(f"资料不存在: {source_id}")
    extracted = read_json(inside(root, source["extracted_path"]))
    if not any(b.get("text", "").strip() for b in extracted["blocks"]):
        raise BidError("正文为空，先完成 OCR 和原文核对；不能仅靠确认跳过")
    source["review"] = {"reviewer": reviewer, "note": note, "at": now(),
                        "snapshot": source_snapshot(root, source)}
    write_json(root / "sources.json", sources)


def record_review(root, kind, status, reviewer, note):
    root = project_dir(root)
    if kind not in MANUAL_CHECKS or status not in ("pass", "issue", "not_applicable"):
        raise BidError("无效复核类型或状态")
    records = read_json(root / "reviews.json")
    if not isinstance(records, list):
        raise BidError("reviews.json 须为数组")
    records = [r for r in records if r.get("kind") != kind]
    records.append({"kind": kind, "status": status, "reviewer": reviewer,
                    "note": note, "at": now(), "snapshot": fingerprint(root)})
    write_json(root / "reviews.json", records)


def audit(root):
    root = project_dir(root)
    state = load_state(root)
    p = state["project.json"]
    as_of = check_date(p["as_of_date"])
    issues = []

    def issue(category, code, severity, target, message):
        issues.append({"category": category, "code": code, "severity": severity,
                       "target": target, "message": message})

    sources = {s["id"]: s for s in state["sources.json"]}
    extracted = {}
    for sid, s in sources.items():
        for key, sha in (("path", "sha256"), ("extracted_path", "extracted_sha256")):
            file = inside(root, s[key])
            if not file.is_file() or digest(file.read_bytes()) != s[sha]:
                issue("traceability", "SOURCE_CHANGED", "blocker", sid, f"{key} 丢失或已变化，请重新导入并核对来源")
        path = inside(root, s["extracted_path"])
        if not path.is_file():
            continue
        text = read_json(path)
        if not isinstance(text.get("blocks"), list) or any(not isinstance(b, dict) or not isinstance(b.get("locator"), str) or not isinstance(b.get("text"), str) for b in text["blocks"]):
            raise BidError(f"资料 {sid} 的抽取 blocks 格式无效")
        locators = [b["locator"] for b in text["blocks"]]
        if len(locators) != len(set(locators)):
            raise BidError(f"资料 {sid} 的定位符重复")
        extracted[sid] = {b["locator"]: b["text"] for b in text["blocks"]}
        if not any(t.strip() for t in extracted[sid].values()):
            issue("traceability", "EMPTY_SOURCE", "blocker", sid, "无可用文本；需 OCR 或转换")
        if text.get("warnings"):
            review = s.get("review") or {}
            originals_present = all(inside(root, s[key]).is_file() for key in ("path", "extracted_path"))
            if not originals_present or review.get("snapshot") != source_snapshot(root, s):
                issue("traceability", "SOURCE_REVIEW", "blocker", sid, "资料包含解析限制，尚未完成当前版本原件核对")

    def source_valid(ref, target, allowed_roles):
        if not isinstance(ref, dict):
            issue("traceability", "NO_SOURCE", "blocker", target, "缺少原文出处")
            return False
        sid, locator, quote = ref.get("source_id"), ref.get("locator"), ref.get("quote")
        source = sources.get(sid)
        if not source or source["role"] not in allowed_roles:
            issue("traceability", "SOURCE_ROLE", "blocker", target, "来源不存在或用途不符")
            return False
        text = extracted.get(sid, {}).get(locator, "")
        if not isinstance(quote, str) or not quote.strip() or quote not in text:
            issue("traceability", "QUOTE_MISMATCH", "blocker", target, "原文摘录与指定位置不匹配")
            return False
        return True

    requirements = {r["id"]: r for r in state["requirements.json"]}
    evidence = {e["id"]: e for e in state["evidence.json"]}
    outline = {c["id"]: c for c in state["outline.json"]}
    responses = {r["requirement_id"]: r for r in state["responses.json"]}
    drafts = {d["chapter_id"]: d for d in state["draft.json"]}
    if not any(s["role"] in ("tender", "amendment") for s in sources.values()):
        issue("coverage", "NO_TENDER", "blocker", "sources", "未导入招标文件")
    if not requirements:
        issue("coverage", "NO_REQUIREMENTS", "blocker", "requirements", "尚未建立要求台账；空台账不表示无风险")
    if not outline or not drafts:
        issue("coverage", "NO_DRAFT", "blocker", "draft", "目录或正文为空")
    for key in ("company", "lot"):
        if not p[key].strip():
            issue("consistency", "PROJECT_FIELD", "blocker", key, "缺少投标主体或标包；无分包时 lot 填 whole")
    for key in ("name", "company", "lot"):
        if PLACEHOLDER.search(p[key]):
            issue("consistency", "PLACEHOLDER", "blocker", key, "项目主数据存在待填项")
    valid_evidence = {}
    for eid, e in evidence.items():
        valid = source_valid(e.get("source"), eid, ("company", "history"))
        if e["company"] != p["company"]:
            valid = False
            issue("qualification", "WRONG_COMPANY", "blocker", eid, "证据主体与本次投标主体不一致")
        if e["status"] != "verified":
            valid = False
            issue("qualification", "UNVERIFIED_EVIDENCE", "blocker", eid, "企业证据未核验")
        if e.get("valid_until") and check_date(e["valid_until"]) < as_of:
            valid = False
            issue("qualification", "EXPIRED_EVIDENCE", "blocker", eid, f"证据在核验日期 {as_of} 已过期")
        if e["kind"] == "certificate" and not e.get("valid_until") and not e.get("validity_note", "").strip():
            valid = False
            issue("qualification", "VALIDITY_UNKNOWN", "blocker", eid, "资质证据缺少有效期或长期有效的依据说明")
        valid_evidence[eid] = valid

    # Detect missing parents and cycles before traversal/export.
    for cid, chapter in outline.items():
        if PLACEHOLDER.search(chapter["title"]):
            issue("coverage", "PLACEHOLDER", "blocker", cid, "目录标题存在待填项")
        parent = chapter.get("parent_id")
        if parent and parent not in outline:
            issue("coverage", "MISSING_PARENT", "blocker", cid, "目录父章节不存在")
        seen = {cid}
        while parent in outline:
            if parent in seen:
                issue("coverage", "OUTLINE_CYCLE", "blocker", cid, "目录父子关系成环")
                break
            seen.add(parent)
            parent = outline[parent].get("parent_id")
        for rid in chapter.get("requirement_ids", []):
            if rid not in requirements:
                issue("coverage", "UNKNOWN_REQUIREMENT", "blocker", cid, f"引用不存在的要求 {rid}")
        for eid in chapter.get("evidence_ids", []):
            if eid not in evidence:
                issue("traceability", "UNKNOWN_EVIDENCE", "blocker", cid, f"引用不存在的证据 {eid}")
    for rid, r in requirements.items():
        source_valid(r.get("source"), rid, ("tender", "amendment"))
        if r["lot"] not in (p["lot"], "all"):
            issue("consistency", "WRONG_LOT", "blocker", rid, "要求属于其他标包")
        chapters = [c for c in outline.values() if rid in c.get("requirement_ids", [])]
        severity = "blocker" if r["mandatory"] else "warning"
        if not chapters:
            issue("coverage", "UNMAPPED_REQUIREMENT", severity, rid, "要求未映射到目录")
        response = responses.get(rid)
        if not response:
            issue("response", "NO_RESPONSE", severity, rid, "缺少逐条响应")
            continue
        cid = response["chapter_id"]
        draft = drafts.get(cid)
        if cid not in outline or rid not in outline[cid].get("requirement_ids", []):
            issue("coverage", "RESPONSE_MAPPING", severity, rid, "响应章节与要求映射不一致")
        if not draft or not draft["content"].strip() or rid not in draft.get("requirement_ids", []):
            issue("coverage", "EMPTY_RESPONSE_CHAPTER", severity, rid, "响应未落实到正文")
        if response["status"] != "satisfied" or not response["text"].strip():
            issue("response", "RESPONSE_GAP", severity, rid, "响应为部分满足、偏离、缺失或待核实")
        eids = response.get("evidence_ids", [])
        if r["category"] == "qualification" and not eids:
            issue("qualification", "QUALIFICATION_GAP", "blocker", rid, "资格要求缺少企业证明材料")
        for eid in eids:
            if not valid_evidence.get(eid, False):
                issue("qualification", "INVALID_RESPONSE_EVIDENCE", "blocker", rid, f"响应证据 {eid} 不可用")
            if draft and eid not in draft.get("evidence_ids", []):
                issue("traceability", "UNUSED_RESPONSE_EVIDENCE", "blocker", rid, f"响应证据 {eid} 未关联到正文")
        if r.get("score") is not None or r["category"] == "scoring":
            if not draft or len(draft.get("content", "").strip()) < 20:
                issue("scoring", "THIN_SCORE_RESPONSE", "warning", rid, "评分项正文过短，需核验可评分事实与证明")
    for rid in responses.keys() - requirements.keys():
        issue("response", "UNKNOWN_RESPONSE", "blocker", rid, "响应引用不存在的要求")
    text_parts = []
    for cid, draft in drafts.items():
        if cid not in outline:
            issue("coverage", "ORPHAN_DRAFT", "blocker", cid, "正文无对应目录")
        text = draft["content"]
        text_parts.append(text)
        if not text.strip():
            issue("coverage", "EMPTY_CHAPTER", "blocker", cid, "正文为空")
        if draft["status"] != "reviewed":
            issue("response", "DRAFT_NOT_REVIEWED", "blocker", cid, "章节尚未完成语义核对")
        if PLACEHOLDER.search(text):
            issue("coverage", "PLACEHOLDER", "blocker", cid, "正文存在待填项")
        for rid in draft.get("requirement_ids", []):
            if rid not in requirements:
                issue("coverage", "UNKNOWN_REQUIREMENT", "blocker", cid, f"正文引用不存在的要求 {rid}")
        for eid in draft.get("evidence_ids", []):
            if not valid_evidence.get(eid, False):
                issue("traceability", "INVALID_DRAFT_EVIDENCE", "blocker", cid, f"正文证据 {eid} 不可用")
    for cid in outline.keys() - drafts.keys():
        # Container headings need no body, but leaves must have authored content.
        if not any(c.get("parent_id") == cid for c in outline.values()):
            issue("coverage", "MISSING_CHAPTER", "blocker", cid, "叶子章节未撰写")
    all_text = "\n".join(text_parts + [p["name"], p["lot"]] + [c["title"] for c in outline.values()])
    if p["anonymous"]:
        identities = list(set([p["company"]] + p["identity_terms"]))
        for term in identities:
            if term and term in all_text:
                issue("format", "ANONYMOUS_IDENTITY", "blocker", "draft", f"暗标正文或标题含身份线索: {term}")
    # Known wrong fields can be listed by the writer; heuristic extraction is not proof.
    for draft in drafts.values():
        values = draft.get("field_values", {})
        if not isinstance(values, dict):
            raise BidError("draft.field_values 须为对象")
        authoritative = {"project_name": p["name"], "company": p["company"], "lot": p["lot"], **p["facts"]}
        for key, value in values.items():
            if key not in authoritative or value != authoritative[key]:
                issue("consistency", "FIELD_MISMATCH", "blocker", draft["chapter_id"], f"关键字段 {key} 与项目主数据不一致")
    check_price(p["facts"], issue)
    if p["facts"].get("bid_total") is None and any(r["category"] == "price" and r["mandatory"] for r in requirements.values()):
        issue("price", "PRICE_REQUIRED", "blocker", "facts", "存在强制报价要求但未录入报价总额")
    # Lightweight intra-document reuse clue; semantic/external duplicate review is separate.
    draft_items = list(drafts.items())
    for i, (cid, d) in enumerate(draft_items):
        a = re.sub(r"\s+", "", d["content"])
        if len(a) < 80:
            continue
        for other_id, other in draft_items[i + 1:]:
            b = re.sub(r"\s+", "", other["content"])
            if len(b) >= 80 and SequenceMatcher(None, a, b, autojunk=False).ratio() >= 0.85:
                issue("similarity", "SIMILAR_CHAPTERS", "warning", f"{cid}/{other_id}", "章节文本高度相似，核验是否重复堆砌或误用模板")
    snapshot = fingerprint(root, state)
    reviews = read_json(root / "reviews.json")
    if not isinstance(reviews, list) or any(not isinstance(r, dict) for r in reviews):
        raise BidError("reviews.json 须为对象数组")
    for kind in MANUAL_CHECKS:
        rows = [r for r in reviews if r.get("kind") == kind]
        valid = (len(rows) == 1 and rows[0].get("snapshot") == snapshot
                 and rows[0].get("status") in ("pass", "not_applicable")
                 and bool(rows[0].get("reviewer", "").strip()) and bool(rows[0].get("note", "").strip()))
        if kind in ("semantic", "format") and rows and rows[0].get("status") == "not_applicable":
            valid = False
        if not valid:
            category = {"semantic": "response", "format": "format", "signature": "format", "similarity": "similarity"}[kind]
            issue(category, "REVIEW_REQUIRED", "blocker", kind, "当前版本尚无有效专项复核记录；记录须说明范围、发现和依据")
    counts = Counter(i["severity"] for i in issues)
    return {"schema_version": "1.0", "project": p["name"], "as_of_date": str(as_of),
            "snapshot": snapshot, "checked_at": now(), "status": "blocked" if counts["blocker"] else "checks_complete",
            "summary": {"blocker": counts["blocker"], "warning": counts["warning"],
                        "requirements": len(requirements), "chapters": len(outline)},
            "categories": list(CATEGORIES), "issues": issues,
            "scope": "本地结构与基础规则检查；语义、版式、签章和跨文件相似复核须单独记录。checks_complete 不保证中标或法律合规。"}


def check_price(facts, issue):
    def number(value):
        if isinstance(value, bool):
            raise InvalidOperation()
        parsed = Decimal(str(value))
        if not parsed.is_finite() or parsed < 0:
            raise InvalidOperation()
        return parsed
    try:
        budget = number(facts["budget"]) if facts.get("budget") is not None else None
        total = number(facts["bid_total"]) if facts.get("bid_total") is not None else None
        if budget is not None and total is not None and total > budget:
            issue("price", "OVER_BUDGET", "blocker", "facts", "投标总价超过项目预算/最高限价；请核对口径")
        items = facts.get("line_items", [])
        if not isinstance(items, list):
            raise BidError("facts.line_items 须为数组")
        if items:
            if total is None:
                issue("price", "NO_TOTAL", "blocker", "facts", "有分项报价但缺少总价")
            item_total = Decimal("0")
            for item in items:
                if not isinstance(item, dict) or item.get("currency", facts.get("currency")) != facts.get("currency"):
                    issue("price", "PRICE_CURRENCY", "blocker", "facts", "报价币种不一致")
                    continue
                line = (number(item["quantity"]) * number(item["unit_price"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if "amount" in item and number(item["amount"]) != line:
                    issue("price", "LINE_AMOUNT", "blocker", "facts", "分项金额与数量乘单价不一致")
                item_total += line
            if total is not None and item_total != total:
                issue("price", "TOTAL_MISMATCH", "blocker", "facts", "分项金额合计与总价不一致")
        if total is None:
            issue("price", "PRICE_UNKNOWN", "warning", "facts", "未录入报价，未完成报价核验；不适用时在专项复核中说明")
    except (InvalidOperation, KeyError, TypeError, ValueError) as exc:
        issue("price", "INVALID_PRICE", "blocker", "facts", f"报价数据无效: {type(exc).__name__}")


def ordered_chapters(outline):
    result = []
    def walk(parent=None, depth=1):
        if depth > 30:
            raise BidError("目录过深或成环")
        for row in sorted((c for c in outline if c.get("parent_id") == parent), key=lambda c: (c["order"], c["id"])):
            result.append((row, depth))
            walk(row["id"], depth + 1)
    walk()
    if len(result) != len(outline):
        raise BidError("目录包含不可达章节，请修复父子关系")
    return result


def markdown_report(result):
    lines = [f"# {result['project']} 审查报告", "", f"核验日期：{result['as_of_date']}",
             f"状态：{result['status']}；阻断项：{result['summary']['blocker']}；提示项：{result['summary']['warning']}",
             "", result["scope"], "", "| 级别 | 类别 | 对象 | 发现 |", "| --- | --- | --- | --- |"]
    for i in result["issues"]:
        values = [i["severity"], i["category"], i["target"], i["message"]]
        lines.append("| " + " | ".join(v.replace("|", "\\|").replace("\n", " ") for v in values) + " |")
    return "\n".join(lines) + "\n"


def response_matrix(root):
    state = load_state(project_dir(root))
    responses = {r["requirement_id"]: r for r in state["responses.json"]}
    lines = ["# 招标要求与投标响应矩阵", "", "| 要求 | 招标定位 | 要求内容 | 强制 | 分值 | 响应状态 | 章节 | 证据 |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in state["requirements.json"]:
        s = r.get("source") or {}
        response = responses.get(r["id"], {})
        values = [r["id"], f"{s.get('source_id', '')} {s.get('locator', '')}", r["text"],
                  "是" if r["mandatory"] else "否", str(r.get("score") if r.get("score") is not None else ""),
                  response.get("status", "missing"), response.get("chapter_id", ""), ", ".join(response.get("evidence_ids", []))]
        lines.append("| " + " | ".join(v.replace("|", "\\|").replace("\n", " ") for v in values) + " |")
    return "\n".join(lines) + "\n"


def export_document(root, output, mode="draft"):
    root = project_dir(root)
    result = audit(root)
    if mode == "submission" and result["status"] != "checks_complete":
        raise BidError(f"存在 {result['summary']['blocker']} 个阻断项；先 audit 修复，或以 draft 模式导出")
    state = load_state(root)
    p = state["project.json"]
    chapters = ordered_chapters(state["outline.json"])
    if not chapters:
        raise BidError("目录为空，无法导出")
    drafts = {d["chapter_id"]: d for d in state["draft.json"]}
    # Container headings may legitimately have no body. Keep the leaf fallback
    # below, but never invent a missing-body warning for a heading-only volume.
    container_ids = {chapter.get("parent_id") for chapter in state["outline.json"]}
    for chapter_id in container_ids - {None}:
        drafts.setdefault(chapter_id, {"content": ""})
    output = Path(output).resolve()
    if not output.is_relative_to(root / "outputs"):
        raise BidError("导出文件须位于项目 outputs 目录中")
    if output.exists() or output.with_suffix(output.suffix + ".receipt.json").exists():
        raise BidError("输出文件已存在，请换用新文件名，保留历史版本")
    if output.suffix.lower() not in (".md", ".docx"):
        raise BidError("导出扩展名仅支持 .md 和 .docx")
    lines = [f"# {p['name']} 投标文件", ""]
    if mode == "draft":
        lines.extend([f"工作草稿  尚有 {result['summary']['blocker']} 个阻断项及 {result['summary']['warning']} 个提示项", ""])
    if not p["anonymous"]:
        lines.extend([f"投标人：{p['company']}", f"标包：{p['lot']}", ""])
    lines.extend(["## 目录", ""])
    for chapter, depth in chapters:
        lines.append("  " * (depth - 1) + "- " + chapter["title"])
    lines.append("")
    for chapter, depth in chapters:
        lines.extend(["#" * min(depth + 1, 6) + " " + chapter["title"], "",
                      drafts.get(chapter["id"], {}).get("content", "【待填写正文】"), ""])
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() == ".md":
        output.write_text("\n".join(lines), encoding="utf-8")
    else:
        write_docx(output, p, chapters, drafts, result, mode)
    receipt = {"plugin_version": VERSION, "mode": mode, "at": now(),
               "file": output.name, "sha256": digest(output.read_bytes()),
               "snapshot": result["snapshot"], "audit_status": result["status"],
               "review_records": read_json(root / "reviews.json"),
               "note": "导出成功仅证明文件生成；最终文件须渲染并核对招标格式、附件、签章及提交要求。"}
    write_json(output.with_suffix(output.suffix + ".receipt.json"), receipt)
    return output


def write_docx(output, project, chapters, drafts, result, mode):
    try:
        from docx import Document
        from docx.shared import Cm, Pt, RGBColor
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
    except ImportError as exc:
        raise BidError("Word 导出需要 python-docx；请安装插件 requirements.txt") from exc
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    fmt = project["format"]
    margin = float(fmt.get("margin_cm", 2.5))
    size = float(fmt.get("font_size_pt", 12))
    if not (1 <= margin <= 5 and 8 <= size <= 24):
        raise BidError("页边距须在 1 至 5 cm，正文字号须在 8 至 24 pt")
    section.top_margin = section.bottom_margin = section.left_margin = section.right_margin = Cm(margin)
    for style_name in ("Normal", "Title", "Heading 1", "Heading 2", "Heading 3", "Heading 4", "Heading 5", "Heading 6"):
        style = doc.styles[style_name]
        style.font.name = "Times New Roman"
        style._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), fmt.get("font", "宋体"))
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.font.size = Pt(size if style_name == "Normal" else (22 if style_name == "Title" else max(12, 18 - int(style_name[-1]))))
        # Bundled/default Word templates may carry a blue border in Title.
        for border in list(style._element.iter(qn("w:pBdr"))):
            border.getparent().remove(border)
        style.paragraph_format.space_after = Pt(8)
        style.paragraph_format.widow_control = True
    doc.styles["Normal"].paragraph_format.line_spacing = 1.35
    doc.core_properties.author = ""
    doc.core_properties.last_modified_by = ""
    doc.core_properties.title = f"{project['name']} 投标文件"
    doc.add_paragraph(doc.core_properties.title, "Title")
    if mode == "draft":
        doc.add_paragraph(f"工作草稿  尚有 {result['summary']['blocker']} 个阻断项及 {result['summary']['warning']} 个提示项")
    if not project["anonymous"]:
        doc.add_paragraph(f"投标人：{project['company']}")
        doc.add_paragraph(f"标包：{project['lot']}")
    doc.add_heading("目录", level=1)
    for chapter, depth in chapters:
        paragraph = doc.add_paragraph(chapter["title"])
        paragraph.paragraph_format.left_indent = Cm(min(depth - 1, 5) * 0.5)
    doc.add_page_break()
    for chapter, depth in chapters:
        doc.add_heading(chapter["title"], level=min(depth, 6))
        content = drafts.get(chapter["id"], {}).get("content", "【待填写正文】")
        # Deliberately small Markdown subset; native tender forms must be retained separately.
        rows = content.splitlines()
        index = 0
        while index < len(rows):
            line = rows[index].strip()
            if not line:
                index += 1
                continue
            if line.startswith("|") and line.endswith("|"):
                table_rows = []
                while index < len(rows) and rows[index].strip().startswith("|"):
                    cells = [c.strip() for c in rows[index].strip().strip("|").split("|")]
                    if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                        table_rows.append(cells)
                    index += 1
                if table_rows:
                    columns = max(len(row) for row in table_rows)
                    if columns > 6:
                        raise BidError("Word 表格超过 6 列，请拆表以保证可读性")
                    table = doc.add_table(rows=0, cols=columns)
                    table.style = "Table Grid"
                    table.autofit = False
                    for row in table_rows:
                        cells = table.add_row().cells
                        for j, value in enumerate(row):
                            cells[j].text = value
                    for cell in table.rows[0].cells:
                        for run in cell.paragraphs[0].runs:
                            run.bold = True
                    for row in table.rows:
                        tr_pr = row._tr.get_or_add_trPr()
                        tr_pr.append(OxmlElement("w:cantSplit"))
                    table.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
                continue
            if re.match(r"^#{1,6} ", line):
                hashes, text = line.split(" ", 1)
                doc.add_heading(text, level=min(depth + len(hashes), 6))
            else:
                # Plain text preserves contractual wording; no silent replacements or paraphrasing.
                doc.add_paragraph(line)
            index += 1
    # Anonymous output has no author, company cover, header, or footer identities.
    doc.save(output)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="新建项目，不覆盖非空目录")
    init.add_argument("--project", required=True)
    init.add_argument("--name", required=True)
    init.add_argument("--company", default="")
    init.add_argument("--lot", default="")
    init.add_argument("--as-of")
    imp = sub.add_parser("ingest", help="导入用户指定的本地文件")
    imp.add_argument("--project", required=True)
    imp.add_argument("--file", required=True)
    imp.add_argument("--role", choices=SOURCE_ROLES, required=True)
    for name in ("library-init", "library-add", "library-search", "library-use"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--library", required=True)
        if name == "library-init":
            cmd.add_argument("--company", required=True)
        elif name == "library-add":
            cmd.add_argument("--file", required=True)
            cmd.add_argument("--kind", choices=("certificate", "case", "person", "product", "module"), required=True)
            cmd.add_argument("--tags", default="")
            cmd.add_argument("--valid-until")
        elif name == "library-search":
            cmd.add_argument("--query", default="")
            cmd.add_argument("--as-of")
        else:
            cmd.add_argument("--project", required=True)
            cmd.add_argument("--item", required=True)
    for name in ("audit", "matrix", "status", "snapshot"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--project", required=True)
    for name in ("review-source", "review"):
        cmd = sub.add_parser(name, help="记录已实际完成的复核；命令本身不执行复核")
        cmd.add_argument("--project", required=True)
        cmd.add_argument("--reviewer", required=True)
        cmd.add_argument("--note", required=True)
        if name == "review-source":
            cmd.add_argument("--source", required=True)
        else:
            cmd.add_argument("--kind", choices=MANUAL_CHECKS, required=True)
            cmd.add_argument("--status", choices=("pass", "issue", "not_applicable"), required=True)
    exp = sub.add_parser("export")
    exp.add_argument("--project", required=True)
    exp.add_argument("--out", required=True)
    exp.add_argument("--mode", choices=("draft", "submission"), default="draft")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            print(initialize(args.project, args.name, args.company, args.lot, args.as_of))
        elif args.command == "ingest":
            print(json.dumps(ingest(args.project, args.file, args.role), ensure_ascii=False, indent=2))
        elif args.command == "library-init":
            print(library_init(args.library, args.company))
        elif args.command == "library-add":
            print(json.dumps(library_add(args.library, args.file, args.kind, args.tags, args.valid_until), ensure_ascii=False, indent=2))
        elif args.command == "library-search":
            print(json.dumps(library_search(args.library, args.query, args.as_of), ensure_ascii=False, indent=2))
        elif args.command == "library-use":
            print(json.dumps(library_use(args.project, args.library, args.item), ensure_ascii=False, indent=2))
        elif args.command == "review-source":
            if not args.note.strip() or not args.reviewer.strip():
                raise BidError("复核人和说明不能为空")
            review_source(args.project, args.source, args.reviewer, args.note)
            print("已记录原件核对；这条记录不替代实际核对")
        elif args.command == "review":
            if not args.note.strip() or not args.reviewer.strip():
                raise BidError("复核人和说明不能为空")
            record_review(args.project, args.kind, args.status, args.reviewer, args.note)
            print("已记录专项复核；项目变化后记录自动失效")
        elif args.command in ("audit", "status"):
            result = audit(args.project)
            if args.command == "audit":
                root = project_dir(args.project)
                write_json(root / "outputs" / "audit.json", result)
                (root / "outputs" / "audit.md").write_text(markdown_report(result), encoding="utf-8")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 2 if result["status"] == "blocked" else 0
        elif args.command == "snapshot":
            print(fingerprint(project_dir(args.project)))
        elif args.command == "matrix":
            root = project_dir(args.project)
            path = root / "outputs" / "response-matrix.md"
            path.parent.mkdir(exist_ok=True)
            path.write_text(response_matrix(root), encoding="utf-8")
            print(path)
        elif args.command == "export":
            print(export_document(args.project, args.out, args.mode))
        return 0
    except (BidError, OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
