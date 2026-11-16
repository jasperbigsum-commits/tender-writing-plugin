# 标书写作工作台

可安装的技能型插件，以[百炼公开产品页](https://www.bailian-ai.com/agent-tender)的六步投标流程为主线：资料沉淀、文件导入、智能研读、生成目录、撰写排版、审查导出。具体实现为本项目自行编写，当前源码版本0.1.1。

## 使用方式

插件启用后提供招标文件、澄清与企业资料，输入：

> 根据这些文件建立标书项目，先完整研读并整理要求与缺口，再生成目录、逐章写作并审查导出。投标主体是……，标包是……。

六个技能为 `bid-writing`、`company-library`、`tender-reading`、`bid-outline`、`bid-drafting`、`bid-review`。当前模型负责研读和写作，脚本负责文件、定位、台账、基础检查与Word导出。制标和评标的相邻业务边界见[角色说明](skills/bid-writing/references/roles.md)。

## 本地命令

Python 3.10以上。基础JSON/Markdown工作流使用标准库，PDF和Word的可选依赖在 `requirements.txt`。建议专用环境；Codex中优先使用其提供的运行时。

```powershell
python "skills/bid-writing/scripts/bidflow.py" --help
python "skills/bid-writing/scripts/bidflow.py" init --project "../projects/demo" --name "示例项目" --company "示例甲公司" --lot whole
python "skills/bid-writing/scripts/bidflow.py" ingest --project "../projects/demo" --file "examples/tender.md" --role tender
```

然后由模型实际阅读原文，按[数据契约](skills/bid-writing/references/data-contract.md)填写要求、证据、目录、响应和正文。详细命令见[运行手册](skills/bid-writing/references/cli.md)。空项目审查会返回阻断状态，这是预期行为。

## 当前支持与边界

- TXT/Markdown、DOCX及带文本层PDF导入；来源副本、定位及SHA-256留在项目内。
- 跨项目企业资料存储和关键词查找；所选资料导入项目后重新核验。
- 要求、目录、响应和正文关联；九类基础检查、专项核验记录、修改后失效。
- Markdown和基础A4 Word导出，保留草稿状态、拒绝覆盖已有版本，附带文件哈希回执。

扫描件需另做OCR，复杂图表与招标制式模板需宿主文档能力处理。检查和导出都不替代实际语义、签章、CA、版式及递交核验。没有正式评标、自动定标或跨供应商全量查重服务。

脚本无外联、无API Key配置。会话中的资料处理仍由宿主模型环境负责，不能将“本地脚本”解释为整套工作流离线运行。

## 分发

根 `plugin.json` 为Agent Plugins 1.0；另含Codex及Claude格式兼容清单。ZIP只打包一个插件，不含用户项目资料、研究抓取、测试缓存或凭据。宿主支持程度与安装后的技能发现须在实际环境验证；本目录本身不代表已安装。
