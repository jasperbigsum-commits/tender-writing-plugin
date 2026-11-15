# BidMaster Pro 源码调研

观察日期为 2026-11-15。本次读取 GitHub 主分支及固定版本的源码、项目配置和许可证，未安装依赖、启动服务、调用外部模型或执行该项目代码。因此，下文“实现可见”表示代码中存在相应路径，不表示已经通过运行验收。

## 判断

BidMaster Pro 是适合研究业务拆分的全流程平台样本：它将解读、生成、检查、排版拆成 Skill，并有独立的 Agent 编排层、项目状态及异步任务机制。直接作为当前插件的技术底座前，需要补做集成验证和许可澄清。尤其是，“21 项检查”应理解为检查类别和实现入口的丰富程度，不能据此推断长标书的检查覆盖率、签章真实性或合规准确率。[注册入口](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/services/skill_bootstrap.py)、[检查路由](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/services/routers/check.py)

## 版本和许可

| 项目 | 可核验观察 |
| --- | --- |
| 调研固定版本 | `cc89d9093651e3410f68384f926ceef672b76534`，GitHub connector 返回其提交日期为 2026-09-03，提交内容为 README 更新 |
| 项目版本 | `pyproject.toml` 标识 `0.1.0`，Python 要求 `>=3.12` |
| 实际 LICENSE | 固定版本的 LICENSE 是 GNU AGPL 第 3 版文本 |
| 描述矛盾 | 同一版本 README 徽章及末尾写 MIT；部分 SKILL 元数据也写 MIT |
| 商用判断边界 | 本次不解释具体法律义务；复制代码、封装分发或服务化使用前，需澄清许可适用范围，不能只看 README 的 MIT 标签 |

