# ProposalLLM 源码调研

观察日期：2026年11月15日。范围：公开 README、两个 Python 实现文件、依赖清单、许可证及提交记录。未安装依赖，未运行下载代码，未调用模型，也未验证仓库内示例文档的生成质量。

## 判断

ProposalLLM 更接近面向产品售前的“Excel 要求矩阵驱动 Word 拼装脚本”。它最值得借鉴的是**要求逐条应答、产品内容模块化复用、章节编号回填**。当前公开实现不足以作为完整的标书 Agent 平台：需求结构和模块匹配主要由人工填写，代码没有展示独立的招标文件解析、语义检索或提交前审查流程。[README](https://github.com/William-GuoWei/ProposalLLM/blob/a63290bd12a3ac6c6b52638a42d3c69f46d8c667/README.md)、[生成主循环](https://github.com/William-GuoWei/ProposalLLM/blob/a63290bd12a3ac6c6b52638a42d3c69f46d8c667/Generate.py#L455-L554)

## 仓库快照

| 项目 | 观察结果 | 证据 |
| --- | --- | --- |
| 仓库 | William-GuoWei/ProposalLLM，默认可见分支 main | [仓库](https://github.com/William-GuoWei/ProposalLLM) |
| 最新可见提交 | `a63290bd12a3ac6c6b52638a42d3c69f46d8c667`，2024-11-14 11:16:40 UTC | [提交](https://github.com/William-GuoWei/ProposalLLM/commit/a63290bd12a3ac6c6b52638a42d3c69f46d8c667) |
| 实现规模 | 根目录公开两个 Python 实现：`Extract_Word.py`、`Generate.py`；另有 Word 与 Excel 文件 | [根目录](https://github.com/William-GuoWei/ProposalLLM/tree/a63290bd12a3ac6c6b52638a42d3c69f46d8c667) |
| 许可证 | 根目录 `LICENSE` 标识 Apache License 2.0；这里只识别文件，不作许可证合规结论 | [LICENSE](https://github.com/William-GuoWei/ProposalLLM/blob/a63290bd12a3ac6c6b52638a42d3c69f46d8c667/LICENSE) |
| 维护判断 | 本次按提交时间降序查询，最近可见提交仍为上述日期；只能说明公开仓库的可见更新情况 | [提交记录](https://github.com/William-GuoWei/ProposalLLM/commits/main/) |

项目页面的关注量不作为质量、正确率或可部署性的依据。README 中关于模型免费额度的说法属于原文历史描述，本次没有确认其当前有效性。

## 实际实现路径

```text
产品手册 Template.docx
  → Extract_Word.py 按 Heading 1/2/3 拆分
  → 编号加标题命名的 Word 功能模块

人工维护的需求对应表.xlsx
  B 列 分类标题
  C 列 具体要求
  G 列 产品功能模块编号
  → Generate.py 逐行处理
  → 生成应答与标题，复制对应模块或由模型补写
  → 回写 D/E/F 列，并保存目标 Word
```

这是一条“确定性的文档拼装 + 模型文本生成”路线。图中的字段与写回关系可从主循环直接核对；并非本次运行得到的流程记录。[Generate.py 455–554行](https://github.com/William-GuoWei/ProposalLLM/blob/a63290bd12a3ac6c6b52638a42d3c69f46d8c667/Generate.py#L455-L554)

### 产品内容拆分

`Extract_Word.py` 按 Word 标题样式维护三级计数，逐块遍历段落与表格；把正文、表格和部分图片写入独立文档。文件命名含章节编号，供后续 G 列进行匹配。代码也给出了图片最大宽度处理。[标题计数](https://github.com/William-GuoWei/ProposalLLM/blob/a63290bd12a3ac6c6b52638a42d3c69f46d8c667/Extract_Word.py#L15-L34)、[模块写入](https://github.com/William-GuoWei/ProposalLLM/blob/a63290bd12a3ac6c6b52638a42d3c69f46d8c667/Extract_Word.py#L37-L86)、[正文抽取](https://github.com/William-GuoWei/ProposalLLM/blob/a63290bd12a3ac6c6b52638a42d3c69f46d8c667/Extract_Word.py#L127-L198)

这提供了可理解、可人工修订的模块复用方式，但与企业知识库仍有距离：本次阅读的实现没有资质有效期、投标主体隔离、证据审核状态或向量召回流程。上述判断限于所读的公开脚本。

### 需求驱动写作

`Generate.py` 读取 B/C/G 列，生成短标题与逐条应答，按开关添加二级或三级章节，并回填应答及章节号。找到了 G 列对应的模块时复制内容，未找到时调用模型生成说明。该行为在代码中可见；生成正确率、原始格式保真度和大文档表现均未运行验证。[模块匹配](https://github.com/William-GuoWei/ProposalLLM/blob/a63290bd12a3ac6c6b52638a42d3c69f46d8c667/Generate.py#L246-L266)、[生成与回填](https://github.com/William-GuoWei/ProposalLLM/blob/a63290bd12a3ac6c6b52638a42d3c69f46d8c667/Generate.py#L468-L541)

### 模型与部署

配置写在脚本全局变量里，包含 OpenAI 和百度调用相关参数；主循环实际调用的是使用百度接口的函数，另有 OpenAI 调用函数。代码带有旧式 `openai.Completion.create` 写法，而依赖清单固定 `openai==1.39.0`。这构成需要适配核验的兼容性风险，本次未执行该调用。[模型配置与调用](https://github.com/William-GuoWei/ProposalLLM/blob/a63290bd12a3ac6c6b52638a42d3c69f46d8c667/Generate.py#L25-L112)、[requirements.txt](https://github.com/William-GuoWei/ProposalLLM/blob/a63290bd12a3ac6c6b52638a42d3c69f46d8c667/requirements.txt)

从公开文件看，运行形态是本地 Python 脚本配合预置 Word/Excel 文件，而非提供前后端、用户权限、任务队列或 API 的多用户服务。依赖清单同时包含旧 `docx` 和 `python-docx` 等包；实际环境兼容情况需要另外测试，不能把安装说明等同于部署成功证据。

## 重要缺口

| 发现 | 代码证据 | 对插件设计的影响 |
| --- | --- | --- |
| 应答提示词预设正向承诺 | `Prompt_Answer` 要求先输出“完全支持”；主循环先生成应答，后查找模块 | 响应状态必须由招标要求与企业证据共同判断，不能从措辞模板推出满足 |
| 缺少资料时仍生成正文 | 模块不存在则调用模型直接生成内容 | 资料不足要保留未知状态、待填项和补证任务 |
| 文件修改缺少版本分离 | 载入的 Excel 和目标 Word 按原变量路径保存 | 输入只读，输出版本化，保留导出回执 |
| 模块中表格图片被跳过 | 遍历单元格 run 检出图片后执行 `pass` | 必须验证图片、嵌入件和签章等非文本信息 |
| 部分路径存在静态代码风险 | 复制函数在第一次读取局部 `current_level` 之前未初始化 | 工程采纳前需补自动化测试；不能据 README 声称开箱即用 |
| 不具备完整任务运行状态 | 网络调用及写文档集中在脚本执行流程中 | 长文项目应支持章节级状态、失败重试、断点恢复和审查快照 |

证据：[提示词](https://github.com/William-GuoWei/ProposalLLM/blob/a63290bd12a3ac6c6b52638a42d3c69f46d8c667/Generate.py#L34-L47)、[调用顺序与缺失模块分支](https://github.com/William-GuoWei/ProposalLLM/blob/a63290bd12a3ac6c6b52638a42d3c69f46d8c667/Generate.py#L478-L541)、[保存位置](https://github.com/William-GuoWei/ProposalLLM/blob/a63290bd12a3ac6c6b52638a42d3c69f46d8c667/Generate.py#L550-L554)、[复制函数](https://github.com/William-GuoWei/ProposalLLM/blob/a63290bd12a3ac6c6b52638a42d3c69f46d8c667/Generate.py#L386-L450)、[单元格图片处理](https://github.com/William-GuoWei/ProposalLLM/blob/a63290bd12a3ac6c6b52638a42d3c69f46d8c667/Extract_Word.py#L179-L195)。

`current_level` 问题是基于 Python 局部变量规则的静态推断：含标题的模块走到该分支时可能触发 `UnboundLocalError`。本次没有执行仓库代码，因此没有将其写成已复现故障。

## 能力边界

| 能力 | 证据等级 | 本次判断 |
| --- | --- | --- |
| 人工整理的要求矩阵驱动生成 | 代码可见 | 是核心控制面 |
| 产品资料模块复用 | 代码可见 | 文件编号匹配，非向量检索 |
| 点对点应答和章节号回填 | 代码可见 | 适合借鉴可追溯矩阵结构 |
| Word 标题、正文、表格和部分图片拼装 | 代码可见 | 未验证保真度，存在跳过图像的分支 |
| 招标 PDF/OCR 自动研读 | 未取得实现证据 | 所读实现以既有 Excel/Word 为入口 |
| 证据有效期与主体隔离 | 未取得实现证据 | 不应作为企业资料治理底座 |
| 语义真实性与偏离判断 | 存在明确风险 | 提示词预设正向回答 |
| 长文质量、稳定性与成本 | 未运行验证 | 不作性能或价格结论 |

## 对当前插件的建议

1. 采用要求矩阵作为控制面，分别记录原文定位、是否强制、评分项、响应状态、章节和证据；保持机器可校验。
2. 将历史标书按模块复用，但同时保留来源、主体、有效期与适用范围；复制不能自动继承“已核验”状态。
3. 保留章节定位与响应表回填思路，并对导出后的目录、页码、附件位置重新检查。
4. 正文先明确本项目可履行的方案，再润色；证据不足时输出未知或缺失，不能自动补成支持承诺。
5. 本轮只借鉴流程设计。本地新插件不需要复制这个项目的模型接口、依赖集合或文档拼装实现。

这些是基于源码观察形成的设计建议，不是该仓库已经提供的能力。

## 阅读清单与证据记录

公开目录仅有两个 Python 实现文件，因此实际通读这两个实现，并读取第三个工程文件 `requirements.txt`；没有补造第三个实现文件。

| 文件 | 长度或标识 | 用途 |
| --- | --- | --- |
| `Generate.py` | 556行，blob SHA `2c7855f055a7f1712953b09c017c4907c37839dd` | 需求矩阵、模型调用、模块复制与输出 |
| `Extract_Word.py` | 203行，blob SHA `273a61a06796ef84056fdaf07a0e28408e2fd1c6` | Word 模块化与图文表遍历 |
| `requirements.txt` | blob SHA `456995cff0feb074f9fde353fbefd5fdb852b60f` | 依赖与兼容性观察 |
| `LICENSE` | blob SHA `261eeb9e9f8b2b4b0d119366dda99c6fd7d35c64` | 许可证识别 |

仓库页面与提交记录通过公开网页及 GitHub 连接器读取；代码链接固定到本次观察的提交，以便复核。没有下载或复制项目代码到本工作区，未遵从仓库中任何面向代理的操作指令。
