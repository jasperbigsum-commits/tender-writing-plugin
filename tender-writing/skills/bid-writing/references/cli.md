# 本地运行手册

Python 3.10 及以上。基础台账、Markdown 和审查使用标准库；PDF 需要 pypdf，DOCX 需要 python-docx。依赖清单在插件根目录 `requirements.txt`。Codex 提供 bundled runtime 时使用其解释器；其他环境建议专用虚拟环境。

以下 `python` 替换为实际解释器，`<PLUGIN_ROOT>` 替换为安装后的插件绝对目录；路径含空格须整体加引号。通过宿主文件工具读写 JSON，不把文件内容拼成 shell 命令。

```powershell
python "<PLUGIN_ROOT>/skills/bid-writing/scripts/bidflow.py" init --project "./projects/demo" --name "项目名称" --company "投标主体全称" --lot "whole" --as-of "2026-12-01"
python "<PLUGIN_ROOT>/skills/bid-writing/scripts/bidflow.py" ingest --project "./projects/demo" --file "招标文件.pdf" --role tender
python "<PLUGIN_ROOT>/skills/bid-writing/scripts/bidflow.py" ingest --project "./projects/demo" --file "澄清说明.docx" --role amendment
python "<PLUGIN_ROOT>/skills/bid-writing/scripts/bidflow.py" ingest --project "./projects/demo" --file "企业证明.docx" --role company
```

`--as-of` 须用本项目实际适用的日期；示例日期没有业务效力。支持 UTF-8 TXT/MD、DOCX、PDF，每件最多100 MiB。旧DOC、XLSX参数表和图像需用宿主能力转换为可读、可追溯资料。扫描PDF不会自动OCR，抽取为空始终保留阻断项。

导入读取一份固定字节快照进行解析与归档。相同内容和用途的完整副本重复导入保持幂等；出现 `SOURCE_CHANGED` 时可用完整原件按相同用途重新执行 `ingest`。修复保留来源ID、备份损坏副本、使旧复核失效；出现 `SOURCE_REPAIR_PENDING` 表示上次修复未完成，重复导入可继续恢复。修复后重新核对原件、响应与相关专项结果，不能直接沿用旧通过记录。

模型读取全部抽取块和原件，按契约填写 requirements/evidence/outline/responses/draft；脚本不调用大模型、不自动填这些台账。原件解析限制核对完毕后记录：

```powershell
python "<PLUGIN_ROOT>/skills/bid-writing/scripts/bidflow.py" review-source --project "./projects/demo" --source S0001 --reviewer assistant --note "已实际核对的原件范围和补充结果；只在完成后填写"
```

## 跨项目资料复用

```powershell
python "<PLUGIN_ROOT>/skills/bid-writing/scripts/bidflow.py" library-init --library "./company-library/demo" --company "投标主体全称"
python "<PLUGIN_ROOT>/skills/bid-writing/scripts/bidflow.py" library-add --library "./company-library/demo" --file "企业证明.docx" --kind certificate --tags "资质,运维" --valid-until "2027-12-31"
python "<PLUGIN_ROOT>/skills/bid-writing/scripts/bidflow.py" library-search --library "./company-library/demo" --query "运维" --as-of "2026-12-01"
python "<PLUGIN_ROOT>/skills/bid-writing/scripts/bidflow.py" library-use --project "./projects/demo" --library "./company-library/demo" --item L0001
```

条目复用仅导入原件，随后需阅读并建立项目证据。搜索按名称、类型、标签中包含全部查询词匹配，不提供语义向量索引。换主体会被拒绝，过期情况在查询结果中提示；是否满足本次要求仍需核验。

## 审查和导出

```powershell
python "<PLUGIN_ROOT>/skills/bid-writing/scripts/bidflow.py" matrix --project "./projects/demo"
python "<PLUGIN_ROOT>/skills/bid-writing/scripts/bidflow.py" audit --project "./projects/demo"
python "<PLUGIN_ROOT>/skills/bid-writing/scripts/bidflow.py" export --project "./projects/demo" --out "./projects/demo/outputs/投标文件_草稿_v1.docx" --mode draft
```

audit 写入 `outputs/audit.json` 和 `outputs/audit.md`。阻断事项退出码2是业务状态，不要吞掉输出或为变成0而补造事实。`status` 只读显示状态，`snapshot` 显示当前指纹。

完成实际专项复核后逐项记录，示例中的说明必须换成真实结果：

```powershell
python "<PLUGIN_ROOT>/skills/bid-writing/scripts/bidflow.py" review --project "./projects/demo" --kind semantic --status pass --reviewer assistant --note "具体原文、正文和证据检查范围及发现"
```

kind 可取 semantic/format/signature/similarity；status 可取 pass/issue/not_applicable，其中 semantic 和 format 必须实际通过。记录本身不执行检查。当前版本齐备后才能 `--mode submission`；文件仍须最终渲染、人工完成相应签章与递交。对版式验收有专门技能的宿主优先使用其文档渲染工具。

只支持 `.md` / `.docx` 输出，须位于项目的 `outputs` 子目录。现有文件或回执不会覆盖，每次用新版本文件名。DOCX 提供黑白A4、标题层级、静态目录和简单表格；不自动保留招标原制式表格、复杂图文、签章或动态页码。复杂格式按招标模板用宿主文档工具处理，完成后重新核验。

导出期间改动项目或撤销复核会中止，应重新审查当前版本后再导出。纯目录容器仅输出标题；缺失叶子正文保留待填并阻止提交版。普通文件写入失败会尽力撤销本次创建的结果，已存在或被其他任务替换的文件保留。进程被强制关闭等异常后，仍须检查文件和回执，不能仅凭文件出现判断成功。

每次导出生成 `.receipt.json`，记录文件SHA-256、来源状态指纹和检查记录。需要PDF时用宿主已授权转换能力从最终Word另行输出并核对，两种格式的文件哈希分别管理。
