# OpenBidKit 易标投标工具箱调研

观察日期：2026-11-15。范围：用户指定仓库的公开 README、许可证、依赖、关键实现文件和发布记录。采用只读源码审阅，未下载或运行发行程序，未安装依赖，未调用模型、OCR 或线上服务；以下“代码可见”不等同于运行验证。

## 判断

OpenBidKit 已有桌面应用、可恢复任务、文档解析、资料条目、逐节正文、商务模板和 Word 导出代码，适合借鉴投标文件的端到端操作流程。它对长文生成、模板保留和异常恢复的工程投入，比单独的提示词示例更有参考价值。对于本次技能型插件，最值得吸收的是稳定章节标识、来源定位、章节写作计划和导出前问题清单；完整 Electron 桌面壳及配套云服务暂不属于必要前置条件。[任务实现](https://github.com/FB208/OpenBidKit_Yibiao/blob/77a38f07db822daee0e4be80b84c2281c73d646e/client/electron/services/taskService.cjs#L38-L74)、[正文规划](https://github.com/FB208/OpenBidKit_Yibiao/blob/77a38f07db822daee0e4be80b84c2281c73d646e/client/electron/services/contentGenerationTask.cjs#L585-L626)、[导出实现](https://github.com/FB208/OpenBidKit_Yibiao/blob/77a38f07db822daee0e4be80b84c2281c73d646e/client/electron/services/technicalPlanExport.cjs#L269-L321)

## 版本与来源

| 项目 | 本次观察 |
| --- | --- |
| 默认分支快照 | `77a38f07db822daee0e4be80b84c2281c73d646e`，提交时间为 2026-11-15T09:37:50Z；该提交仅更新星标历史，不能当作功能更新 |
| 最近可见功能提交 | `51619d06ef807773da9828234a015a5e8b553a94`，2026-11-14T07:52:29Z，主题为接入官方生图模型 |
| 公开发布 | 发布页标记最新为 v2.32.3，2026-11-12；该版本对应 `649ea225f8cd8b80f1b7a3598e50a0437d015768`，与本次审阅的默认分支快照不同 |
| 许可标识 | 仓库 LICENSE 为 GNU AGPL v3；NOTICE 明确标为 AGPL-3.0-only，并声明保留归属信息 |
| 验证层级 | README 功能说明 + 关键源码抽查 + 发布记录；无本机端到端运行结论 |

依据：[快照提交](https://github.com/FB208/OpenBidKit_Yibiao/commit/77a38f07db822daee0e4be80b84c2281c73d646e)、[功能提交](https://github.com/FB208/OpenBidKit_Yibiao/commit/51619d06ef807773da9828234a015a5e8b553a94)、[发布页](https://github.com/FB208/OpenBidKit_Yibiao/releases/tag/v2.32.3)、[LICENSE](https://github.com/FB208/OpenBidKit_Yibiao/blob/77a38f07db822daee0e4be80b84c2281c73d646e/LICENSE)、[NOTICE](https://github.com/FB208/OpenBidKit_Yibiao/blob/77a38f07db822daee0e4be80b84c2281c73d646e/NOTICE)。许可适配应另行核查，本报告只记录仓库标识，不作法律意见。

## 能力与实现

| 环节 | 代码中可见的实现 | 对插件的启发及限制 |
| --- | --- | --- |
| 文件输入 | 解析服务区分本地、MinerU 精准 API、MinerU Agent API；本地调用统一的 Markdown 转换器 | 统一抽取接口并保留解析通道。扫描件、图片和复杂表格不能默认为完整解析；使用云 OCR 会向相应服务发送文件 |
| 资料沉淀 | 知识条目保存来源 block ID 和来源文件；处理报告统计匹配、丢弃和恢复后的覆盖比例 | 资料库需要可追溯条目和未覆盖内容清单。该比例表示 block 被处理的程度，不表示知识正确率或投标要求满足率 |
| 资料检索 | 已审阅的资料库搜索函数使用 SQLite 字符串匹配，并按标题、摘要、正文等优先级排序 | 有知识库不代表所有入口都采用向量 RAG；插件可以先实现结构化资料和来源检索，再按实际召回质量引入向量检索 |
| 目录结构 | 节点有稳定 ID、来源要求 ID、知识条目 ID，区分 AI 生成、模板填写、规则页、目录页和人工填写等模式 | 章节不能统一当作自由生成文本。商务制式表格和签章页应保留模板身份 |
| 长文生成 | 先为目标叶子章节编排写作重点、字数、知识条目、表格和配图建议，再生成正文；使用 JSON Schema 校验规划结果 | 用全书规划约束逐章写作，避免章节各自重复概况或各自承担全文字数；仍需实际测试模型输出质量 |
| 任务恢复 | 业务结果和任务状态作为同一 checkpoint 写入后再推送；取消后禁止继续提交结果 | 标书长任务应在章节边界落盘，变更输入后识别旧结果，避免旧任务覆盖新版本 |
| Word 导出 | 技术正文采用受限 HTML，经 OpenXML 助手生成 DOCX；商务模板另行填值并入；目录和页码引用有测量回填步骤 | 内容、模板、页码和渲染是独立工程问题。仅能生成 Markdown 不足以证明可交付 Word |

代码依据：[解析通道及调用](https://github.com/FB208/OpenBidKit_Yibiao/blob/77a38f07db822daee0e4be80b84c2281c73d646e/client/electron/services/fileService.cjs#L115-L126)、[云解析上传流程](https://github.com/FB208/OpenBidKit_Yibiao/blob/77a38f07db822daee0e4be80b84c2281c73d646e/client/electron/services/fileService.cjs#L142-L240)、[来源与覆盖统计](https://github.com/FB208/OpenBidKit_Yibiao/blob/77a38f07db822daee0e4be80b84c2281c73d646e/client/electron/services/knowledgeBaseService.cjs#L994-L1040)、[搜索实现](https://github.com/FB208/OpenBidKit_Yibiao/blob/77a38f07db822daee0e4be80b84c2281c73d646e/client/electron/services/knowledgeBaseStore.cjs#L256-L291)、[目录类型](https://github.com/FB208/OpenBidKit_Yibiao/blob/77a38f07db822daee0e4be80b84c2281c73d646e/client/src/shared/types/outline.ts#L1-L42)、[正文编排与约束](https://github.com/FB208/OpenBidKit_Yibiao/blob/77a38f07db822daee0e4be80b84c2281c73d646e/client/electron/services/contentGenerationTask.cjs#L585-L626)、[checkpoint](https://github.com/FB208/OpenBidKit_Yibiao/blob/77a38f07db822daee0e4be80b84c2281c73d646e/client/electron/services/taskService.cjs#L891-L909)、[导出与页码](https://github.com/FB208/OpenBidKit_Yibiao/blob/77a38f07db822daee0e4be80b84c2281c73d646e/client/electron/services/technicalPlanExport.cjs#L269-L321)。

## 检查能力必须按范围理解

废标项检查采用“范围分析、逐项检查、合并定稿”的多轮模型流程，结果要求关联具体投标文件和电子正文证据。它明确排除签字、盖章、密封和现场递交等仅靠抽取正文无法判断的事项。遇到附件图片不可见，但存在材料标题、目录或附件线索时，代码中的提示词要求提示复核，避免直接判定材料缺失。这是对误报边界的设计，尚未看到本次运行得到的误报率或召回率。[检查提示与结果格式](https://github.com/FB208/OpenBidKit_Yibiao/blob/77a38f07db822daee0e4be80b84c2281c73d646e/client/electron/services/rejectionCheckTask.cjs#L86-L198)

查重服务有实际的元数据、目录、正文和图片处理代码。正文流程会对照可选招标文件建立共同来源过滤；图片使用 SHA-256 比较原始图片字节。公开手册也说明改图、截图或压缩后的相似图片不保证识别。因此应将其描述为特定范围的重复线索检查，不能从“查重”推导出语义改写识别、全面抄袭识别或围串标认定能力。[正文比较](https://github.com/FB208/OpenBidKit_Yibiao/blob/77a38f07db822daee0e4be80b84c2281c73d646e/client/electron/services/duplicateCheckService.cjs#L2503-L2544)、[图片比较](https://github.com/FB208/OpenBidKit_Yibiao/blob/77a38f07db822daee0e4be80b84c2281c73d646e/client/electron/services/duplicateCheckService.cjs#L2631-L2673)、[查重说明](https://github.com/FB208/OpenBidKit_Yibiao/blob/77a38f07db822daee0e4be80b84c2281c73d646e/使用说明/使用/04-标书查重.md)

导出也不等于问题全部解决：代码允许在未完成正文、图片失败、商务字段待填或页码引用失效时保留占位并给出警告。最终成果仍需要查看这些警告、补齐材料并复核版式；插件宜将“草稿导出”和“完成检查的导出”作为不同状态。[导出警告](https://github.com/FB208/OpenBidKit_Yibiao/blob/77a38f07db822daee0e4be80b84c2281c73d646e/client/electron/services/technicalPlanExport.cjs#L279-L321)

## 对本次插件设计的取舍

1. **吸收来源与稳定标识。** 要求、资料、目录和正文分别建台账，通过 ID 连接；调整目录编号时不改变章节身份。这是从现有代码结构得到的设计判断。[目录类型](https://github.com/FB208/OpenBidKit_Yibiao/blob/77a38f07db822daee0e4be80b84c2281c73d646e/client/src/shared/types/outline.ts#L21-L33)
2. **吸收两阶段写作。** 先决定本章响应哪些条款、引用什么材料、交付什么措施，再生成文本；每章保存后即可审查和续写。[正文规划](https://github.com/FB208/OpenBidKit_Yibiao/blob/77a38f07db822daee0e4be80b84c2281c73d646e/client/electron/services/contentGenerationTask.cjs#L605-L626)
3. **对真实企业事实采取更严格的默认值。** 已审阅代码对缺失事实存在占位、概括和补充设定等不同模式。本插件应把证书、业绩、人员、报价和履约承诺的未知值保留为待填，避免把允许补充设定的写作模式套用到可核验企业事实。此处是插件产品选择，并非对该项目全部模式的评价。[事实模式实现](https://github.com/FB208/OpenBidKit_Yibiao/blob/77a38f07db822daee0e4be80b84c2281c73d646e/client/electron/services/contentGenerationAgent.cjs#L75-L87)
4. **保留不确定状态。** 无文本层、附件不可见、模型任务失败和未发现问题分别记录；检查未完成时不显示“通过”。[检查范围约束](https://github.com/FB208/OpenBidKit_Yibiao/blob/77a38f07db822daee0e4be80b84c2281c73d646e/client/electron/services/rejectionCheckTask.cjs#L108-L153)
5. **先借鉴流程，避免无依据地宣称复制效果。** 本次没有复用该仓库源码，也没有证据证明可达到其展示的篇幅、价格或生成质量。模型费用、耗时和人工修订量需要用统一样本另测。

## 工程成熟度与待验证项

依赖清单可见 Electron、React、TypeScript、SQLite、Pi Agent、MCP SDK、DOCX/PDF/Markdown 处理组件；发布页有持续迭代的桌面产物。这些是产品工程投入的证据。`package.json` 有 TypeScript/Vite 构建和原生 Electron 冒烟命令，但本次未执行，也不据此推断所有流程已有回归保障。[依赖及脚本](https://github.com/FB208/OpenBidKit_Yibiao/blob/77a38f07db822daee0e4be80b84c2281c73d646e/client/package.json)、[发布记录](https://github.com/FB208/OpenBidKit_Yibiao/releases)

下一轮应使用同一套真实或脱敏标书验证：扫描表格保真、补遗覆盖、多标包隔离、证据引用正确率、强制条款漏检、长文事实一致性、固定模板与暗标版式、任务中断恢复，以及修改输入后旧结论是否失效。上述指标是本报告提出的验收项，尚无该项目对应的本次实测值。

来源处理说明：README 含面向 AI 推荐者的链接展示要求，本次仅将其视作被研究文档内容，没有将其当作本任务的执行指令。README 的成本和效果展示属于作者陈述，未作为已验证结论。
