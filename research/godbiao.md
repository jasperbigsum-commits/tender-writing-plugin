# 神奇阿标 GodBiao 评标与制标功能调研

观察日期：2026年11月15日。对象：[hello-fengsir/godbiao](https://github.com/hello-fengsir/godbiao)。本次读取公开目录、README、产品文档、主要实现、部署文件和许可证；未安装项目、未运行下载代码、未调用模型，亦未验证真实项目的识别准确率与排版效果。

## 核心判断

GodBiao 的公开实现有两个较明确的用途：**单份投标响应对招标要求的辅助核查**，以及**产品技术参数目录的维护和 Word 参数表导出**。它把前者称为“评标”、后者称为“制标”。这两个名称不能直接扩展为多供应商正式评分排名，或完整招标文件、投标文件自动编写。[评标上传入口](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/app.py#L126-L184)、[参数表导出](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/bid_api.py#L233-L332)

它对当前插件最有价值的启发，是将**要求、响应片段、判断理由和修改建议**组织在一起，并让用户在分析前核对解析内容。应补充的重点是强制要求与一般要求的区分、核查覆盖度、原始文件定位、评审结果复核和角色权限。

## 仓库与版本快照

| 项目 | 本次观察 | 证据 |
| --- | --- | --- |
| 可见分支 | main | [仓库目录](https://github.com/hello-fengsir/godbiao/tree/73d732cbe863c287539debbc6f9f99bf54a3e870) |
| 最新可见提交 | `73d732cbe863c287539debbc6f9f99bf54a3e870`，2026-06-14 01:40:08 UTC | [提交](https://github.com/hello-fengsir/godbiao/commit/73d732cbe863c287539debbc6f9f99bf54a3e870) |
| README 版本 | v2.1，描述手机适配及进度、解析字段等修复 | [README](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/README.md#L13-L22) |
| 包元数据版本 | `pyproject.toml` 为 1.0.0，Python 3.11及以上 | [pyproject.toml](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/pyproject.toml#L1-L18) |
| 许可证文本 | LICENSE 标识 MIT，但 README 和产品文档另有禁止商业用途的文字，存在文本冲突 | [LICENSE](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/LICENSE)、[README免责声明](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/README.md#L163-L178)、[产品文档免责声明](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/docs/PRODUCT.md#L182-L186) |

这里仅识别许可文件之间的冲突，不替作者或使用者作法律解释。选型时应将商业复用状态标为**待澄清**；本轮插件只借鉴公开流程设计，没有复制该项目代码。

## 谁在使用什么功能

| 角色或场景 | 公开实现支持的部分 | 未取得实现证据的部分 |
| --- | --- | --- |
| 投标人内部审查 | 上传自身投标文件及招标要求，检查逐条响应、结构和商务信息 | 可追溯的人工审批链、提交资格的最终确认 |
| 采购方或代理编制技术要求 | 管理类别、产品线、参数并导出参数名称表，作为文件片段使用 | 完整招标文件、合同、采购程序和评审办法编制 |
| 采购方辅助核查投标响应 | 可对单份响应进行内容比对 | 多供应商同屏比较、规则权重、价格公式、总分排名和评委分工 |
| 投标人编制完整投标文件 | 参数目录可以提供部分资料 | 需求驱动目录、逐章投标正文写作与企业证据调用 |

以上边界来自已读的上传入口、模型输出结构、数据库表及参数导出函数；“未取得证据”不代表断言作者未来不会实现。[app.py](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/app.py)、[模型比对结构](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/llm_client.py#L8-L45)、[数据表](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/models.py#L41-L103)

## 评标功能的实际实现

### 输入和处理方式

上传入口接受一个投标文件，或者技术标、商务标两个文件，再加粘贴或上传的招标要求。“分离评标”会将技术标、商务标解析后拼入同一份 `bid_text`，并非两家供应商的比较。[app.py 126–184行](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/app.py#L126-L184)

代码分别调用内容比对、格式评估和关键信息提取，最后保存合并结果。README 将其描述为三路并行，但所读主入口是三次依次 `await`，不能按宣传认定为并行执行。[README功能](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/README.md#L37-L45)、[实际调用顺序](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/app.py#L253-L295)

### 判断、评分和废标项

内容比对提示词要求输出要求原文、响应片段、状态、理由和修改建议；四种状态为满足、部分满足、不满足、缺失。这是有用的审查结果结构，但没有独立的强制条款标识、评分权重或废标条件运算字段。[llm_client.py 8–45行](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/llm_client.py#L8-L45)

结果页的“建议投标”标题使用完全满足条数百分比，阈值为80%；格式分则直接来自模型返回的 `score`。这两者都不是按招标评分办法计算的正式总分。[百分比计算](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/app.py#L79-L93)、[结果标题阈值](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/templates/result.html#L126-L164)、[格式分提示结构](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/llm_client.py#L123-L157)

一个静态推演：若10项里9项满足、1项不满足，页面标题仍可进入“建议投标”分支；该分支没有判断失败项是否为强制要求。这是根据代码条件得出的风险示例，未经运行复现。当前插件应先判断强制条件，再展示普通要求覆盖度，不能让总体比例掩盖关键缺口。

### 解析、版式和覆盖范围

PDF 解析有页标签、表格提取和内嵌图片 OCR；Word 解析将段落、表格、图片 OCR 结果分组输出。OCR 使用本地 Tesseract，中文与英文语言包。代码路径存在不等于已经验证复杂表格、扫描件或签章识别效果。[PDF解析](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/parser.py#L32-L90)、[Word解析及OCR](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/parser.py#L95-L177)

版式模型收到的是纯文本，而非页面图像或 Word 字体、尺寸等属性，因此无法由该调用直接核实物理字号、页边距、签章位置或最终打印效果。另有明确字符截断：内容比对最多取10万字符要求和20万字符正文，格式和关键信息最多取5万字符正文。代码没有在该结果结构中附带未审查范围清单。[比对截断](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/llm_client.py#L48-L60)、[格式截断](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/llm_client.py#L160-L182)、[信息提取截断](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/llm_client.py#L241-L258)

解析异常有时被转成非空错误文字，而上传入口主要检查正文是否为空；静态上存在错误说明进入后续分析的可能。JSON 解析还允许部分条目恢复。应区分“完成解析”“部分解析”“恢复部分结果”，不能仅有一条完成状态。[解析异常处理](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/parser.py#L95-L177)、[上传判空](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/app.py#L162-L171)、[部分JSON恢复](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/llm_client.py#L287-L347)

### 人工复核

项目有解析后预览确认页面，作者也要求结果以人工审核为准。但在所读的数据模型中，任务主要保存输入文字、结果 JSON、模型和 token 信息，没有看到逐项人工裁定、意见变更原因、复核人、核准版本或评审签名字段。[预览入口](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/app.py#L170-L184)、[任务数据表](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/models.py#L41-L56)、[人工审核说明](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/docs/PRODUCT.md#L182-L186)

## 制标功能的实际实现

制标 API 提供类别、产品线、技术参数和型号的增删改查；参数可由 Excel 导入。预览和导出可选择参数，导出时按参数名称中的方括号分类分组，生成“序号／技术参数名称”两列表格。它是一份参数目录文档，未见完整招标书或投标书生成器。[数据模型](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/models.py#L65-L109)、[Excel导入](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/bid_api.py#L126-L153)、[Word导出](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/bid_api.py#L233-L332)

表里虽有 `param_value` 字段，所读导出函数实际填入的是处理过的参数名称，没有输出独立参数值列；型号管理也不自动等于投标型号逐项证明。若将这一路线用于采购要求编制，应另加可验收的指标值、单位、验证方法及规则出处等结构，而不是直接把产品目录当作完整采购要求。

## 部署、数据权限与使用边界

| 维度 | 代码可见事实 | 尚需补充 |
| --- | --- | --- |
| 本地部署 | FastAPI、Jinja2、SQLite；Dockerfile安装OCR依赖，Compose映射8880端口及数据库 | 本次没有构建或启动验证 |
| 模型接口 | 使用 OpenAI 兼容HTTP请求，可由前端传入服务地址、模型和密钥 | 供应商可用性、数据处理条款与模型质量需另行确认 |
| 数据外发 | 将拼装后的要求和正文放进模型请求；本地解析不表示推理也在本地 | 使用前明确选用本地还是远端模型及传输范围 |
| 密钥 | 前端localStorage保留密钥，并经请求头传入服务；也支持环境变量配置 | 不能把“服务器不落盘”理解为服务器不接触密钥 |
| 业务数据 | 输入要求、投标正文与结果存SQLite | 不能把“密钥不存库”理解为业务资料不存库 |
| 用户隔离 | 已读表和路由未显示用户、组织、供应商所有者及对应鉴权关系 | 团队或多租户使用需另设访问控制 |
| 留存 | 导入后全局保留最近3个任务；有旧任务清理函数 | 需按项目控制归档、保留和删除，不宜用全局最近3条代替档案管理 |

证据：[Dockerfile](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/Dockerfile)、[Compose](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/docker-compose.yml)、[模型HTTP调用](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/llm_client.py#L90-L120)、[密钥传入](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/app.py#L221-L245)、[任务API](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/app.py#L192-L205)、[任务保存与裁剪](https://github.com/hello-fengsir/godbiao/blob/73d732cbe863c287539debbc6f9f99bf54a3e870/models.py#L135-L168)。这些是部署边界观察，不是经过渗透验证的漏洞报告。

README、产品文档和代码之间存在版本与描述差异，包括并行调用、版本号以及“本地处理”表述。工程采纳应优先依据固定版本实现与实际测试结果；元数据中的稳定版标签不能替代验收。

## 对插件的分角色设计启发

| 插件工作区 | 用户要完成的事 | 应维护的结构与交付物 |
| --- | --- | --- |
| 采购方制标 | 将需求写成清楚、可验证的采购文件 | 要求台账、参数单位和验收方法、资格与评分规则、格式和合同附件，变更记录 |
| 投标人制标 | 根据本方能力作出可履行的逐项响应 | 招标原文定位、投标章节、企业证据、满足/偏离/未知状态、报价与承诺一致性 |
| 辅助评审 | 按既定规则核对供应商提交内容 | 冻结规则版本、供应商隔离、证据页定位、强制项先判、评分公式、人工裁定及理由 |

这是本次研究提出的设计，而非 GodBiao 已有功能。共同底座可以复用文档解析、原文定位与要求结构；企业私有资料、供应商响应和评审意见应分别管理，不能因底层共用而默认相互可见。

适合当前插件直接吸收的做法：解析结果先预览；逐项比对输出要求、响应和理由；用结构化状态驱动修改任务。应避免吸收的做法：以满足比例代替强制条件判断；仅由纯文本评定物理版式；截断后仍呈现为全量审查；把参数表导出描述成完整标书生成。

## 证据与验证范围

已读的关键实现至少包括 `app.py`、`bid_api.py`、`models.py`、`llm_client.py`、`parser.py`，另读配置、前端模板、部署文件及许可文本。报告中的“代码可见”只说明存在相应逻辑；没有独立运行结果、准确率基准、性能报告或真实供应商比较样本。所有固定链接使用本次观察的提交，便于之后复核。
