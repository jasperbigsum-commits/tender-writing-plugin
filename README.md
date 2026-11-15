# 标书智能体插件

[![CI](https://github.com/jasperbigsum-commits/tender-writing-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/jasperbigsum-commits/tender-writing-plugin/actions/workflows/ci.yml)

本项目以[百炼标书写作智能体](https://www.bailian-ai.com/agent-tender)的六步主体流程为依据，完成行业现状调研和可安装的本地技能插件。其他方案用于实际实现取舍，采购技术制标和正式评标作为相邻研究范围保留。

## 阅读入口

- [现状调研与插件设计](research/标书写作现状调研与插件设计.md)：七个商业产品、四个开源项目、源码发现与六步流程的实现取舍。
- 专项调研：[OpenBidKit](research/openbidkit.md)、[ProposalLLM](research/proposalllm.md)、[BidMaster-Pro](research/bidmaster.md)、[GodBiao](research/godbiao.md)。
- [插件使用说明](tender-writing/README.md)：六个技能、文件工具、资料复用和导出边界。
- [本地命令手册](tender-writing/skills/bid-writing/references/cli.md)和[数据契约](tender-writing/skills/bid-writing/references/data-contract.md)。
- [验收记录](docs/验收记录.md)：31项测试、Word实际渲染、包校验及未验证范围。

## 安装和启用

项目根目录已提供 `.claude-plugin/marketplace.json` 本地目录清单，指向 `tender-writing/`。此布局属于Codex支持的兼容本地市场布局，路径相对本项目根目录解析。[官方插件打包说明](https://developers.openai.com/plugins/build/plugins)

克隆项目后安装本地插件：

```powershell
git clone https://github.com/jasperbigsum-commits/tender-writing-plugin.git
cd tender-writing-plugin
codex plugin marketplace add .
codex plugin add tender-writing@tender-writing-local
```

安装后刷新宿主技能列表，确认出现 `bid-writing` 等六个技能。安装命令基于验收时的CLI帮助核对；具体宿主版本可能需要刷新或重新打开会话。仓库发布不会自动安装插件。构建的ZIP是单插件包，市场清单在源码项目内，不放入单插件ZIP。

也可从[发布版本](https://github.com/jasperbigsum-commits/tender-writing-plugin/releases)下载单插件ZIP和SHA-256校验文件。需要命令行文件工具时，在独立Python环境安装 `tender-writing/requirements.txt`。

启用后的示例任务：

> 用标书写作工作台根据这些招标、澄清和企业文件建立项目，先完整研读并输出要求与缺口，再编目录、逐章写作并审查导出。

## 开发和验收

使用Python 3.10及以上；Word/PDF相关能力需 `tender-writing/requirements.txt` 中的可选依赖。Codex环境优先使用bundled解释器。

```powershell
python -m pip install -r tender-writing/requirements.txt
python -m unittest discover -s tests -v
python tools/run_demo.py --out tmp/demo
python tools/build_plugin.py
```

示例使用人工构造资料，保留尚未完成的复核阻断项，用来验证状态控制。它不调用外部模型，也不代表真实投标质量。Word最终版式核验与外部项目的实际运行验证单独记录在验收报告。

GitHub Actions在Python 3.10和3.12上运行现有测试与打包校验。CI不调用模型、不使用真实招标资料，也不执行Word桌面渲染。