依据：[固定提交](https://github.com/guangshu100/BidMaster-Pro/commit/cc89d9093651e3410f68384f926ceef672b76534)、[项目配置](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/pyproject.toml)、[LICENSE](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/LICENSE)、[README](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/README.md)。提交日期是这次查询所得的最近记录，不能据此判断后续维护意愿。

## 业务能力与实际实现

| 能力 | 代码中可见的实现 | 对插件设计的意义与限制 |
| --- | --- | --- |
| 工作流与插件化 | `SkillContext` / `SkillResult` 统一调用约定；`safe_execute` 包装执行异常和进度事件；加载器读取分类目录内的 SKILL.md 和 Python 实现；LangGraph 根据 DSL 建图 | 可借鉴“业务技能 + 统一输入输出 + 可持久化项目”拆分。这里的 Python Skill 引擎不是可以直接装入 Codex 的插件格式，需要适配 |
| 人工阶段复核 | GateKeeper 将复核人、时间和说明写到项目 `.stages/<stage>/.reviewed` 文件 | 有阶段控制的设计；`is_passed` 仅检查文件存在，未与正文/资料哈希绑定。资料发生变化时，旧复核是否仍应有效需要另外处理 |
| 企业资料辅助写作 | KnowledgeAssist 先查询指定资料库，再尝试全局检索，将资料片段和相关度注入章节提示 | 便于复用，但来源是文本片段，不等同于资质真实性校验。全局降级路径有静态接口不一致，见下节 |
| 检索 | HybridRetriever 有向量召回、关键词召回和 RRF 融合；关键词函数名为 `_bm25_search`，实际计算是 TF-IDF 向量相似度 | 可以借鉴混合检索结构；不能将这个实现描述为标准 BM25，当前读取路径也未发现单独的语义重排模型或公司画像过滤参数 |
| 长章节生成 | 区分数据依赖章节；缺资料时给占位提示；章节目标超过 4000 字且有大纲时拆小节，最多 3 路并发，按序合并，并有有限次数续写 | 是比单次长提示更具体的写作策略。生成失败的小节会返回空字符串并被合并时略去，仍需用完整性台账发现缺失 |
| 规则检查 | 合规、资质、保证金、签章、有效期、实质性参数、一致性等分别有 Skill 和 UI/路由入口 | 类别丰富；主要抽查的业务检查是调用 LLM 返回 JSON，并非每项都有独立确定性规则证明 |
| 查重 | `difflib`、Jaccard、字符 n-gram、滑动窗口、章节结构相似及可选 LLM 语义分析 | 相比只问 LLM“是否雷同”更具体。外部比较只使用传入的有限参考文本，不能描述为全网查重或违法认定 |
| OCR | MinerU 抽象客户端含云端和自部署模式，提交、查询、下载结果和 ZIP 内 Markdown 解析路径 | 集成设计可见；本次未用真实扫描件、云端 Key 或自部署服务检验协议及版面恢复质量 |
| Word 导出 | 从章节树和正文生成封面、标题、表格、页码，允许配置字体、页边距和行距 | 可借鉴独立文档引擎；本次发现静态名称作用域问题，不能声称该类已成功导出 |

依据：[Skill 基类](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/core/skill_engine/base.py)、[加载器](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/core/skill_engine/loader.py)、[编排器](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/core/agent_engine/orchestrator.py)、[阶段复核](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/core/agent_engine/gate_keeper.py)、[资料辅助](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/services/generate/skills/knowledge_assist_skill.py)、[检索器](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/core/rag_engine/retriever.py)、[正文生成](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/services/generate/skills/content_gen_skill.py)、[查重实现](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/services/check/skills/duplicate_check_skill.py)、[MinerU 客户端](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/core/ocr/mineru_client.py)、[Word 导出](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/services/format/skills/bid_docx_export_skill.py)。

## 需要重点验证的差距

**长标书检查存在明确的输入截断。** 合规 Skill 将招标和投标文本分别截取前 6000 字符；保证金分别取 4000；签章分别取 3000；实质性参数分别取 5000。若后部条款没有在其他路径中被单独调入，该调用就无法看到它们。这是源码事实；整体工作流能否通过其他预处理补偿，需要端到端样例验证。对本插件而言，应保留按页/条款的覆盖清单及未读范围，不能仅增加检查类别数量。[合规](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/services/check/skills/compliance_check_skill.py#L47-L54)、[保证金](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/services/check/skills/deposit_check_skill.py)、[签章](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/services/check/skills/signature_check_skill.py)、[实质性参数](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/services/check/skills/mandatory_req_check_skill.py)

**签章检查的名称大于本次所见的验证手段。** 抽查的签章 Skill 以文本询问模型是否有签字、公章、CA 等，没有传入图像、数字签名验证结果或证书链。因此只能视作签章事项提示或文本线索审查。模型输出 pass 不能证明盖章图像存在、CA 有效或实际密封完成。[签章检查](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/services/check/skills/signature_check_skill.py)

**全局资料检索降级存在接口不一致。** KnowledgeAssist 第 89 行调用 `retrieve(query, top_k=...)`，而 HybridRetriever 第 23–28 行的声明要求 `collection_name`；调用周围的异常处理返回空列表。静态推断该降级路径会丢失资料上下文，指定资料库路径则显式传入 collection_name，应分别验收。本次未执行该路径。[调用处](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/services/generate/skills/knowledge_assist_skill.py#L78-L93)、[接口定义](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/core/rag_engine/retriever.py#L23-L28)、[指定资料库路径](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/services/routers/knowledge.py#L250-L272)

**独立 Word 导出类存在静态名称作用域问题。** `_build_document` 在自身函数内导入 Cm、RGBColor 和 qn，随后调用的 `_set_page_format`、`_set_styles` 却直接使用这些名称；模块顶部没有相应导入。按 Python 名称作用域规则，这些函数局部导入不能供兄弟方法使用。应先修复并以真实 DOCX 渲染测试验证，再将该类视作可用组件。此判断来自静态阅读，未执行；仓库还存在其他导出路径，不能据此认定整个项目所有导出均不可用。[源码第 49–117 行](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/services/format/skills/bid_docx_export_skill.py#L49-L117)

**“全部检查”与类别总数需要分开记录。** `_do_full_check` 的实现说明是并行执行 15 个 Skill；另有多个单项检查接口和枚举类别。因而产品宣传中的 21 项，不应直接转写为“一次点击一定运行全部 21 项”。选择了什么、成功了什么、失败和跳过了什么，应进入报告。[全部检查工作函数](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/services/routers/check.py#L418-L546)、[检查类型](https://github.com/guangshu100/BidMaster-Pro/blob/cc89d9093651e3410f68384f926ceef672b76534/services/models.py#L35-L57)

## 对本次插件的落地建议

以下属于依据源码作出的设计建议，不是对原项目的功能描述。

1. 保留解读、写作、检查和文档输出的能力边界，用当前宿主模型执行语义工作，本地工具管理文件和确定性校验。
2. 用要求 ID 贯通原文、响应矩阵、章节、企业证据和审查结论。长文件按页或条款切分，并显式报告读取进度与缺失范围。
3. 企业资质、人员、业绩等章节缺少真实资料时保留待填，不让模板或模型补造事实；对资料召回为空、失败、过期分别提示。
4. 复核记录绑定项目版本或内容摘要；招标补遗、正文、报价或附件变化后使相关复核失效。
5. 将格式渲染、签章核验和提交动作独立处理，区分“导出文件”“基础检查完成”和“提交前核验完成”。
6. 当前阶段借鉴数据契约和流程拆分，自行实现必要工具；在许可矛盾澄清前，不将本仓库代码直接打包进插件。

## 研究范围和置信度

结构、函数参数、输入截断、依赖和许可证文本判断置信度高，因为直接读取了固定版本文件。多组件集成、OCR 服务兼容性、企业隔离、生成质量、耗时成本和真正的投标合规效果未做运行验证，置信度未建立。本调研也未将仓库 Star 数、README 截图或检查类别数作为质量证明。
