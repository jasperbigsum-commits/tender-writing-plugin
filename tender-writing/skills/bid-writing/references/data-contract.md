# 项目数据契约

每个项目独立目录，文件均为 UTF-8 JSON。通过 `init` 创建空数据。资料与产物在项目内，不写回用户原件。模型在实际阅读后填写 JSON；脚本不自动生成要求或事实。编辑前保留必要版本，填完运行 `audit` 检查。

## 项目和来源

`project.json` 是主数据：`name` 项目名，`company` 投标主体，`lot` 标包（无分包填 `whole`），`as_of_date` 有效期核验日期（YYYY-MM-DD）。`facts` 包括招标编号、币种、预算、总价及分项；金额用十进制字符串，分项为 `quantity`、`unit_price`、可选 `amount`、`currency`。脚本按分项乘积保留两位、四舍五入，再求和；税费、币种换算及招标特殊公式另核验。

`anonymous` 标记暗标，`identity_terms` 填应检出的主体简称、人员名等身份线索。暗标导出省去投标人封面字段并清空作者，但仍需核对附件、图像和最终文档元数据。`format` 控制基础 A4 排版的字体、字号及页边距；它不是任意 Word 模板配置。

`sources.json` 由 `ingest` 生成，记录稳定 ID、用途、原件副本及抽取文件的相对路径和 SHA-256。用途 tender/amendment/company/history/bid 分别是招标、澄清、企业证明、历史材料、现有投标文件。抽取文件有 `blocks`，每块含 `locator` 与 `text`。

定位例子：`line:12`、`page:3`、`paragraph:6`、`table:1:row:2`。DOCX 定位不表示页码。原文引用一律采用：

```json
{"source_id":"S0001","locator":"line:4","quote":"该位置实际存在的原文摘录"}
```

## 招标要求 requirements.json

```json
[
  {
    "id": "R0001",
    "category": "qualification",
    "text": "要求的完整含义，保留限制条件",
    "mandatory": true,
    "score": null,
    "lot": "whole",
    "source": {"source_id":"S0001","locator":"line:4","quote":"逐字摘录"}
  }
]
```

category 可取 qualification、technical、commercial、format、price、submission、scoring。分值不明确用 null；不可自行补分。原文出处只接受 tender 或 amendment。冲突、澄清替代关系及已读覆盖范围记入研读简报。

## 企业证据 evidence.json

```json
[
  {
    "id": "E0001",
    "company": "本次投标主体全称",
    "kind": "certificate",
    "status": "unverified",
    "valid_until": "2027-12-31",
    "validity_note": "有效期原文依据",
    "source": {"source_id":"S0002","locator":"line:2","quote":"逐字摘录"},
    "claims": ["此证据直接支持的企业事实"],
    "scope_note": "适用产品、项目或业务范围"
  }
]
```

kind 建议 certificate、case、person、product、module。status 只取 verified/unverified；verified 必须经过实际核验。valid_until 不适用可为 null；certificate 没有到期日时必须有真实的长期有效依据说明，不能借说明字段绕过未知有效期。来源只接受 company/history。历史正文说明不自动证明现有资质或产品功能。

## 目录 outline.json

```json
[
  {"id":"C0001","parent_id":null,"order":1,"title":"资格与证明材料","requirement_ids":["R0001"],"evidence_ids":["E0001"]}
]
```

ID 不随标题或顺序变化；parent_id 表示树形结构。所有强制要求都要映射，所有叶子章节都要有正文。

## 响应 responses.json

```json
[
  {"requirement_id":"R0001","status":"unknown","chapter_id":"C0001","evidence_ids":["E0001"],"text":"本次实际响应及偏离说明"}
]
```

status 可取 satisfied/partial/deviation/missing/unknown。satisfied 不是默认值；资格项须有可用证明。每条要求只保留一个主响应，其他响应位置在正文或说明中关联。

## 正文 draft.json

```json
[
  {
    "chapter_id":"C0001",
    "content":"章节正文。缺少数据时写【待提供：具体材料】。",
    "status":"draft",
    "requirement_ids":["R0001"],
    "evidence_ids":["E0001"],
    "field_values":{"project_name":"项目主数据中的项目名","lot":"whole"}
  }
]
```

正文完成实际核验后 status 改 reviewed。field_values 支持 project_name、company、lot 和 facts 中的字段；它是写作者申报的字段索引，不是从全文自动抽取。审查时仍需全文比对。

## 复核与输出

`reviews.json` 通过 `review` 命令记录 semantic/format/signature/similarity 专项复核。记录含当前数据和来源文件的指纹、真实检查人、范围、发现及说明。原件核对通过 `review-source` 单独记录。数据一经变化专项复核失效，不能自动沿用。

`audit` 退出码：0 为基础检查及记录齐备；2 为有阻断事项；1 为输入或执行错误。状态 `checks_complete` 仅代表该检查范围完成。`outputs` 存放审查报告、响应矩阵、导出文档及哈希回执。回执不构成签名或法律认证。
