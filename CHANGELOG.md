## [Unreleased]

### 🐛 Bug 修复 (Bug Fixes)
- **同名图书数据隔离**: 增强简介、评分和目录改为优先按书库相对路径匹配；目录表自动从文件名唯一键迁移为路径唯一键，避免不同分类下同名图书串数据。
- **文件操作安全**: 移动、重命名、删除和元数据写入限制在已配置图书目录内，拒绝 `../` 越界路径；目标同名文件存在时明确报错，不再静默覆盖。
- **退出与分析进程回收**: 分析成功、失败、超时和取消后统一回收子进程与队列；窗口关闭后主动停止 Uvicorn，降低同步或 AI 调用后退出卡死风险。
- **配置原子保存**: 本地及同步配置使用临时文件和原子替换写入，避免退出或并发保存留下半截 JSON。
- **静态资源缓存**: 桌面端 HTML/JS/CSS 响应使用 `no-store`，避免覆盖安装后 WebKit 继续加载旧脚本。
- **OpenRouter 模型路由**: 带供应商子路径的模型也保留外层 `openrouter/`，避免被 LiteLLM 错误路由到 DeepSeek 等官方接口。
- **自定义 AI 验证连接**: 验证连接复用 LiteLLM provider/model 归一化逻辑，自动补齐 `openrouter/`、`openai/` 等前缀，修复 `LLM Provider NOT provided` 误报。
- **在库详情首次加载**: 在库选中图书后，详情渲染完成会主动刷新专门的增强简介和目录接口，避免首次选择时只显示旧缓存或空状态。
- **增强简介来源回退**: 自动模式下如果“文件内置”或后端返回的首选来源为空，会回退到数据库/另一有效来源并同步按钮状态，避免首次进入时正文区域空白。
- **桌面退出卡死规避**: 同步成功后清理未同步标记，退出时不再通过 `beforeunload` 阻塞桌面 WebView，避免同步后退出卡住。
- **分析按钮状态复位**: 修复“开始信息及简介分析”完成后主按钮仍显示“停止分析”的问题。
- **本地目录建议接口**: 修正 `/api/local/suggest-directories` 的参数传递，匹配前端调用并返回稳定的 `success/suggestions` 结构。
- **同步连接恢复**: 数据库同步/查重分析前刷新 SQLite 单例连接，避免云同步或外部替换数据库后出现偶发 `disk I/O error`。
- **预览目录滚动**: 预览弹窗左侧目录面板限制溢出，长目录由内部目录区域滚动显示。

### ✅ 验证 (Validation)
- 新增同名图书简介/目录隔离、旧目录表迁移、路径越界和同名覆盖保护测试；真实数据库副本迁移后目录记录数保持一致且 `integrity_check=ok`。
- 补充 LiteLLM provider/model 归一化测试，覆盖未带 provider 前缀的自定义模型。
- 补充本地分类和目录建议接口测试。
- 完成设置、同步、查重、云同步、预览、目录识别、ISBN、主分析按钮等前端交互冒烟测试。

## [v0.8.3] - 2026-05-20

### ✨ 新增功能 (New Features)
- **轻量只读预览**: 图书详情新增 PDF/EPUB 预览按钮；PDF 使用现有 PyMuPDF 按页内存渲染，EPUB 只读提取前几章安全正文片段，不写回原书文件，也不生成临时解包文件。
- **预览与同步界面优化**: EPUB 预览增加目录区并扩大正文读取量；PDF 预览弹窗加大并修正翻页控件对齐；同步按钮改为明确的“本地 → 云端 / 云端 → 本地”方向说明。
- **增强简介新旧表同步**: 新增 `scripts/sync_insight_summaries.py`，将 `enhanced_insights.summary_v1` 中更完整的新版增强简介回填到旧展示表 `enhanced_summaries`，并按当前配置目录用相对路径、文件名、标题/作者映射旧机器路径，生成桌面同步记录。

### 🐛 Bug 修复 (Bug Fixes)
- **增强简介读取兜底**: 详情读取会检查新表 `summary_v1`，当它比旧展示表更详细时优先展示，避免同一本书的新旧摘要表不同步。
- **跨机器路径适配**: 增强简介读取在路径/文件名不一致时增加标题和作者匹配，降低旧机器绝对路径导致的摘要丢失。
- **来源切换位置优化**: 顶部兜底来源提示改为紧凑 tooltip；增强简介/目录的“数据库 / 文件内置”切换移到标签栏右侧，减少上下联动混乱。
- **目录识别联动修复**: PDF 没有内置书签时，从前几页文本中识别常见目录结构；EPUB 增加 NAV 文档和章节标题兜底，减少目录无法自动读取的问题。
- **跨模式路径同步修复**: 修正入库整理与在库管理切换后仍沿用旧图书路径的问题，避免目录和增强简介请求读错文件。
- **库内目录懒加载修复**: 在库管理数据库无目录缓存时，自动只读 EPUB/PDF 内置目录并写入应用数据库缓存，不修改原书文件。
- **AI 目录触发优化**: AI 目录整理先判断内置目录质量，目录可用时直接使用内置目录，只有缺失或过弱时才进入 AI 整理/内容提取。
- **增强简介同步修复**: 前端为增强简介请求加入取消和过期响应保护，避免切换图书或重复点击时旧结果覆盖当前图书。
- **异步状态加固**: 分析、增强简介、目录识别和详情懒加载现在按请求归属清理状态，避免旧请求结束时清掉新请求的 loading 或按钮状态。
- **增强简介联动修复**: “开始信息及目录分析”开启增强简介时会联动生成，并显示加载/失败状态；生成完成后只刷新当前图书，避免加载到其他图书的结果。
- **AI 目录持久化修复**: 数据库保留 AI 生成的文本目录，不再因为结构化条目为空而丢失目录结果。
- **目录编码容错修复**: 清理 PDF/EPUB 目录中的非法 Unicode surrogate 字符，避免目录保存和接口返回时出现 UTF-8 编码异常。
- **同步误报修复**: 启动同步检测改为比较数据库核心内容指纹，不再因为 SQLite checkpoint 或目录缓存更新时间变化误判“本地数据较新”。
- **同步性能修复**: 大数据库同步状态检测保留核心数据精确比较，但目录/章节缓存改用快速签名，避免启动、云同步按钮和设置页刷新被全量缓存 hash 卡住。
- **同步/查重弹窗恢复**: 数据库同步与图书馆查重接口增加前端超时、错误态和重试按钮，避免接口慢返回时弹窗一直转圈。
- **云同步按钮修复**: 手动云同步入口增加重复点击保护和超时错误提示，点击后不再因为状态检测慢而表现为无响应。
- **顶部 tooltip 样式统一**: 顶部已启用图标和“兜底来源：数据库优先”的 tooltip 统一使用绿色边框/文字样式。
- **分析按钮文案优化**: “信息、简介、目录”同时启用时，主按钮使用“开始信息、简介及目录分析”，避免重复出现“及”。
- **Gemini 退出崩溃修复**: Gemini SDK 改为懒加载，并强制使用 REST transport，避免打包应用普通启动或退出时触发 gRPC 原生线程崩溃。
- **TOC 缓存清理**: 数据库目录缓存不再保存 EPUB 内部 `href`/`anchor`/`target_index` 跳转字段，避免外部库迁移或同步时把 `text/part0001.html#...` 误当作真实路径。
- **TOC 质量过滤**: 目录缓存会过滤 `part0001.html`、`*_split_001.html` 这类文件名式目录标题，避免把 EPUB 内部章节文件名当作有效目录展示。
- **TOC/增强简介维护脚本**: 新增 TOC 缓存路径噪声清理脚本，并保留桌面 Markdown 报告；增强简介同步继续按当前库路径、文件名、书名作者和结构化评分匹配，不按旧机器路径直接覆盖。
- **Calibre 外部工具检测**: `ebook-convert` 和 `fetch-ebook-metadata` 统一走外部 Calibre 检测，补齐 Apple Silicon 常见的 `/opt/homebrew/bin`，并支持环境变量指定工具路径；应用包仍不内置 Calibre。
- **历史记录说明更新**: 文档明确当前转移历史保存在本地数据库 `transfer_logs`，旧版 `图书转移记录.md` 只用于迁移或人工留档。
- **同步文件清理**: 同步校验会清理空的 SQLite `-wal` 和无待写入数据的 `-shm`，减少 iCloud 目录里的无效旁路文件。
- **配置同步修复**: iCloud 同步目录中的 `preferences.json` 与 `ai_config.json` 会合并进当前配置，同时保留本机路径设置。
- **同步备份简化**: 数据库覆盖前只保留单个 `book_data.db.backup`，旧的 `.bak` / `.bak_sync` 会自动归并清理。
- **本地工具接口修复**: 修正 ISBN 查询、本地分类、查重、本地识别和目录建议的请求模型，匹配前端实际 payload。
- **错误提示归一化**: 前端增加统一 API 错误解析，对 AI 503 高峰、API Key/额度、服务连接失败等场景显示更明确的提示。
- **前端渲染安全加固**: 目录、简介兜底渲染和批量悬浮预览增加 HTML 转义，避免异常元数据污染界面。

### 📦 打包与依赖 (Packaging)
- **补齐运行依赖**: 添加 `ddgs`、Google OAuth、PDF/EPUB 解析和 pywebview 相关依赖，修复新环境和打包环境缺包问题。
- **依赖冲突修复**: 将 `google-auth` 固定到兼容 `google-auth-oauthlib` 的版本，并升级 `primp` 以匹配 `ddgs`。
- **PyInstaller 完整性**: 补充 `ddgs`、`python_multipart`、Google Drive 等 hidden imports，并显式打包 `drive.v3.json`。
- **PyMuPDF 打包补强**: 显式加入 `pymupdf` hidden import，兼容新版 PyMuPDF 的模块拆分。
- **LiteLLM 打包瘦身**: PyInstaller 仅收集 LiteLLM completion 运行时，排除 proxy/UI/test 等可选模块，减少包体和无关依赖告警。
- **依赖分层**: 新增 `requirements-dev.txt`，测试和类型检查依赖不再进入运行时依赖安装；移除未使用的 `duckduckgo_search` 旧包。
- **签名顺序修复**: Google API 冗余资源清理后自动重新 ad-hoc 签名，避免包内文件删除导致 `codesign` 校验失败。
- **冻结应用日志路径修复**: 打包应用运行时改为写入 `~/.book_organizer/logs`，避免在 `.app/Contents` 内生成日志导致签名失效。
- **构建前置校验**: `build_standalone.sh` 新增 `pip check`、关键模块导入检查和 Python 3.11-3.13 版本约束。

### ✅ 验证 (Validation)
- `pytest` 通过。
- `ruff` 通过。
- `pip check` 通过。
- macOS `.app` 构建、签名校验和冻结包启动冒烟测试通过。
- 新增 GitHub Actions CI，自动执行依赖检查、Python 测试、Ruff 和前端 JS 语法检查。
- 更新开发测试/构建文档，统一当前端口、Python 版本和构建脚本路径。

## [v0.8.2] - 2026-03-24

### ⚡️ 优化 (Optimizations)
- **默认端口调整**: 将默认服务端口从 `8000` 更改为 `18000`，以避免与 omlx/ollama 等常见系统服务冲突。
- **端口自动切换**: 增强了端口占用检测逻辑，若 `18000` 被占用，将自动向上寻找可用端口。

## [Historical Unreleased Notes]

### ✨ 新增功能 (New Features)
- **AI Agent Skill 提取**: 将 BookOrganizer 核心能力封装为独立的 AI Agent Skill (`BookOrganizer-Skill`)。
  - 完美支持 Claude Code、OpenClaw 等 AI Agent 工具。
  - 支持通过环境变量（`BOOK_ORGANIZER_APP_DIR`）独立克隆和运行。
- **全文搜索优化**: 引入 SQLite FTS5 索引加速 `enhanced_summaries` 的模糊匹配，显著提升搜索响应速度。
- **代码健壮性**: 在数据库查询中添加 FTS5 自动同步索引逻辑与 LIKE 语义回退机制，确保搜索稳定性。

### 🐛 Bug 修复 (Bug Fixes)

- **批量处理阻塞修复**: 修复了在批量处理时 FastAPI 抛出 `cannot schedule new futures after interpreter shutdown` 错误的问题。将网络阻塞型的 AI 端点由 `async def` 修改为 `def`，利用 FastAPI 的内部线程池调度，避免阻塞 ASGI 事件循环。
- **JSON 控制字符容错**: 在所有大模型回传结果的 `json.loads` 解析中添加 `strict=False`，修复批量处理中产生的 `Invalid control character` 错误，增强非标准 JSON 的解析鲁棒性。

## [v0.8.1] - 2026-01-21

### 🐛 Bug 修复 (Bug Fixes)
- **遗漏端点恢复**: 恢复了从 `server.py` 拆分时遗漏的 `/api/identify_metadata` 端点，修复了“识别信息”按钮无效的问题。
- **路径解析修复**: 统一了入库管理和在库管理的图书选取路径逻辑，解决了在库管理模式下识别信息显示“文件不存在”的错误。
- **元数据获取优化**: 修正了 `/api/metadata` 接口在在库模式下的路径解析，使其能够正确读取子目录中的图书元数据。
- **前端状态同步**: 修正了 `api.js` 和 `settings.js` 中对当前书籍路径的引用，确保所有 AI 操作均指向正确的物理文件。

## [v0.8.0] - 2026-01-21

### 🏗️ 架构重构 (Architecture Refactoring)
- **服务端拆分**: 将单体 `server.py` 拆分为模块化的 `src/book_organizer/routers/` 目录，包含 `config`, `library`, `analysis`, `integrations`, `sync` 等独立路由模块。
- **入口精简**: `server.py` 从 ~3800 行精简至 ~200 行，仅负责生命周期管理和路由挂载。
- **依赖解耦**: 优化了模块间的循环引用，明确了核心逻辑 (`framework`) 与接口层 (`routers`) 的边界。

### 🛡️ 规范与稳定性 (Standards & Stability)
- **全项目技能化**: 引入 `.agent/skills/refactoring-standards` 技能，确立架构重构、代码稳定性和可观测性的标准。
- **代码稳定性声明**: 对关键路径代码（如 `file_ops.py`）添加 `✅ 稳定方法` 标记，防止意外回归。
- **日志标准化**: 全面采用 `loguru` 替换原生 `logging`/`print`，统一日志格式与轮转策略。

### 🔧 构建系统更新
- **Mac 构建**: 更新 `BookOrganizer.spec`，自动识别并包含新增的 `routers` 子模块。
- **Windows 构建**: 更新 `build_windows.bat`，同步添加 hidden-imports 确保打包完整性。

### 🐛 Bug 修复
- **同步端点恢复**: 修复了重构过程中遗漏的 `/api/config/sync/validate` 和 `/api/config/sync` 端点。
- **样式修复**: 修复 `style.css` 中存在的 CSS 语法错误。

## [v0.7.7] - 2026-01-21

### ✨ 核心功能增强

#### 离线模式与智能自动兜底 (Offline & AI Fallback)
- **精准定义的离线模式**: 
  - 明确了"离线模式" = **不调用 AI**，但保留有用的联网功能 (ISBN 查询、在线搜索)。
  - 在离线模式下，"识别信息"和"推荐目录"功能将立即响应，利用本地算法而非等待 AI 超时。
- **AI 故障自动接管**: 
  - 当选定的 AI 模型 (Gemini/DeepSeek) 因网络、额度或配置问题调用失败时，系统**不再报错中断**。
  - **自动降级**: 系统会无缝切换到本地离线逻辑，尝试通过文件名解析、元数据提取和启发式规则完成任务。
  - **用户感知**: 界面会显示温和的黄色警告，提示由于 AI 故障已自动显示本地结果，确保流程顺畅。

#### 自动学习推荐引起 (Automated Learning Engine) 🧠
- **即时进化**: 每当您成功归档一本书，系统会立即分析其文件名关键词与目标目录的关系，并更新推荐规则。
- **无限制学习**: 
  - 移除了每个目录的学习关键词数量上限（原为 10/50 条）。
  - 引入了 **180 天滚动窗口** 的"自然老化"机制，长期不用的规则会自动淡出，保持推荐系统的高效与准确。
- **相似图书关联**: 离线推荐引擎新增了基于 `difflib` 的模糊匹配能力，能主动搜索库中已有的相似图书（如系列书），并直接推荐其所在目录。

#### 批量处理离线化 (Batch Offline Support) ⚡
- **完整闭环**: 实现了“批量入库”和“批量增强”功能的离线闭环，支持无 AI 时的本地分类与目录推荐。
- **极致性能优化**: 在离线模式下智能跳过昂贵的文本提取操作，大幅加速大规模批量处理任务。

#### ISBN 智能查询增强
- **离线可用**: 明确 ISBN 查询功能不受"离线模式"开关影响，始终尝试通过 OpenLibrary/Google Books 获取准确元数据。

### 🐛 Bug 修复
- **解析稳定性增强**: 修复了 AI 引擎内部依赖解包 (Unpacking) 失配的潜在 Bug，提升了复杂调用链下的系统稳定性。
- **识别信息 500 错误**: 修复了 AI 引擎配置缺失时导致的服务器内部错误，增加了健壮的错误捕获。
- **增强简介覆盖问题**: 修复了在离线模式或 AI 失败时，空结果可能覆盖已有增强简介的问题。
- **目录建议为空**: 修复了相似图书搜索时未剥离文件后缀导致的匹配失败问题。
- **批量处理兜底**: 修复了批量入库/增强功能在 AI 失败时直接报错的问题，改为自动降级到离线逻辑。
- **增强简介覆盖保护**: 在离线模式或 AI 故障时，优先显示数据库中已存在的增强简介；同时优化前端交互，生成的 Loading 状态和错误提示不再覆盖已有内容。

### 🔧 代码质量
- **日志系统升级 (Loguru)**: 
  - 引入 `loguru` 替代原生 `print`，实现结构化分级日志。
  - 日志自动输出至 `logs/book_organizer.log`，支持 10MB/10天 自动轮转。
- **基础架构标准化**: 新增 `pyproject.toml` 和 `.pre-commit-config.yaml`，锁定 Ruff 配置与格式化规范。
- **代码稳定性**: 为核心文件操作 (`file_ops.py`) 和离线工具 (`local_utils.py`) 添加 ✅ 稳定性声明。
- **Ruff 清洗**: 修复了所有 bare `except` 语句，添加了缺失的 `json` 导入，规范化了代码格式。

### 📝 文档更新
- **README.md**: 更新架构图，反映"混合智能架构" (Hybrid Intelligence Architecture)。
- **User Rules**: 更新了关于代码稳定性声明的规范。

---


### 🔧 本地处理能力增强 (Local Processing)
- **ISBN/ISSN 智能提取**: 
  - 支持从通过 PDF/EPUB 文件元数据或文本前几页自动提取 ISBN。
  - 集成 Open Library 和 Google Books API 进行元数据补全。
  - 支持调用本地 Calibre (`fetch-ebook-metadata`) 命令行工具进行深度查询（需安装 Calibre）。
- **本地查重与分类**:
  - 新增基于文件名的本地查重算法，快速识别重复书籍。
  - 新增基于启发式规则的本地自动分类建议（无需 AI）。

### ✨ 离线模式与智能兜底 (Offline & Fallback)
- **离线模式集成**: "开始信息及目录分析" 按钮现已完美支持离线模式。
  - 选择 "离线模式" 时，系统会自动跳过 AI 调用，仅通过本机元数据和启发式规则进行快速整理。
- **智能自动兜底**: 当 AI 服务（如 Gemini/DeepSeek）暂时不可用（网络错误/额度耗尽）时，系统会自动降级到 "离线模式" 逻辑，确保分析任务顺利完成。
- **降级提示**: 当触发自动兜底时，界面会弹出橙色警告，告知用户当前结果为本地分析版本。

### 🐛 Bug 修复
- **数据保护**: 修复了在离线模式或 AI 降级时可能意外覆盖已有增强简介的问题。
- **目录功能**: 修复了离线模式下目录提取 (TOC) 失效的问题 (现已强制使用本地提取)。
- **稳定性**: 修复了离线模式调用增强简介接口时的 500 错误。

### 🧹 代码清理
- **imports 优化**: 修复了 `server.py` 等多处模块导入顺序问题 (E402)。
- **逻辑去重**: 移除了 `isbn_lookup.py` 中重复的函数定义。
- **代码规范**: 修复了多处不规范的异常捕获和单行语句问题。

### ⚡️ 离线能力 (Offline Capability)
- **字体本地化**: 移除 Google Fonts 依赖，全面切换至系统原生字体栈 (`-apple-system`, `Segoe UI` 等)，提升加载速度并支持离线使用
- **图标本地化**: 内置 Font Awesome 图标库，移除 CDN 依赖 (SoftwareOrganizer, BookOrganizer)
- **隐私增强**: 消除对 `fonts.googleapis.com` 和 `cdnjs.cloudflare.com` 的追踪请求

### 🧹 代码清理
- 集成全局 Skills 规范
- 移除 `server.py` 中残留的无效代码
- 清理未使用变量 (`ai_config`, `duplicate_groups`)
- 规范化代码格式 (Ruff)
- **更新 .gitignore** (2026-01-16): 新增 `book_organizer.db` 和 `.agent/` 目录排除

### 📝 文档更新
- 关联全局 Skills 文档 (`~/.gemini/skills/`)
- 优化开发流程文档引用

## [v0.7.6] - 2026-01-10

### 🐛 Bug 修复

#### 同步弹窗配置时间戳修复 ☁️
- **问题**: 同步设置中"本地"配置的修改时间显示不正确（可能为 0 或过期数据）
- **根因**: 后端检查的是不存在的 `preferences.json`，而实际本地配置文件为 `book_organizer_config.json`
- **修复**: 更新 `validate_sync_config` 函数，正确检查本地配置文件

#### AI 配置标签页选择修复 🤖
- **问题**: 打开 AI 配置弹窗时，默认标签页（核心规则）可能无法正确激活
- **根因**: `switchAITab` 函数使用脆弱的 `textContent.includes()` 匹配方式
- **修复**: 
  - 为所有标签按钮添加 `data-tab` 属性
  - 重构 `switchAITab` 使用 `dataset.tab` 精确选择
  - 修复 `saveAIConfig` 中 `API_BASE` 的安全访问

### 🧹 代码质量

#### 代码注释本地化 📝
- **范围**: `ai_config.js`、`state.js`、`api.js`
- **内容**: 将约 60 处英文注释翻译为中文，提升代码可读性和维护一致性
- **验证**: 确认 `sync.js`、`ui.js`、`zoom.js`、`app.js`、`server.py` 已为中文注释

### 📝 修改文件清单
- `src/server.py` - 同步验证逻辑修复
- `static/index.html` - AI 配置标签添加 data-tab 属性
- `static/ai_config.js` - 标签切换逻辑重构 + 注释本地化
- `static/js/modules/state.js` - 注释本地化
- `static/js/modules/api.js` - 注释本地化

---



### ✨ UX 改进

#### 启动同步检测弹窗 🚀
- **新增功能**: 启动时自动检测云端与本地数据库差异，弹窗提醒用户选择同步方向
- **自动检测开关**: 新增"自动检测差异"复选框，点击后**立刻保存**设置，无需再点"应用设置"
- **上次同步信息**: 弹窗中显示上次同步的设备和时间，帮助用户做出决策

#### 同步弹窗样式统一 🎨
- **视觉一致性**: 启动检测弹窗与云端冲突弹窗样式完全统一
  - 标题居中、图标居中
  - 弹窗宽度统一为 550px
  - 云端/本地数据左右对比布局
- **紧凑布局**: 优化垂直间距，减少不必要的留白
  - 底部 padding 减少到 10px
  - 按钮间距优化

### 🔧 技术改进

#### CSS 隔离性
- 所有同步弹窗样式使用 **ID 选择器** (`#sync-conflict-modal`, `#sync-lifecycle-modal`)
- 确保修改不影响其他通用弹窗

### 📝 修改文件清单
- `static/style.css` - 同步弹窗样式优化（宽度、padding、margin）
- `static/js/modules/settings/cloud-sync.js` - 自动检测开关即时保存
- `static/js/modules/sync.js` - 启动检测弹窗添加上次同步信息

---

## [v0.7.4] - 2026-01-06

### ✨ UX 改进

#### 增强模式交互优化 🪄
- **全局总开关**: 在 AI 配置的"增强规则"标签页新增了标准的 **增强模式总开关**，与顶部导航栏的增强图标完全联动。
- **状态同步**: 
  - 顶部导航栏图标状态与配置页开关实时双向同步
  - "增强规则"标签页的状态指示灯颜色从绿色修正为与其他 UI 一致的 **蓝色** (`var(--primary-color)`)
- **App.js 重构**: 封装了全局的 `setEnhancedMode` 方法，确保多入口控制的一致性。

#### 导航栏布局调整 📐
- **按钮顺序优化**: 交换了 **云同步** 和 **设置** 按钮的位置，将常用的云同步按钮前置，符合操作习惯。
  - 新顺序: 云同步 <-> 刷新 <-> 设置 <-> 帮助

### 📝 修改文件清单
- `static/index.html` - AI配置页开关、Header按钮顺序
- `static/app.js` - `setEnhancedMode` 逻辑封装
- `static/style.css` - 状态灯颜色修正、Header 间距优化
- `src/book_organizer/sync_manager.py` - 查重忽略记录改用相对路径

### 🔧 技术改进

#### 查重忽略记录跨设备同步 🔄
- **问题**: 忽略记录使用绝对路径存储，导致跨设备同步后无法正确匹配（不同设备的 `target_dir` 不同）。
- **修复**: 
  - 改用相对路径（相对于 `target_dir`）存储忽略规则。
  - 添加自动迁移逻辑：首次加载时检测并转换旧的绝对路径为相对路径。
- **效果**: 只要两台设备的图书目录结构相同，忽略记录可正确同步和匹配。

---

## [v0.7.3] - 2026-01-05

### 🔧 代码重构与优化

#### JavaScript 模块拆分 📦
- **settings.js** (1714行 → 5个模块):
  - `settings/model-config.js` (288行) - 标签切换、内置模型管理
  - `settings/custom-provider.js` (282行) - 自定义 Provider CRUD
  - `settings/google-drive.js` (394行) - Google Drive 集成
  - `settings/cloud-sync.js` (268行) - iCloud 同步设置
  - `settings.js` (476行) - 主入口、通用设置
- **libraryBatch.js** (1204行 → 5个模块):
  - `libraryBatch/selection.js` (278行) - 多选功能
  - `libraryBatch/hover-popup.js` (272行) - Hover 浮动弹窗
  - `libraryBatch/modal.js` (351行) - 批量处理弹窗
  - `libraryBatch/process.js` (345行) - 批量增强/转换逻辑
  - `libraryBatch.js` (57行) - 主入口

#### Python 脚本重构 🐍
- **migrate_database.py**:
  - 添加完整类型注解 (Type Hints)
  - 使用参数化 SQL 替代 f-string 拼接
  - 使用 Path 对象替代字符串拼接
  - 拆分为 7 个小函数
- **migrate_transfer_logs.py**:
  - 使用 dataclass 替代字典
  - 添加完整类型注解
  - 消除全局变量
  - 预编译正则表达式
  - 拆分为 8 个小函数

#### Windows 构建脚本对齐 🪟
- **build_windows.bat** 对齐 Mac 版功能:
  - 新增 18 个 hidden-import (fitz, pikepdf, litellm, tiktoken, ollama, openai, book_organizer.* 等)
  - 新增 11 个 exclude-module 优化体积
  - 新增 2 个 add-data 配置
  - 添加 Google API 清理逻辑

#### 前端样式重构 🎨
- **Header 样式优化**: 移除了 Header 按钮样式中的 `!important` 强制声明，改用 CSS 特异性 (Specificity) 控制，提升样式可维护性。
- **JS 内联样式提取**: 
  - **ui.js**: 移除了 11 处内联样式 (空状态、相似提示等)，提取为 `.empty-list-message`, `.similar-files-container` 等 CSS 类。
  - **sync.js**: 移除了大量内联样式，提取为 `.sync-conflict-modal` 等组件样式。

### 🐛 Bug 修复

#### 1. 数据库备份策略调整 (Rolling Backup)
- **优化**: 废弃了生成带时间戳的多个备份文件 (`.bak_YYYYMMDD...`) 的策略。
- **新策略**: 采用固定文件名的轮替备份 (`book_data.db.bak`)，每次备份时覆盖旧文件。
- **效果**: 彻底解决了 `.bak` 文件无限增殖导致占用磁盘空间的问题，同时始终保留最近一份安全副本。

#### 2. 同步状态检测修复 (WAL Checkpoint)
- **问题**: 在 SQLite WAL 模式下，主数据库文件 (`.db`) 的修改时间和大小未包含 `.wal` 临时文件中的最新变更，导致同步检测误判"无更新"。
- **修复**: 在执行同步冲突检测前，强制执行 `PRAGMA wal_checkpoint(TRUNCATE)`，将所有数据刷入主文件。
- **效果**: 确保了文件系统元数据与数据库内容完全一致，消除了导致虚假冲突弹窗的根源。

#### 3. 界面显示修复
- **同步时间显示**: 修复了同步冲突弹窗中"上次同步"时间显示为 `(Invalid Date)` 的问题（修正了前后端字段名不一致 `time` vs `timestamp`）。

### 📝 文档更新
- **PROJECT_STRUCTURE.md**: 更新 JS 模块列表，添加子模块目录

---



## [v0.7.2] - 2026-01-04

### 🧹 代码质量审查与修复

#### 修复 (Fixes)
- **图书查重目录映射修复**: 修正了查重功能错误扫描 `source_dir` (下载目录) 而非 `target_dir` (书库目录) 的问题，现在能正确查找库内重复图书。
- **忽略列表云同步**: `dedup_ignores.json` 现在支持双向自动同步。
  - 读取时：自动检查云端是否有更新版本并拉取。
  - 保存时：自动推送到云端备份。

#### 优化 (Optimizations)
- **图书馆查重性能优化**:
  - 移除了"忽略/取消忽略"操作后的全库重扫逻辑。
  - 实现了前端"乐观更新" (Optimistic UI)，操作响应从 ~3s 提升至 0ms (即时响应)。
  - 保持了数据的一致性，后台静默同步，前台即时反馈。

#### 文档 (Documentation)
- **代码注释汉化**: 全面汉化了核心模块 (`sync_manager.py`, `api.js`, `sync.js`) 的代码注释，提升代码可读性与维护性。

#### 代码审查 (Code Audit)
- **全面审查**: 对后端 Python (5个核心文件) 和前端 JavaScript (4个模块) 进行了代码逻辑、错误和功能审查
- **审查报告**: 生成详细问题清单，按严重程度分类

#### 已修复问题 (6项)

| 类别 | 问题 | 修复方式 |
|------|------|----------|
| 重复代码 | 作者/文件名格式化逻辑重复 | 提取为 `_normalize_author()` / `_normalize_filename()` 函数 |
| Copy-Paste | server.py 连续调用两次 `load_config()` | 删除重复行 |
| 异常处理 | config.py 裸 `except: pass` 吞掉异常 | 添加 `except Exception as e` + 警告日志 |
| 竞态条件 | batch.js 顺序处理未 await | 添加 `await analyzeBook()` |
| 废弃代码 | server.py 遗留无用注释 | 删除 core_content 注释 |
| UX 体验 | 搜索防抖 3 秒过长 | 缩短为 500ms |

#### 待处理问题 (已登记)

| 优先级 | 问题 | 备注 |
|--------|------|------|
| P2 | 大文件拆分 (server, ui, settings, etc.) | 需 6-8 小时重构 |
| P3 | AbortController / HTML onclick / CSS !important | 延期处理 |

---

## [v0.7.1] - 2026-01-03

### ✨ UX 改进

#### 同步冲突解决 (Sync Conflict Resolution)
- **全新确认弹窗**: 将原有的 `confirm` 简单对话框替换为自定义的 **3 按钮模态框**
- **明确的操作选项**: 为了消除歧义，现在提供三个明确选择：
  1. **下载云端版本**: 覆盖本地数据
  2. **上传本地版本**: 覆盖云端数据
  3. **取消操作**: 不做任何更改
- **详细对比信息**: 弹窗内直观展示云端与本地的数据库大小、修改时间和上次同步记录

---

## [v0.7.0] - 2026-01-03

### 🎨 UI 标准化与重构

#### 功能卡片样式统一 (Unified Feature Cards)
- **卡片组件**: 引入全新 `.ui-feature-card` CSS 组件，统一所有功能开关的视觉风格
- **应用范围**: 
  - **历史数据参考**: 将原有的复选框改造为大卡片，包含图标和说明
  - **内容与搜索控制**: 同样升级为标准卡片样式
  - **测试功能 (Beta)**: 所有 Beta 功能开关（重复搜索、元数据写入等）全部迁移至新卡片风格
- **视觉一致性**: 所有卡片均采用渐变背景、圆角边框和悬停阴影，与 iCloud 同步卡片保持高度一致
- **交互反馈**: 激活状态下图标增加脉冲呼吸动画，状态更直观

### 🛡️ 核心功能增强

#### 数据库同步验证 (Sync Verification)
- **逻辑审查**: 全面审查了 `server.py` 和 `sync.js` 的同步逻辑，确保在数据覆盖前进行完整的安全检查
- **接口稳定性**: 确认 `/api/config/sync/validate` 和 `/api/config/sync` 接口能正确处理各种边界情况（如空数据库、配置缺失等）

### 📝 文档更新
- **PROJECT_STRUCTURE.md**: 更新项目结构图，反映最新的模块组织
- **README.md**: 完善功能特性描述，更新截图预览（需重新生成）

---

## [v0.6.11] - 2026-01-03

### 🛡️ 数据库同步安全修复

#### 用户选择确认
- **同步方向选择**: 开启同步时，如果云端和本地都有数据库，会弹出对话框让用户选择：
  - "确定" → 下载云端数据（推荐用于新设备）
  - "取消" → 上传本地数据到云端
- **新增验证 API**: `/api/config/sync/validate` 返回云端/本地数据库大小对比

#### 关键安全检查
- **大小比较保护**: 如果云端数据库大小小于本地的 10%（且本地 > 1MB），会自动上传本地数据而不是下载云端空数据
- **反向保护**: 如果本地数据库远小于云端，会自动下载云端数据并备份本地
- **Ollama 配置同步**: 新增 Ollama URL 和模型设置同步

---

## [v0.6.10] - 2026-01-03

### 🔄 自动数据库同步

#### 启动时自动同步
- **触发时机**: 程序启动时，如果 iCloud 同步已启用
- **同步逻辑**: 
  - 先执行 WAL Checkpoint，合并增量数据到主数据库
  - 比较本地和云端的 mtime，决定上传或下载
  - 下载云端数据前，自动创建本地备份 (`book_data.db.bak_sync`)
- **注意**: 程序关闭时不触发同步，避免延迟关闭

---

## [v0.6.9] - 2026-01-03

### ☁️ iCloud 同步增强 (完整版)

#### 新增同步项
- **`user_preferences`**: 用户界面偏好（Enhanced Mode、Model Selection、Web Search、TOC 开关）
- **`ai_config.json`**: AI 配置（核心规则、附加规则、字段提取规则）
- **`gemini` / `deepseek` / `volcengine`**: AI 引擎 API Keys 和模型设置
- **`custom_providers`**: 自定义 AI Provider 配置
- **`google_drive_token.json`**: Google Drive OAuth Token（新设备自动获取）
- **`client_secrets.json`**: Google OAuth 应用凭证

#### 不同步（机器特定）
- `source_dir`, `target_dir`, `transfer_log_dir` (路径配置)
- `app.log`, `book_data.db.bak*` (日志和备份文件)

#### 清理
- 删除了废弃的 `book_organizer_ai_config.json` 文件

---

## [v0.6.8] - 2026-01-03

### 🛡️ 安全与稳定性改进

#### 1. 同步逻辑优化 (Sync Manager)
- **改进**: 当多个同名文件存在于不同目录时，同步逻辑现在优先匹配相同目录或具有相同父目录名称的文件，而非随机选择第一个匹配项。
- **效果**: 减少同名文件导致的数据库记录错误关联。

#### 2. AI 错误信息增强 (AI Engines)
- **改进**: AI 调用失败时，错误信息现在会包含具体类型（限流、认证、超时、网络），而非笼统的 "AI 调用失败"。
- **效果**: 便于用户快速定位问题根源。

#### 3. 路径解析统一 (Server)
- **改进**: `rename_only` API 端点现使用统一的 `resolve_file_path` 函数，移除了冗余的手动路径检查逻辑。
- **效果**: 代码更简洁，路径解析行为与其他 API 保持一致。

---

## [v0.6.7] - 2026-01-03

### 🚑 紧急修复 (Hotfix)

#### 数据库安全备份机制修复
- **问题**: 原备份机制使用 `shutil.copy2` 直接复制正在运行的 WAL 模式数据库，导致备份文件出现 "database disk image is malformed" 损坏
- **修复**: 
  - 弃用文件直接复制方式
  - 改用 SQLite 原生 Online Backup API (`sqlite3.backup`)
  - 确保在应用运行时能生成事务一致、完整有效的备份文件
- **恢复**: 成功从历史有效备份中恢复了受损的数据库，并清理了无效的零字节备份文件

---

## [v0.6.6] - 2026-01-03

### 🧱 核心修复：数据同步与完整性

#### 1. 智能双向同步 (True Bidirectional Sync)
- **问题**: 原逻辑在云端存在文件时，默认执行“云端覆盖本地”，导致本地最新改动丢失。
- **修复**: 引入严格的时间戳 (Mtime) 比较机制。现在系统会精确判断：若本地文件较新则自动上传，若云端较新则自动下载。

#### 2. 数据完整性保障 (WAL Checkpoint)
- **问题**: 同步时直接复制 `.db` 文件，未合并 WAL 里的最新数据，导致同步的数据不完整。
- **修复**: 每次同步前强制执行 `PRAGMA wal_checkpoint(FULL)`，确保所有内存/日志中的新数据都被刷入主数据库文件。

#### 3. 本地安全备份 (Auto Backup)
- **功能**: 在执行“云端覆盖本地”的操作前，系统会自动将当前的本地数据库备份为 `book_data.db.bak_sync`。
- **策略**: 采用“单文件轮替”策略，始终保留最近一次被覆盖的版本，既安全又不占用额外磁盘空间。

#### 4. 数据库分析修复
- **修复**: 移除了 `sync_manager` 中导致数据库分析卡死的硬编码路径，现已完全适配用户配置的源目录。

### 🚑 紧急恢复
- 成功修复了损坏的 SQLite 数据库文件，并清洗了受损的 UTF-8/JSON 记录。

---

## [v0.6.5] - 2026-01-03

### 🐛 Bug 修复

#### 同步机制逻辑重构 🔄
- **问题**: 原同步逻辑在“本地无数据库”时会误判为新机器，或在“本地有数据库”时强制上传覆盖云端配置，导致用户在新设备配置 AI 后被云端空配置覆盖
- **修复**: 
  - 彻底废弃“新/旧机器”判定逻辑，统一采用**双向智能同步**策略
  - 对 `ai_config.json`, `preferences.json`, `client_secrets.json` 等所有配置文件引入 **mtime（修改时间）仲裁**
  - **谁新听谁的**: 自动比较云端和本地文件的修改时间，始终保留最新版本
- **UX 优化**: 同步成功后增加页面自动刷新机制，确保新拉取的配置立即生效

---

## [v0.6.4] - 2026-01-03

### ✨ 新功能

#### iCloud 同步增强 ☁️
- **一键同步按钮**: 顶部导航栏新增云同步按钮（帮助按钮左侧），支持一键手动触发数据库与配置同步
- **智能路径支持**: 设置页 iCloud 路径提示现在可点击一键填入，且后端支持 `~` 路径自动展开，无需手动输入完整用户路径
- **交互优化**: 同步过程中按钮图标增加旋转动画反馈，完成后显示成功提示

### 📚 文档
- **帮助文档**: 更新应用内帮助弹窗，新增由于云同步和数据库查重功能的详细说明

---

## [v0.6.3] - 2026-01-02

### 🐛 Bug 修复

#### 批量增强路径 404 修复
- **问题**: 在批量增强操作后，若文件名未发生变更，点击查看详情或悬停预览会报 404 错误
- **根因**: 后端 `rename_only` 接口在无重命名时仅返回文件名（basename），导致前端路径更新错误
- **修复**: 统一后端返回逻辑，无论是否重命名均返回完整的相对路径

#### AI 状态灯显示修复
- **问题**: AI 配置弹窗中 "内容与搜索控制" 的状态指示灯与顶部快捷栏不一致，总是显示为开启
- **修复**: 修正前端判断逻辑，检查具体的 `enabled` 属性而非仅检查对象是否存在

#### 数据源切换刷新
- **优化**: 点击顶部 "数据库增强" 快捷开关时，立即重新加载当前选中书籍的简介和目录，无需手动刷新页面

### ⚡️ 性能优化
- **批量预览秒开**: 优化批量增强列表的悬停预览机制，优先读取数据库缓存并跳过耗时的文件元数据提取，实现毫秒级响应

### 📚 文档
- **帮助文档**: 新增 "顶部快捷工具" 章节，说明常用快捷按钮的功能

---

## [v0.6.2] - 2026-01-02

### 🎨 界面优化

#### 顶部快捷开关按钮
- **新增内容与搜索开关**: 放大镜图标，一键切换 AI 配置中的"内容与搜索控制"总开关
- **新增数据库增强开关**: 数据库图标，一键切换数据源优先级（数据库/元数据）
- **状态联动**: 快捷开关与设置页面/AI配置弹窗中的对应选项实时同步

#### 动态标签显示
- **在库管理模式**: 标签根据数据源开关显示"增强简介（数据库）"或"增强简介（内置）"
- **入库管理模式**: 标签始终显示"增强简介（内置）"和"图书目录（内置）"
- **数据加载联动**: 切换数据源时，自动从对应来源（数据库/文件内置）加载简介和目录

#### 抬头按钮区紧凑化
- **高度压缩**: 按钮高度从 `36px` 缩小至 `32px`，字体调整为 `0.9rem`
- **间距紧凑**: 按钮间距从 `12px` 减少至 `6px`，大幅提升横向空间利用率
- **样式隔离**: 仅针对 Header 区域生效，不影响全局其他按钮样式

### 🐛 Bug 修复

#### 批量处理联网开关同步修复
- **问题**: 批量处理模块无法正确读取全局“联网搜索”开关状态（始终显示为关）
- **修复**: 在 `state.js` 和 `app.js` 中将 `isWebSearchEnabled` 状态实时同步到全局 `window` 对象，确保跨模块访问一致性
- **效果**: 批量处理日志现可正确显示当前联网开关状态

#### 数据库查询逻辑增强与加固
- **问题**: 批量增强后，悬停简介/目录图标时偶尔无法加载已保存的数据
- **修复**: 增强 `database.py` 中的 `get_summary` 和 `get_toc` 查询逻辑，添加3层 fallback 策略
  1. 精确 basename 匹配（默认，最快）
  2. 精确完整路径匹配（兼容旧数据）
  3. 模糊路径匹配（处理路径分隔符差异）
- **加固**: 同样为 `get_book_rating` 添加了 3 层匹配策略，并确保 `get_all_summaries` 按更新时间降序排序，确保状态同步最准确
- **效果**: 即使文件名修改、路径格式不一致或存在重复记录，系统也能始终获取到最准确的书籍状态和记录

#### 批量增强图标实时更新彻底修复
- **问题**: 批量信息增强执行完成后，简介和目录图标依然显示为灰色（未激活状态）
- **根因**: `updateRowStatus` 函数在检查 `has_enhanced_summary` 和 `has_toc` 状态时，队列中的状态尚未更新（竞态条件）
- **修复**: 
  1. 重构 `updateRowStatus` 函数，新增 `itemState` 参数直接传递状态，避免依赖队列中的延迟更新
  2. 增强完成后自动清除 `hoverPopupCache` 缓存，确保 hover 时获取最新数据
  3. 添加调试日志便于追踪问题
  4. 改进图标更新逻辑，总是处理有/无数据两种情况

#### 全场景目录自动保存
- **问题**: 只有在库批量增强会保存目录，其他场景（入库转移、保存修改、入库批量）都不保存文件内置目录
- **修复**: 在所有保存/转移操作中自动提取并保存 EPUB/PDF 内置目录
  - `/api/rename_only` (保存修改) - 添加目录提取逻辑
  - `rename_and_move_book()` (入库转移) - 添加目录提取逻辑  
  - `/api/batch_enhance_single` (在库批量) - 已修复
  - `/api/batch_organize_single` (入库批量) - 添加目录状态返回
- **效果**: 无论通过哪种方式保存/转移图书，只要文件有内置目录就会自动保存到数据库

#### Hover 简介加载卡住修复
- **问题**: 批量增强后 hover 简介图标时一直显示"分析加载中..."
- **根因**: 前端使用错误的字段名 `details.enhanced_summary`，而 API 实际返回的字段是 `details.summary`
- **修复**: 统一使用 `details.summary` 字段名

### 🔧 构建优化

#### macOS 打包体积优化
- **Calibre 导入修复**: 修复 `book_organizer.calibre` 导入错误（实际模块为 `pdf_converter`），确保 PDF 转换功能正常
- **Google API 清理增强**: 
  - 改进清理逻辑，自动检测打包结构（.app bundle 或 onedir）
  - 显示清理效果统计（节省空间大小）
  - 仅保留 `drive.v3.json`，清理其他 567 个 API 定义文件
  - 体积优化：从 ~180M 减少至 ~90M（节省约 91M）
- **PIL 模块精简**: 排除不需要的图像处理子模块
  - `PIL.ImageQt` - Qt 框架集成（不使用）
  - `PIL.ImageTk` - Tkinter 集成（不使用）
  - `PIL.FpxImagePlugin` - FlashPix 老格式（已废弃）
  - 保留 `PIL.WmfImagePlugin` 以确保 Windows 平台兼容性

### 📝 修改文件清单
- `static/style.css` - Header 按钮样式覆盖
- `static/js/modules/state.js` - 全局变量同步
- `static/js/modules/app.js` - 开关状态同步逻辑
- `static/js/modules/libraryBatch.js` - 批量增强图标更新逻辑重构、hover 简介字段名修复
- `src/server.py` - rename_only/batch_organize_single API 添加目录自动提取
- `src/book_organizer/transfer.py` - rename_and_move_book 添加目录自动提取
- `scripts/build_standalone.sh` - 构建脚本优化和版本更新 (v0.6.2)
- `src/book_organizer/database.py` - 数据库查询逻辑增强（3层 fallback）

---

## [v0.6.1] - 2026-01-02

### ✨ 新功能

#### 内容与搜索控制整体开关 🎛️
- **全局开关**: 在 AI 配置的"内容与搜索控制"标签页顶部新增"启用自定义配置"开关
- **完全跳过模式**: 开关关闭时，完全跳过内容提取和联网搜索，AI 分析仅依赖文件名和文件内嵌元数据
- **状态指示灯同步**: 开关状态实时反映在顶部 AI 配置按钮的状态指示灯上

### 🔧 技术改进

#### 后端架构优化
- **新增辅助函数**: `get_content_search_config()` 统一处理配置读取和 `enabled` 开关逻辑
- **跳过标志**: 当 `enabled=False` 时返回 `skip=True` 标志，调用方据此跳过相关功能
- **影响范围**: 涉及 `extract_core_content()`、`search_book_online()` 及所有使用内容提取参数的 AI 分析函数

### 📝 修改文件清单
- `src/book_organizer/config.py` - 添加 `enabled` 默认值 + `get_content_search_config()` 辅助函数
- `src/book_organizer/ai_engines.py` - 7 处调用改用新辅助函数，添加跳过检测
- `src/book_organizer/search.py` - 添加跳过检测
- `src/server.py` - 4 处调用改用新辅助函数
- `static/index.html` - 添加开关 UI
- `static/ai_config.js` - 开关状态读取/保存/重置 + 状态指示灯联动

---

## [v0.6.0] - 2026-01-01

### ✨ 新功能

#### 图书馆查重功能 🔍
- **智能重复检测**: 自动扫描图书库中的相似图书，基于模糊匹配算法识别疑似重复组
- **查重弹窗**: 在顶部"同步"下拉菜单中新增"图书馆查重"入口
  - 显示所有疑似重复图书分组
  - 每个分组展示格式标签（EPUB/PDF）、文件大小、完整路径
  - 显示增强简介和目录状态图标，帮助判断保留版本
- **忽略/取消忽略**: 
  - 对于故意保留的"重复"（如不同格式版本），可点击"忽略"将该组从查重列表移除
  - 忽略记录基于文件路径集合签名，文件增删后自动重新检测
  - 可在"忽略记录"标签页查看并取消忽略
- **安全删除**: 删除操作需确认，删除后自动从分组中移除；若剩余少于 2 本，整个分组自动消失

#### 数据库同步功能 🗄️
- **两项同步入口**: 顶部"同步"按钮改为下拉菜单，包含"数据库同步"和"图书馆查重"
- **同步按钮精简**: 移除文字标签，仅保留图标和下拉箭头，界面更简洁

### ⚡ 性能优化

#### 批量处理 Token 优化 🎯
- **入库批量分析**: 合并元数据+目录建议+增强简介为单次 AI 调用，节省约 20-30% Token
  - 新增 `/api/batch_organize_single` 端点
  - 新增 `get_batch_organize_analysis()` 后端函数
  - 支持联网搜索、增强简介开关
- **在库批量增强**: 合并元数据+增强简介为单次 AI 调用，节省约 30-40% Token
  - 新增 `/api/batch_enhance_single` 端点
  - 新增 `get_batch_enhance_analysis()` 后端函数
  - 开关关闭时跳过 AI 调用，不消耗 Token

#### 开关联动完善 🔧
- **入库批量**: 正确读取联网搜索、增强简介开关状态
- **在库批量**: 正确读取增强简介开关状态
- **文本提取字数**: 根据联网开关自动调整 (`search_mode_chars` vs `standard_mode_chars`)

### 🎨 界面优化

#### 弹窗风格统一
- **统一尺寸**: 所有主要弹窗（设置、AI 配置、记录、批量处理、同步、查重等）统一为 `max-width: 900px`
- **标题栏**: 统一 `padding: 16px 20px`，字号 `1.15rem`，图标颜色一致
- **关闭按钮**: 统一 `32×32px` 方形按钮，带悬停效果
- **内容区域**: 统一 `padding: 16px 20px`
- **底部按钮区**: 统一 `padding: 12px 20px`，按钮样式标准化

#### 其他 UI 调整
- **搜索框优化**: 
  - 占位文字居中显示
  - 更新提示文本："搜索... (空格支持多条件, +数字代表星级筛选)"
- **查重弹窗 Pill 标签**: "查重记录"和"忽略记录"使用 Pill 胶囊风格，选中态为蓝底白字

### 🐛 Bug 修复

- **删除后分组自动清理**: 修复删除图书后若剩余 1 本，分组仍显示的问题（需在 remove 前保存容器 ID）
- **数据库路径错误**: 修复 `dedup_ignores.json` 保存路径错误（AttributeError: db_dir → 改用 db_path 推导）
- **批量列表目录显示**: 修复在库批量增强列表悬停目录图标显示"暂无数据"的问题
- **批量增强图标实时更新**: 修复批量增强完成后简介/目录图标状态同步问题
  - 增强完成后自动重新获取书籍详情，确保若文件名重命名修复了关联，目录图标也能立即点亮
  - **路径通过性修复**: 修复因文件重命名导致后续状态查询使用旧路径而失败的问题（现解析重命名响应并自动更新查询路径）
  - 修复了简介图标不会立即变为可点击状态的问题
  - `/api/library/book_details` 现返回 `toc` 和 `toc_text` 字段
  - 前端支持目录数组和 AI 整理文本两种格式

### 📝 修改文件清单

#### 批量处理优化
- `src/book_organizer/ai_engines.py` - 新增 `get_batch_organize_analysis()` 和 `get_batch_enhance_analysis()`
- `src/server.py` - 新增 `/api/batch_organize_single`、`/api/batch_enhance_single`，扩展 `/api/library/book_details`
- `static/js/modules/batch.js` - 使用合并 API，支持开关控制
- `static/js/modules/libraryBatch.js` - 检查增强简介开关，支持目录两种格式显示

#### 其他
- `src/book_organizer/sync_manager.py` - 新增查重分析、忽略/取消忽略逻辑
- `static/js/modules/sync.js` - 新增查重弹窗 UI、标签切换、删除逻辑
- `static/style.css` - 弹窗风格统一样式块
- `static/index.html` - 搜索框占位文字更新

---



### 🧹 代码清理

#### Phase 1 低风险清理
- **删除重复代码**: 
  - `server.py`: 移除重复的 `# Database` 注释和重复的 `import datetime`
  - `ai_engines.py`: 移除遗留调试注释（8行）
- **废弃函数标记**: 标记 `/api/test_connection` 为废弃，已被 `test_connection_v2` 替代
- **CSS 去重**: 
  - 合并重复的 `.warning-bg` 定义
  - 将 `#settings-btn` 硬编码颜色 `#6b7280` 改为 CSS 变量 `var(--text-muted)`
  - 移除重复的 `/* Buttons */` 注释

#### 项目文件整理
- **清理构建产物**: 删除 `build/`、`dist/`、`.mypy_cache/`、`.pytest_cache/`、`.ruff_cache/`
- **清理缓存**: 删除所有 `__pycache__/` 和 `.DS_Store` 文件
- **清理临时文件**: 删除 `releases/core_reference/` 提取目录
- **清理旧版本**: 删除旧版发布包，仅保留最新版 `BookOrganizer_Mac_2025-12-25.zip`

### 📉 代码行数变化
| 文件 | 修改前 | 修改后 | 变化 |
|:-----|:-------|:-------|:-----|
| `server.py` | 2387 | 2378 | -9 |
| `ai_engines.py` | 907 | 899 | -8 |
| `style.css` | 5368 | 5362 | -6 |

### 📝 修改文件清单
- `src/server.py` - 删除重复注释和导入
- `src/book_organizer/ai_engines.py` - 删除调试注释
- `static/style.css` - CSS 去重和变量化

### 🐛 Bug 修复

- **数据库锁定问题**: 彻底修复入库模式切换图书时的卡顿问题
  - 移除 OS 级文件锁（fcntl），改用 SQLite 内置锁机制
  - 启用 WAL (Write-Ahead Logging) 模式提高并发性能
  - 设置 multiprocessing 为 spawn 模式，避免子进程继承文件锁
  - 代码精简：删除约 100 行锁相关代码

---






### ✨ 新功能

#### 图书评分系统 ⭐
- **五星评分**: 在库管理模式下，为图书添加 1-5 星评分
- **清除评分**: 悬停评分区域出现清除按钮（禁止图标），点击重置为未评分状态
- **左侧图标同步**: 评分后左侧图书列表显示带数字的金色星标

#### 搜索评分筛选 🔍
- **语法**: 在搜索框输入 `+N` (N=0-5) 筛选指定星级
  - `+5` → 筛选 5 星图书
  - `+0` → 筛选未评分图书
  - `Python +5` → 组合关键词和评分筛选

#### 库管理批量操作 📦
- **批量增强**: 批量生成增强简介，支持选择文件夹或单独图书
- **批量转换**: 批量转换格式并上传云盘
- **进度追踪**: 实时进度条和状态显示
- **悬停预览**: 鼠标悬停快速查看图书简介和目录

### 🎨 样式标准化

#### CSS 变量统一
- **按钮样式**: `.btn-primary`, `.btn-secondary`, `.btn-success`, `.btn-danger` 改用 CSS 变量
  - `--btn-height-sm`, `--btn-padding-x-sm`, `--btn-font-size-sm`, `--btn-gap`
- **过渡动画**: 11+ 处硬编码 `0.2s`/`0.3s` 改为 `--transition-base`/`--transition-fast`/`--transition-slow`
- **移除 `!important`**: `.btn-sm` 不再使用 `!important`

### 🐛 Bug 修复

#### 侧边栏图标布局修复
- **问题**: 评分星标与选择框重叠，刷新后数字消失
- **修复**: 重构 `updateBookListIcon` 函数，智能更新图标而不破坏 DOM 结构
- **CSS 优化**: 调整 `.book-checkbox` 和 `.rating-icon-wrapper` 间距和层级

### 📝 修改文件清单
- `static/index.html` - 添加清除评分图标、批量操作弹窗
- `static/style.css` - 按钮变量化、过渡动画标准化、评分图标样式
- `static/js/modules/ui.js` - 评分处理、搜索筛选、图标更新逻辑
- `static/js/modules/libraryBatch.js` - **新增** 库管理批量操作模块

---

## [v0.5.0] - 2025-12-30

### ✨ 新功能

#### 智能导出与云盘上传 📤
- **格式自动识别**: 系统自动识别文件格式，无需转换的格式（PDF、TXT等）直接上传云盘
- **格式管理界面**: 在「设置 → 测试功能 (Beta)」中可配置需要转换为 PDF 的格式列表
  - 默认包含: EPUB, MOBI, AZW, AZW3, FB2, LIT, LRF, PDB
  - 支持添加/删除自定义格式
- **动态按钮行为**:
  - 需转换格式 (EPUB等): 显示"导出PDF"按钮，使用 Calibre 转换
  - 不需转换格式 + GDrive 已连接: 显示"上传云盘"按钮，直接上传
  - 不需转换格式 + GDrive 未连接: 按钮禁用（灰色）
- **直接上传端点**: 新增 `/api/direct_upload` API，支持非转换格式的直接上传

### 🐛 Bug 修复

####  保存按钮状态修复 💾
- **问题**: 点击"保存修改"后按钮重复触发，且保存成功后仍可连续点击
- **原因**: HTML onclick 与 JavaScript addEventListener 重复绑定
- **修复**: 
  - 移除 HTML 中的 `onclick` 属性，统一使用 JavaScript 事件绑定
  - 保存成功后按钮保持禁用状态，只有编辑元数据时才重新激活
  - 保存失败时按钮重新激活，允许用户重试

#### 文件路径解析优化 🔍
- **问题**: 在入库管理模式下，直接上传功能报 404 文件不存在
- **原因**: 路径解析逻辑与 `rename_only` 不一致，未正确处理相对路径
- **修复**: 统一路径解析逻辑
  - 优先尝试 source_dir (入库管理)
  - 回退到 target_dir (库管理)
  - 最后尝试绝对路径

### 🔧 技术改进

#### 打包脚本增强
- **版本更新**: build_standalone.sh 更新至 v0.5.0
- **新增依赖**: 添加 Google Drive 和 Calibre 相关的 hidden imports
  - `google.oauth2.credentials`
  - `google_auth_oauthlib`
  - `googleapiclient.discovery`
  - `googleapiclient.http`
  - `book_organizer.google_drive`
  - `book_organizer.calibre`

### 📝 修改文件清单
- `src/book_organizer/config.py` - 添加 convert_formats 默认配置
- `static/index.html` - 添加格式管理 UI、修复按钮重复绑定
- `static/js/modules/settings.js` - 格式增删逻辑
- `static/js/modules/ui.js` - 智能导出按钮动态行为、错误处理优化
- `static/style.css` - 格式标签和禁用按钮样式
- `src/server.py` - 新增 /api/direct_upload 端点、优化路径解析
- `static/js/modules/api.js` - 保存按钮状态管理优化
- `scripts/build_standalone.sh` - 更新版本号和依赖列表

---

## [v0.4.9] - 2025-12-28

### ✨ 新功能

#### Calibre PDF 转换功能增强 📄

- **多格式支持**: 扩展支持 EPUB/MOBI/AZW/AZW3/FB2/LIT/LRF/PDB 等格式转换为 PDF
- **PDF 导出目录设置**: 在「设置 → 测试功能 (Beta)」中可配置统一的 PDF 输出目录
  - 设置后所有转换的 PDF 保存到指定目录
  - 留空则保存在原电子书文件旁边（默认行为）
- **智能按钮显示**: PDF 文件不再显示"导出PDF"按钮（已经是 PDF，无需转换）

#### Google Drive 集成 ☁️

- **OAuth 2.0 认证**: 支持通过 Google Cloud 凭据授权连接
- **文件上传**: 将转换的 PDF 上传到 Google Drive
- **文件夹选择**: 可指定目标文件夹
- **自动上传**: 可开启 PDF 转换后自动上传
- **状态指示**: 显示连接状态（已连接/待授权/未配置）

### 🔧 技术改进

#### 后端
- `pdf_converter.py`: 
  - 新增 `CONVERTIBLE_FORMATS` 常量定义支持的格式
  - 新增 `is_convertible_format()` 格式检测函数
  - 重构 `convert_epub_to_pdf()` 为通用的 `convert_to_pdf()`
- `google_drive.py`: **新增** Google Drive OAuth 认证和上传模块
- `config.py`: 在 `beta_features` 中添加 `pdf_export_dir` 和 `google_drive` 配置
- `server.py`: 
  - `/api/calibre/status` 返回 `convertible_formats` 列表
  - `/api/google_drive/*` 新增 Google Drive 系列 API

#### 前端
- `index.html`: 在 Beta 功能页添加 PDF 导出目录和 Google Drive 配置 UI
- `settings.js`: Google Drive 授权/断开/文件夹选择交互逻辑
- `ui.js`: 多格式按钮显示逻辑
- `style.css`: Google Drive 状态指示灯样式

### 📝 修改文件清单
- `src/book_organizer/pdf_converter.py` - 多格式支持
- `src/book_organizer/google_drive.py` - **新增** Google Drive 集成
- `src/book_organizer/config.py` - 新增配置项
- `src/server.py` - API 增强
- `static/index.html` - 设置 UI
- `static/js/modules/settings.js` - 配置保存和 Google Drive 交互
- `static/js/modules/ui.js` - 按钮逻辑
- `static/style.css` - 状态指示灯样式

---



### ✨ 新功能

#### 记录查看器 📋
- **新增记录按钮**: 在头部导航栏添加绿色"记录"图标按钮，点击弹出记录查看器
- **双标签页切换**:
  - **转移记录**: 查看所有图书转移操作历史（原文件名、新文件名、目标分类、时间等）
  - **保存记录**: 查看所有增强简介保存历史
- **日期范围筛选**: 使用起止日期选择器筛选指定时间段的记录
- **模糊搜索**: 支持按文件名、书名、作者进行联合模糊搜索
- **分页功能**: 每页显示 50 条记录，支持上/下页翻页
- **详情悬停**: 鼠标悬停"查看"按钮显示完整详情（原文件名、新文件名、出版社、简介等）

#### 转移日志数据库迁移 🗄️
- **新增 `transfer_logs` 表**: 在 `book_data.db` 中创建专用表存储转移记录
- **迁移脚本**: 新增 `scripts/migrate_transfer_logs.py`，支持从 Markdown 日志批量导入历史记录
- **写入双轨制**: 转移操作同时写入数据库和 Markdown 日志（保持向后兼容）

### 🔧 优化

#### 后端 API 增强
- **新增 `/api/records/transfers`**: 支持 `start_date`, `end_date`, `search`, `page`, `page_size` 参数
- **新增 `/api/records/summaries`**: 同上
- **SQL 级搜索**: 搜索逻辑从内存过滤迁移到 SQL WHERE 子句，正确支持分页

#### UI 样式统一
- **高度对齐修复**: Tab 按钮与输入框统一使用 32px 高度 + `box-sizing: border-box`
- **盒模型统一**: 为按钮添加透明边框，确保与输入框物理结构一致
- **CSS 清理**: 移除重复的属性和注释

### 🐛 Bug 修复

- **分页行号修复**: 第 N 页显示正确的全局序号（如第2页显示 51-100）

### 📝 修改文件清单
- `static/index.html` - 添加记录按钮、弹窗 HTML、分页控件
- `static/style.css` - 添加记录表格、筛选器、分页控件样式
- `static/js/modules/records.js` - **新建** 弹窗交互逻辑
- `src/server.py` - 添加 `/api/records/transfers` 和 `/api/records/summaries` API
- `src/book_organizer/database.py` - 添加 `transfer_logs` 表和相关方法
- `src/book_organizer/transfer.py` - 写入转移日志到数据库
- `scripts/migrate_transfer_logs.py` - **新建** Markdown 日志迁移脚本

---


## [v0.4.7] - 2025-12-23

### 🐛 Bug 修复

#### PDF/EPUB 元数据写入竞态条件修复 🔒
- **问题**: 在高并发或快速操作下，写入元数据生成的固定备份文件名 (`.backup`) 可能引发冲突，导致文件被错误删除
- **解决方案**: 使用 UUID 生成唯一的备份文件名 (`.backup.<uuid>`)，确保每次写入操作的备份文件相互隔离

#### PDF 元数据类型修复
- **修复**: 解决了写入 PDF 元数据时 `dc:creator` 字段类型警告问题（应为列表而非字符串）

### 🧹 代码清理与质量提升

#### 全面代码检查 (Ruff) 🛠️
- **深度清理**: 使用 `ruff` 对全项目代码进行了深度检查和清理
- **逻辑缺陷修复**: 
  - 修复 `metadata.py` 中遗漏的 `Set` 类型导入
  - 修复 `server.py` 中 `analyze_full` 接口 `target_dir` 变量未定义导致的潜在崩溃
- **无效代码移除**: 
  - 移除了 `server.py`, `file_ops.py`, `metadata.py` 中定义的但从未使用的变量（如 `valid_exts`）
  - 移除了冗余的导入和赋值
- **格式规范化**: 
  - 修复了多处单行多语句 (`if x: return`)，提升代码可读性
  - 统一了代码风格

### 📝 修改文件清单
- `src/book_organizer/metadata.py` - 唯一备份文件名、类型修复、导入修复
- `src/server.py` - 变量修复、清理未使用代码
- `src/book_organizer/file_ops.py` - 清理未使用代码
- `src/book_organizer/transfer.py` - 清理未使用代码
- `src/book_organizer/ai_engines.py` - 格式规范化

---

## [v0.4.6] - 2025-12-23

### ⚡ 性能优化

#### 封面放大“秒开”体验 🚀
- **零延迟查看**: 点击封面放大时，直接复用前端已加载的内存数据（Blob URL），不再向服务器发起请求
- **并发无干扰**: 即使后台分析进程（Process）正在运行，查看大图也丝滑流畅，无需等待
- **网络优化**: 消除了查看大图时的冗余网络请求

### 📝 修改文件清单
- `static/js/modules/zoom.js` - 优先复用 Blob URL

#### 封面放大失效修复 🐛
- **Blob 生命周期管理**: 修复了优化后出现的封面放大失效（破图）问题
- **原因**: 原代码在图片加载完成时立即销毁 Blob URL，导致复用时链接已失效
- **修复**: 改为手动管理 Blob 生命周期，仅在加载新封面时销毁旧链接，确保放大功能始终可用
- **文件**: `static/js/modules/ui.js` - 移除自动 revoke，添加 activeCoverBlobUrl 管理

---

## [v0.4.5] - 2025-12-22

### ✨ 新功能

#### AI 模型状态指示灯 🚦
- **视觉反馈**: 在模型选择下拉菜单和设置界面为每个模型添加状态指示灯
  - 🟢 绿色：连接正常
  - 🔴 红色：连接失败或未配置
- **检查机制**: 使用 `list_models` 接口进行轻量级连通性测试，不消耗 Token
- **自定义模型支持**: 支持检测用户添加的自定义 Provider（如火山引擎）

### 🔧 优化

#### 状态检查性能优化
- **智能轮询**: 主界面只检查当前选中的模型（每 15 秒）
- **按需全量检查**: 打开下拉菜单或进入 AI 模型设置页时检查所有模型
- **减少网络请求**: 未选中的模型不进行后台轮询

#### 下拉菜单宽度自适应
- **动态宽度**: 模型选择按钮和菜单宽度根据最长模型名称自动调整
- **CSS 优化**: 使用 `width: max-content` 配合 min/max 约束

### 📝 文档更新
- **帮助文档**: 添加"AI 模型状态指示灯"说明章节
- **CHANGELOG**: 更新版本记录

### 📝 修改文件清单
- `static/app.js` - 重构 `startStatusPolling`，新增 `checkAllProviderStatus`
- `static/js/modules/settings.js` - 添加 `checkSettingsModelStatus` 和状态刷新逻辑
- `static/index.html` - 添加状态指示灯 DOM 元素和帮助说明
- `static/style.css` - 状态指示灯样式和下拉菜单宽度优化

---

## [v0.4.4] - 2025-12-21

### 🔧 重大修复

#### EPUB 元数据写入彻底重构 📖
- **问题**: 使用 ebooklib 的 `write_epub()` 会修改 EPUB 结构（spine/toc），导致目录多出 titlepage/cover 项
- **解决方案**: 完全绕过 ebooklib 写入，使用 **zipfile + lxml** 直接修改 OPF 文件
  - 只修改 metadata 部分，不触碰任何其他文件
  - 目录结构 100% 保持不变
- **支持字段**: title, creator, publisher, subject, calibre:series, description
- **稳定性**: 添加详细文档注释，标明此函数经过验证不应随意修改

#### 增强简介写入模式优化 ✨
- **简化逻辑**: 增强简介不再追加到原始描述后，而是**直接替换**
- **效果**: EPUB 阅读器中看到的是干净的增强简介内容，无分隔符

### ✨ 新功能

#### 数据加载优先级开关 🔀
- **新增设置**: 在「测试功能」中添加优先级切换按钮
- **两种模式**: 
  - 数据库优先（默认）：优先读取编辑后的内容
  - 元数据优先：优先读取文件内嵌的信息
- **UI 样式**: 使用左右拨动按钮组，与现有 UI 风格一致

### 🐛 Bug 修复

#### TOC 数据库同步修复
- **修复**: 在「保存修改」（rename_only）时同步更新 TOC 数据库文件名

### 📝 修改文件清单
- `src/book_organizer/metadata.py` - 重写 `write_epub_metadata()`，添加稳定性注释
- `src/server.py` - 添加数据优先级配置支持、TOC 数据库更新
- `static/index.html` - 添加数据优先级拨动按钮
- `static/js/modules/ui.js` - 加载优先级配置
- `static/js/modules/settings.js` - 保存优先级配置、添加 `setDataPriority()` 函数

---

## [v0.4.3] - 2025-12-21

### 🐛 Bug 修复

#### 批量处理交互修复 🔧
- **删除确认对话框**: 批量处理列表中的删除按钮现在会弹出确认对话框，防止误操作
- **执行完成按钮状态**: 批量执行完成后，正确重置所有按钮状态（隐藏取消和执行按钮，恢复开始分析按钮）

### 🔧 安全增强

#### 元数据写入格式验证 🛡️
- **新增格式验证**: EPUB/PDF 元数据写入后自动验证文件格式完整性
  - EPUB：检查 ZIP 结构、必需文件（mimetype、container.xml）、ebooklib 可读性
  - PDF：验证 pikepdf 可读性
- **失败自动回滚**: 验证失败时自动从备份恢复原始文件
- **转移操作保护**: 元数据写入失败会阻止后续转移操作，避免损坏文件被移动

#### EPUB Titlepage 修复工具 🔧
- **新增脚本**: `scripts/fix_epub_titlepage.py` 用于批量修复被 ebooklib 损坏的 titlepage 页面
- **智能检测**: 自动识别 SVG+image 格式的简单 titlepage（ebooklib 默认模板）
- **安全修复**: 从 OPF manifest/spine 中移除损坏的 titlepage 引用，删除对应文件
- **批量处理**: 支持目录递归、dry-run 预览模式

#### ebooklib 兼容性修复 🐛
- **修复 EpubCoverHtml 覆盖问题**: 写入 EPUB 时将 EpubCoverHtml 转换为普通 EpubHtml，保留原始封面页面内容

### 🔧 功能优化

#### 在库管理模式分析优化 📚
- **API 区分**: "在库管理"模式下使用 `/api/identify_metadata`（无目录建议），"入库整理"模式使用 `/api/analyze`（包含目录建议）
- **统一入口**: 两种模式共用 `analyzeBook()` 函数，内部自动判断

### 📝 修改文件清单
- `src/book_organizer/metadata.py` - 新增 `validate_epub_format()`、`validate_pdf_format()`，增强写入验证
- `src/book_organizer/transfer.py` - 检查写入返回值，失败则停止转移
- `static/js/modules/api.js` - 区分模式使用不同 API
- `scripts/fix_epub_titlepage.py` - 新增 titlepage 修复工具

---

## [v0.4.2] - 2025-12-20

### 🔧 优化改进

#### 数据目录配置项重命名 📁
- **配置项重命名**: 将 `enhanced_summary_dir` 重命名为 `data_dir`
  - 更准确地反映存储内容（增强简介 + 图书目录）
  - 界面标签从「增强简介目录」改为「数据目录」
- **自动迁移**: 旧配置会在启动时自动迁移，无需手动操作

#### 数据库文件合并 🗄️
- **统一数据库**: 将 `enhanced_summaries.db` 和 `book_tocs.db` 合并为单一的 `book_data.db`
  - 两张表（`enhanced_summaries` + `book_tocs`）存储在同一个数据库文件中
  - 便于备份和管理
- **自动数据迁移**: 首次启动时自动将旧数据库数据迁移到新库
- **兼容性**: 保持旧 API 完全兼容，无需修改其他代码
- **新增迁移脚本**: `scripts/migrate_database.py` 用于手动迁移（如需）

### 📝 技术细节

#### 修改文件清单
- `src/book_organizer/config.py` - 配置项自动迁移逻辑
- `src/book_organizer/database.py` - 完整重构，统一数据库类
- `src/server.py` - 更新 ConfigUpdate 模型
- `static/index.html` - 更新界面标签
- `static/js/modules/settings.js` - 更新配置保存
- `static/js/modules/ui.js` - 更新配置加载
- `scripts/migrate_database.py` - 新增迁移脚本

---

## [v0.4.1] - 2025-12-20

### 🐛 Bug 修复

#### AI 目录识别在库管理模式下 404 修复 📚
- **问题**: 在库管理模式（Library Mode）下，AI 目录识别功能报错 `404 Not Found`，导致无法进行 AI 目录提取
- **原因**: 
  - 前端 `extractToc` 函数仅从界面标签获取简短文件名（basename），丢失了包含子目录的完整路径
  - 后端在处理包含特殊字符（如空格、中文）的文件路径时，未强制进行 URL 解码
- **修复**:
  - **前端**: 
    - 修改 `ui.js`，在切换图书时将完整路径暴露为全局变量 `window.currentBookPath`
    - 修改 `app.js`，让目录提取功能优先使用内存中的完整路径而非界面文本
  - **后端**: 
    - 增强 `server.py` 的文件路径解析，添加强制 URL 解码 (`unquote`)
    - 增加针对书库根目录 (`target_dir`) 的显式路径拼接探测，确保能找到深层子目录中的文件

## [v0.4.0] - 2025-12-19

### ✨ 新功能

#### 附加规则 UI 全面升级 📋
- **规则来源区分**: 附加规则现在区分"AI生成"和"手工生成"两种来源
  - 不同来源的规则有独特的颜色标识（AI: 紫色, 手工: 蓝色）
  - 每条规则显示来源标签
- **来源筛选**: 底部切换按钮可筛选显示 AI 或手工规则
- **动态计数**: 切换按钮显示各类规则数量 `手工 (N)` / `AI (N)`
- **可配置 AI 规则数量**: 不再硬编码 7 条限制，用户可自定义 1-20 条

#### LiteLLM 集成 🔌
- **统一 AI 接口**: 使用 LiteLLM 作为主要 AI 集成
- **原生 SDK 作为备用**: 保留 google-generativeai, ollama, openai 作为可选回退
- **打包优化**: 构建时可排除原生 SDK，减小包体积

#### Framework 引擎架构（实验性） 🧪
- 新增 `framework/` 目录，提供可扩展的引擎架构
- 支持自定义分析引擎插件

### 🔧 优化

#### 打包脚本更新
- `build_standalone.sh` 现使用 LiteLLM，排除原生 AI SDK
- 删除不再使用的脚本: `import_md_summaries.py`, `verify_fixes.sh`, `export_source.sh`, `convert_icon.sh`, `create_app.sh`

### 📚 文档

- 更新 `PROJECT_STRUCTURE.md` 反映脚本变更
- 附加规则标签页帮助文字完善

---

## [v0.3.30] - 2025-12-17

### 🐛 Bug 修复

#### 统计显示问题修复 📊
- **修复"未增强"统计显示为0**: `switchMode`函数遗漏了更新`lib-not-enhanced`元素，导致切换到在库管理模式时未增强数量始终显示为0
- **后端数据正确**: API返回的`not_enhanced`值正确（len(books) - enhanced_count），问题仅在前端显示

#### 顺序处理封面加载修复 🖼️
- **问题**: 顺序处理时，切换到下一本书时封面在分析完成前无法加载
- **原因**: 封面请求与分析请求竞争，分析阻塞了封面加载
- **修复**: 
  - `loadCover`函数改为返回Promise
  - `processNextSequential`改为async函数
  - 在开始分析前等待封面加载完成（最多3秒超时）

#### 图书类型图标修复 📚
- **问题**: 即使是epub文件，封面未加载时显示PDF图标
- **修复**: 根据文件扩展名动态设置正确图标
  - `.epub` → 书本图标
  - `.mobi/.azw3/.azw` → Amazon图标
  - `.pdf` → PDF图标

#### 封面放大功能修复 🔍
- **问题**: 点击封面放大时显示破损图片
- **原因**: blob URL在某些情况下失效
- **修复**: 放大时重新从API获取封面，添加`naturalWidth > 0`检查

#### 增强信息显示修复 ✨
- **问题**: 顺序处理时显示上一本书的增强信息
- **修复**: 切换书籍时立即隐藏增强信息区域，即使在顺序模式下

### 🎨 UI/UX 改进

#### 侧边栏标题样式优化
- **简化设计**: 移除蓝色背景框，改为简洁的蓝色图标+蓝色文字
- **与统计栏关联**: 高度设为28px，与stats-bar保持一致
- **水平排列**: 图标和文字水平排列，更简洁

#### 统计标签浮动tooltip
- **新样式**: 标签改为绝对定位的浮动tooltip
- **显示位置**: 从底部滑出，居中对齐
- **视觉效果**: 黑色背景、白色文字、圆角阴影

#### 加载圈样式统一 ⭕
- **统一颜色**: 所有spinner改为淡白色光圈
  - 底圈: `rgba(255, 255, 255, 0.15)`
  - 顶部: `rgba(255, 255, 255, 0.7)`
- **移除蓝色**: 不再使用`var(--primary-color)`

### 🔧 功能优化

#### 批量处理确认窗简化
- **移除确认**: 从批量处理列表移除项目不再需要确认
- **更流畅**: 直接删除，操作更快

### 📝 修改文件清单
- `static/js/modules/ui.js` - 封面加载Promise、统计更新、图标类型
- `static/js/modules/batch.js` - 顺序处理async、移除确认窗
- `static/js/modules/zoom.js` - 封面放大修复
- `static/style.css` - 侧边栏样式、tooltip样式、spinner统一
- `static/index.html` - 侧边栏标题结构

---



### ⚡ 性能优化

#### 分析进程即时终止 🛑
- **问题**: 在顺序处理或手动分析时，切换书籍或点击"停止分析"需要等待当前分析完成，封面和元数据无法立即加载
- **原因**: Python GIL（全局解释器锁）限制，即使使用 `asyncio.to_thread` 也无法实现真正的并发
- **解决方案**: 使用 **多进程** (`multiprocessing.Process`) 运行分析任务
  - 分析在独立子进程中运行，与主服务器完全隔离
  - 新增 `/api/analyze/cancel` 端点，调用 `process.terminate()` 强制杀死分析进程
  - 切换书籍或停止分析时，后端进程被立即终止
  - 主服务器进程立即释放，可以处理封面/元数据请求

### 🔧 技术改进

#### 后端改动 (`server.py`)
- 新增 `_run_analysis_in_process()` - 子进程分析函数
- 新增 `/api/analyze/cancel` 端点 - 强制终止分析进程
- 重构 `/api/analyze` - 使用 `multiprocessing.Process` 和 `Queue` 进行进程间通信
- 使用 `asyncio.to_thread` 优化 `/api/cover` 和 `/api/metadata` 异步处理

#### 前端改动
- `ui.js:selectBook` - 切换书籍时调用取消端点
- `ui.js:selectLibraryBook` - 图书馆模式切换时调用取消端点
- `api.js:analyzeBook` - 点击停止分析按钮时调用取消端点
- `batch.js:stopSequential` - 停止顺序处理时调用取消端点
- `ui.js:loadCover` - 使用 fetch API 的 `priority: 'high'` 提示优先加载封面

### 📝 修改文件清单
- `src/server.py` - 多进程分析实现、取消端点、async 优化
- `static/js/modules/ui.js` - 添加取消调用、封面加载优化
- `static/js/modules/api.js` - 添加取消调用
- `static/js/modules/batch.js` - 添加取消调用

---

## [v0.3.28] - 2025-12-15

### 🐛 Bug 修复

#### 顺序处理模式封面加载修复 🖼️
- **问题**: 在顺序处理模式下，第一本书封面正常显示，但切换到下一本书时封面无法加载
- **原因**: 使用中间 `Image` 对象预加载时存在竞态条件，导致 `onload` 回调未正确触发
- **修复**: 
  - 直接在 `bookCoverEl` 上设置 `onload/onerror` 事件处理器
  - 添加时间戳参数 (`?t=${Date.now()}`) 避免浏览器缓存问题
  - 简化加载流程，消除中间 `Image` 对象

#### 顺序模式跳过按钮优化 ⏭️
- **问题**: 在 AI 分析进行中点击"跳过"按钮时，需要等待分析完成才能跳过
- **修复**: 
  - 点击跳过时立即取消正在进行的 AI 分析 (`currentAnalysisController.abort()`)
  - 取消元数据识别请求 (`currentIdentifyController.abort()`)
  - 取消增强简介请求 (`currentEnhancedSummaryController.abort()`)
  - 重置加载状态 (`showAnalysisLoading(false)`)
  - 跳过确认对话框，直接执行跳过
  - 标记当前书籍为"已跳过"并自动处理下一本

### 📝 技术细节

#### 修改文件清单
- `static/js/modules/ui.js` - 优化 `loadCover` 函数，修复封面加载竞态条件
- `static/js/modules/api.js` - 增强 `skipBook` 函数，添加请求取消逻辑

---

## [v0.3.27] - 2025-12-15

### 🐛 Bug 修复

#### 增强简介保存问题修复 💾
- **问题**: 在库管理模式下生成增强简介后点击"保存修改"，切换图书后再回来增强简介丢失
- **原因**: `window.currentBookSummary` 变量作用域不一致
- **修复**: 统一所有模块使用 `window.currentBookSummary`
  - `state.js`: 添加 `window.currentBookSummary` 初始化同步
  - `api.js`: 第134、178行改为使用 `window.currentBookSummary`
  - `ui.js`: 第177行改为使用 `window.currentBookSummary`

#### 分析功能模式参数修复 🔧
- **问题**: `analyzeBook` 函数硬编码了 `'organize'` 模式，导致在库管理模式下增强简介请求使用错误的模式参数
- **修复**: 将 `'organize'` 改为 `currentMode`，确保两种模式下行为一致

### ✨ 功能增强

#### 文件重命名冲突处理优化 📁
- **新策略**: 使用中转文件名策略，避免产生 `_1` 后缀
  - 步骤1: 源文件 → 临时文件名 (`.tmp_xxxx`)
  - 步骤2: 删除同名旧文件（如果存在）
  - 步骤3: 临时文件 → 正式文件名
- **优点**: 
  - ✅ 完全不产生 `_1` 后缀
  - ✅ 自动处理群晖 Drive 同步冲突
  - ✅ 出错时自动恢复
- **影响文件**: `server.py:rename_only`、`transfer.py:rename_and_move_book`

### 🎨 UI/UX 改进

#### 在库管理模式下禁用不适用功能 🔒
- **批量按钮**: 在库管理模式下禁用，显示提示"批量功能仅在入库整理模式下可用"
- **跳过按钮**: 在库管理模式下禁用，显示提示"跳过功能仅在入库整理模式下可用"
- **视觉效果**: 禁用按钮显示灰色、半透明、不可点击

### 📝 技术细节

#### 修改文件清单
- `src/server.py` - 中转文件名重命名策略
- `src/book_organizer/transfer.py` - 中转文件名移动策略
- `static/js/modules/state.js` - window.currentBookSummary 同步
- `static/js/modules/api.js` - 修复变量引用和模式参数
- `static/js/modules/ui.js` - 修复变量引用、添加按钮禁用逻辑
- `static/style.css` - 禁用按钮样式

---



### ✨ 新增功能

#### 增强简介数据库改为文件名关联 📁
- **问题背景**: 原设计使用完整文件路径关联，导致重命名或移动文件后丢失关联
- **新设计**: 改为使用文件名（basename）作为主要关联键
  - `database.py` 新增 `update_filename()` 方法，重命名时自动更新关联
  - `get_summary()` 改为优先通过文件名匹配，回退到完整路径（兼容旧数据）
- **同步更新**: 
  - `server.py` 的 `rename_only` API 调用 `update_filename()` 保持关联
  - `transfer.py` 的 `rename_and_move_book()` 同样调用 `update_filename()`
- **效果**: 移动或重命名图书后，增强简介仍能正确匹配

#### MD 文件增强信息导入工具 📥
- **新增脚本**: `scripts/import_md_summaries.py`
- **功能**: 从 Markdown 文件批量导入图书增强信息到数据库
- **智能匹配**:
  - 优先检查 MD 中记录的完整路径是否存在
  - 如果不存在，通过文件名在图书库中搜索
  - 只导入实际存在的文件，跳过不存在的
- **参数支持**:
  - `--clear`: 先清空数据库再导入
  - `--dry-run`: 预览模式，不实际导入

### 🔧 优化改进

#### 前端匹配逻辑简化
- **统一匹配**: 图书馆列表的增强状态判断改为只使用文件名匹配
- **与数据库一致**: 确保前后端使用相同的关联方式

### 📝 技术细节

#### 修改文件清单
- `src/book_organizer/database.py` - 新增 `update_filename()`，修改 `get_summary()` 匹配逻辑
- `src/server.py` - 更新 `rename_only` API 和图书馆列表匹配逻辑
- `src/book_organizer/transfer.py` - 更新 `rename_and_move_book()` 调用
- `scripts/import_md_summaries.py` - 新增 MD 导入脚本

---



### 🐛 Bug 修复

#### 打包应用问题修复
- **修复设置持久化**: 将前端设置（增强模式、AI模型选择、联网搜索）从 `localStorage` 迁移至后端 API
  - `localStorage` 在 pywebview 打包应用中不可靠
  - 新增 `GET/POST /api/user_preferences` 端点
  - 设置现保存于 `~/.book_organizer/book_organizer_config.json`
- **修复增强简介 404 错误**: 将 `/api/enhanced_summary` 端点定义移到 `if __name__ == "__main__":` 代码块外部
  - PyInstaller 打包后，该代码块内的路由不会被注册
  - 移动后端点在打包应用中正常工作
- **修复顺序执行列表闪烁**: 顺序执行时左侧图书列表不再显示"加载中"状态

### 🎨 UI/UX 改进

#### 按钮样式统一
- **识别信息按钮**: 运行状态改为与增强简介按钮一致
  - 使用橙色背景 + 白色 spinner + 脉冲动画
  - 添加 `.analyzing` 类实现统一视觉效果
- **加载圈颜色修复**: 橙色按钮内的 spinner 现显示为白色而非蓝色

### 🔧 逻辑优化

#### 按钮联动修正
- **移除错误联动**: 点击"识别信息"按钮不再自动触发"增强简介"
- **保留正确联动**: 只有"开始信息及目录分析"在增强模式开启时同时调用两者
- **清晰职责**: 各按钮功能独立，用户可自由选择操作

### ✨ 新增功能

#### GitHub Actions 多平台构建
- **自动化打包**: 添加 `.github/workflows/build.yml`
- **Windows 构建**: 使用 GitHub `windows-latest` runner 自动打包
- **macOS 构建**: 使用 GitHub `macos-latest` runner 自动打包
- **触发方式**: 版本标签推送（v*）或手动触发

### 📝 技术细节

#### 修改文件清单
- `src/server.py` - 新增用户偏好 API、移动增强简介端点
- `static/app.js` - 迁移模型选择、联网搜索到后端 API
- `static/js/modules/ui.js` - 迁移增强模式到后端 API
- `static/js/modules/settings.js` - 统一按钮样式、移除错误联动
- `static/js/modules/api.js` - 更新增强模式检查、修复顺序执行列表闪烁
- `static/ai_config.js` - 更新 AI 状态指示器
- `static/style.css` - 添加白色 spinner 样式
- `.github/workflows/build.yml` - 新增多平台自动构建工作流

---





### 🐛 Bug 修复

#### 增强简介保存逻辑修复
- **修复自动保存问题**: 增强简介不再在生成时自动保存到数据库
  - 移除 `/api/enhanced_summary` 端点中的自动保存逻辑
  - 现在仅在用户点击"保存修改"或"转移图书"时才保存增强简介
  - 确保与元数据识别功能保持相同的用户确认流程
- **前后端一致性**: 批量处理、单本保存和转移操作都正确保存增强简介到数据库

### 🎨 UI/UX 改进

#### 设置模态框全面优化
- **尺寸统一**: 系统设置模态框尺寸从 700x500 调整为 850x650，与AI配置模态框保持一致
- **滚动修复**: 修复测试功能标签页滚动失效和按钮错位问题
  - 将footer移出scrollable-content区域
  - 创建全局footer，根据标签页动态切换显示按钮
- **间距优化**: 优化通用设置表单字段间距（margin-bottom: 16px），视觉更协调
- **标签页说明**: 为通用设置和AI模型标签页添加页面说明
  - 通用设置：目录配置说明（文件夹树图标）
  - AI模型：AI引擎配置说明（大脑图标）
  - 样式与Beta功能标签页保持一致

### 🔧 显示逻辑优化

#### 增强简介显示分离
- **AI分析区域**: 显示简短的图书摘要（data.summary）
- **增强简介区域**: 显示详细的增强内容（图书简介、详细要点、具体应用）
- **实时更新**: 分析完成后增强简介立即显示在专用区域，无需刷新页面
- **逻辑清晰**: 不再混淆简短摘要和详细增强简介，各司其职

### 📚 文档更新

- 更新 `README.md` - 添加增强简介功能、Beta功能说明
- 更新 `PROJECT_STRUCTURE.md` - 添加 `database.py` 模块和增强简介数据库说明
- 更新 `CHANGELOG.md` - 本版本更新记录

---

## [v0.3.23] - 2025-12-13

### 🐛 Bug 修复

#### 稳定性修复
- **修复 500 Internal Server Error**: 修复了 AI 返回 Markdown 格式 JSON 时导致解析失败的问题（增强简介生成）
- **修复 UnboundLocalError**: 修复了在元数据已锁定的情况下，单本分析流程未正确初始化变量导致的崩溃问题

#### 其他


#### 后端模块化
- **拆分 `book_organizer.py`**: 原 2659 行单体文件拆分为 6 个独立模块：
  - `config.py` (~190 行): 配置加载/保存、常量定义
  - `ai_engines.py` (~550 行): Gemini/DeepSeek/Ollama 集成
  - `metadata.py` (~350 行): PDF/EPUB 元数据提取和写入
  - `file_ops.py` (~270 行): 文件扫描、封面提取
  - `search.py` (~55 行): DuckDuckGo 在线搜索
  - `transfer.py` (~230 行): 重命名/移动、转移日志
- **模块化包**: 创建 `src/book_organizer/` 包，导出 25 个公共函数

#### 前端模块化
- **拆分 `app.js`**: 原 1817 行单体文件拆分为 6 个独立模块：
  - `state.js` (~107 行): 全局状态和 DOM 引用
  - `api.js` (~370 行): 后端 API 调用
  - `ui.js` (~363 行): UI 渲染和通知
  - `batch.js` (~378 行): 批量分析和执行
  - `zoom.js` (~98 行): 封面缩放功能
  - `settings.js` (~325 行): 设置管理和元数据识别
- **入口精简**: `app.js` 精简为 142 行的入口文件

### ✨ 功能增强

#### AI 配置
- **字段提取恢复默认**: 为"字段提取"标签页添加"恢复默认"按钮，样式与"核心规则"一致

#### 增强模式与简介按钮优化
- **增强简介生成**: 优化了增强简介的生成逻辑，支持流式加载状态和错误处理
- **富文本展示**: "增强简介"现在支持 Markdown 格式的富文本展示，自动解析并分节显示（图书简介、详细要点、具体应用）
- **UI 交互优化**: 
  - 增强模式按钮状态现在持久化保存
  - 生成结果支持一键复制和重新生成
  - 优化了加载动画和空白状态

### 📚 文档更新

- 更新 `PROJECT_STRUCTURE.md` 反映新的模块化架构
- 更新 `docs/technical/architecture.md` 添加架构图
- 清理过时文档，归档已完成的阶段性文档
- 删除重复的 `project-map.md`

### 🧹 清理

- 删除遗留文件: `book_organizer_legacy.py`, `app_legacy.js`
- 删除测试脚本: `manage_summaries_v2.sh`
- 归档 Phase1 相关文档到 `docs/archived/development/`
- 更新 `build_standalone.sh` 以支持新的包结构

---

## [v0.3.22] - 2025-12-12

### 🎨 UI/UX 改进

#### 顶部操作栏重构
- **AI 模型移动**:
  - 将 AI 模型选择下拉框移至页面顶部操作栏（靠近“联网”按钮），操作路径更短。
  - 新的选择框风格与顶部其他按钮保持高度一致。
- **视觉风格统一**:
  - **紧凑设计**: 将顶部所有按钮的高度从 40px 统一调整为 **36px**。
  - **字体规范**: 所有相关按钮（分析、跳过、删除、顶部功能键）字体大小统一为 **0.9rem**。
  - **布局优化**: 减小了顶部按钮之间的间距，使头部区域更加紧凑、精致。
- **按钮样式细化**:
  - 新增 `.header-select` 样式，让下拉框拥有与 `.btn-icon` 相同的玻璃拟态背景和悬停效果。
  - 调整 `.btn-primary`, `.btn-secondary`, `.btn-danger` 样式以匹配新的紧凑标准。

### ✨ 功能增强

#### 设置持久化
- **AI 模型记忆**: 
  - 现在只需选择一次 AI 模型（Gemini/DeepSeek/Ollama），系统会在下次打开时自动记住并恢复您的选择。
  - 修复了模型选择状态在页面刷新后重置的问题。
  - 初始化逻辑优化：保证在应用启动的最早阶段读取本地缓存。
- **错误通知优化**:
  - API 错误（如分析失败、网络超时）现在会通过右下角的**浮动通知框**显示，不再使用阻断式的 Alert 弹窗。
  - 错误提示时间延长至 **8秒**，确保用户有足够时间阅读报错信息。

### 🔧 技术细节

- **初始化顺序调整**: 将 `initEngineSelection` 提升到 `init()` 函数的首位执行，确保 DOM 渲染后立即应用缓存设置。
- **CSS 变量**: 继续强化 CSS 变量的使用，减少硬编码的样式值。
# 📝 更新日志

本文档记录 BookOrganizer 项目的所有重要更改。

---

## [v0.3.21] - 2025-12-06

### 🐛 Bug 修复

#### 控制逻辑修复
- **修复 [停止顺序处理] 按钮**: 
  - 点击时现在会**同步中止**当前正在进行的 AI 分析，确保后台任务完全停止。
- **修复 [停止分析] 按钮**: 
  - 之前: 点击时会中止当前分析但错误地立即重启新分析。
  - 现在: 点击时**只中止**当前分析，不重启。
  - **保持模式**: 单独停止 AI 分析**不会取消**顺序处理模式，允许手动继续操作。

#### 预览功能修复
- **修复 EPUB 预览**: 解决了部分 EPUB 文件无法正确提取并显示封面和元数据的问题。

---

## [v0.3.20] - 2025-12-05

### 🗜️ 打包优化

#### 应用体积优化 (200M+ → 132M，节省 34%)
- **问题分析**:
  - 打包后应用达到 200M+，主要原因是包含了 googleapiclient (91M)
  - `google-generativeai` 依赖了 `google-api-python-client`，但运行时不需要
  
- **优化方案**:
  - 采用"打包后删除"策略，在 PyInstaller 构建完成后自动删除不必要的模块
  - 删除 `googleapiclient`、`httplib2`、`uritemplate` 等未使用的依赖
  - 集成 UPX 压缩支持（可选，自动检测）
  
- **优化效果**:
  - ✅ 应用大小: 200M+ → **132M** (节省 68M，34%)
  - ✅ 删除 googleapiclient: **-91M**
  - ✅ 功能完整性: 100% 保留，google.generativeai 正常工作
  
- **构建脚本增强**:
  - 自动检测并使用 UPX（如已安装）
  - 打包后自动清理不必要模块
  - 显示最终应用大小

### 📚 文档完善

#### 技术文档新增
- **新增** `docs/technical/package-optimization-guide.md` - 打包优化完整指南
  - 优化方案详解
  - 依赖占用分析
  - 进一步优化建议
  
- **新增** `docs/technical/package-dependencies-size.md` - 依赖占用详细分析
  - Top 10 依赖组件大小
  - 按功能分类统计
  - 可选优化方案
  
- **新增** `docs/technical/compression-options.md` - 压缩方案对比
  - UPX 压缩说明
  - PIL 优化建议
  - API 重构方案对比

### 🧹 代码清理

- **删除** `hooks/` 目录 - 已不需要的 PyInstaller hooks
- **删除** `scripts/build_standalone_optimized.sh` - 已合并到主脚本
- **删除** `requirements-minimal.txt` - 未使用的依赖文件
- **删除** 重复的优化文档，统一为主文档

### 🔧 技术细节

#### 修改的文件
- `scripts/build_standalone.sh` - 集成优化和清理逻辑
- `CHANGELOG.md` - 添加版本记录

#### 依赖占用分布
| 组件 | 大小 | 占比 | 用途 |
|------|------|------|------|
| pymupdf | 44M | 33% | PDF处理 |
| grpc | 18M | 14% | Google AI通信 |
| 主程序 | 13M | 10% | BookOrganizer |
| pikepdf | 13M | 10% | PDF XMP元数据 |
| Python运行时 | 11M | 8% | Python 3.13 |
| 其他 | 33M | 25% | 各种依赖 |

---


### 🐛 Bug 修复

#### 顶部按钮交互优化 🖱️
- **修复旋转Bug**：
  - 移除了"刷新"按钮和"设置"按钮在鼠标悬停时的旋转效果
  - 原问题：鼠标悬停时图标会发生90度或180度旋转，影响用户体验
  - 解决方案：将 `transform: rotate()` 改为 `transform: translateY(-1px)` 轻微上移效果
  - 统一所有按钮的hover交互方式

- **联网按钮样式统一**：
  - 将"已关闭联网"按钮的默认状态颜色改为与"设置"按钮一致的灰色
  - 背景色：`rgba(107, 114, 128, 0.15)`
  - 文字颜色：`#6b7280`
  - 边框颜色：`rgba(107, 114, 128, 0.3)`
  - 确保关闭状态下图标和文字都显示为统一的灰色调

### 🎨 UI/UX 优化

#### 按钮颜色统一 🎨
- **AI配置按钮颜色调整**：
  - 将"AI配置"按钮从紫色改为蓝色，与"批量处理"按钮保持一致
  - 背景色：`rgba(59, 130, 246, 0.15)`
  - 文字颜色：`#3b82f6`
  - 边框颜色：`rgba(59, 130, 246, 0.3)`
  - Hover背景色：`rgba(59, 130, 246, 0.25)`
  - 提升顶部按钮组的视觉一致性

#### 通知系统优化 🔔
- **智能提示框替换确认对话框**：
  - 保留：删除图书、跳过图书、批量删除等关键操作的确认窗口
  - 改进：将其他非破坏性操作的 alert/confirm 改为优雅的浮动提示框
  - 新增 `showNotification()` 函数，统一管理非关键通知
  - 提示框自动在1-2秒后消失，不打断用户操作流程
  
- **已优化的操作**：
  - 顺序处理完成提示
  - 批量执行操作（移除确认，直接执行）
  - 文件删除成功/失败提示
  - 分析失败提示
  - AI配置保存成功/失败
  - 添加规则超限提示
  - 恢复默认规则/设置
  - AI优化规则结果
  - 清除模型配置

### 🔧 CSS 优化

#### 样式清理
- **移除重复CSS规则**：
  - 删除了第318-322行重复的 `.btn-icon:hover` 规则
  - 该规则会覆盖前面特定按钮的hover样式，导致样式冲突
  - 确保每个按钮的hover效果按预期工作

### ✅ 测试验证
- ✅ 刷新按钮悬停时不再旋转，改为轻微上移
- ✅ 设置按钮悬停时不再旋转，改为轻微上移
- ✅ 已关闭联网按钮显示为灰色，与设置按钮颜色一致
- ✅ 已开启联网按钮显示为绿色（保持不变）
- ✅ AI配置按钮显示为蓝色，与批量处理按钮颜色一致
- ✅ 所有按钮hover效果统一且流畅

---

## [v0.3.18] - 2025-11-29

### 🎨 UI/UX 重构与优化

#### 联网搜索按钮彻底重构 🌐
- **从Toggle开关改为点击式按钮**：
  - 删除旧的滑动开关组件，采用与其他按钮一致的点击式设计
  - 使用地球图标 (`fa-globe`) + 文字的组合形式
  - 位置调整到顶部栏**最左侧**（第一顺位），在"顺序处理"按钮之前
  
- **视觉状态优化**：
  - **关闭状态（默认）**：灰色图标和文字，显示"已关闭联网"，与其他普通按钮视觉一致
  - **开启状态（激活）**：绿色图标和文字，显示"已开启联网"，带有 `.active` 类的高亮效果
  - 点击按钮即可切换状态，状态通过 localStorage 持久化保存
  
- **CSS嵌套错误修复**：
  - 清理了 `.sidebar h3` 样式块中错误嵌套的 `.actions`、`.header-toggle` 等代码
  - 删除孤立的 `border-bottom` 属性和多余的闭合括号
  - 重新组织 header 区域的样式结构，确保所有按钮样式正确应用

#### 顺序处理按钮样式统一 🔄
- **颜色调整**：
  - 将默认状态从绿色改为**蓝色**（与"批量处理"按钮保持一致）
  - 使用 `rgba(59, 130, 246, 0.15)` 蓝色背景
  
- **激活状态优化**：
  - 点击后变成"停止顺序处理"时，使用**橙色**高亮样式
  - 完全匹配"停止分析"按钮的视觉效果：
    - 橙色背景：`rgba(245, 158, 11, 0.2)`
    - 橙色文字：`#f59e0b`
    - 添加脉冲动画效果 (`pulse` animation)
  
- **交互体验改进**：
  - 删除停止顺序处理时的 alert 弹窗，改为静默停止
  - 统一图标使用：恢复时使用 `fa-play` 图标（与初始状态一致）

### 🔧 技术改进

#### JavaScript 重构
- 新增 `isWebSearchEnabled` 全局变量跟踪联网搜索状态
- 重写 `initSearchToggle()` 函数处理按钮点击事件
- 新增 `updateWebSearchButton()` 函数动态更新按钮外观
- 更新所有使用联网搜索状态的函数（`analyzeBook`、`identifyMetadata`）

#### CSS 优化
- 新增 `.glass-header .actions` 容器样式
- 统一 `.btn-icon` 基础样式（高度、padding、边框等）
- 新增 `#web-search-btn` 和 `#web-search-btn.active` 样式
- 新增 `#seq-btn.active-mode` 橙色激活状态样式

### ✅ 测试验证
- ✅ 联网搜索按钮位于最左侧，默认绿色"已开启联网"
- ✅ 点击切换到灰色"已关闭联网"状态正常
- ✅ 再次点击恢复绿色"已开启联网"状态正常
- ✅ 顺序处理按钮默认显示蓝色
- ✅ 点击后变为橙色"停止顺序处理"，带脉冲动画
- ✅ 停止时无弹窗，按钮平滑恢复蓝色
- ✅ 所有按钮高度、样式完全对齐，零误差

---

## [v0.3.17] - 2025-11-29

### ✨ 功能增强

#### 转移操作加载提示 💫
- **新增**: 在转移图书时显示非侵入式的加载提示
- **位置**: 右下角浮动提示框，显示"正在转移图书..."
- **效果**: 解决大文件转移时的"无响应"感，提供即时的视觉反馈
- **设计**: 使用玻璃拟态效果，带旋转加载动画，不阻塞用户操作

### 📝 说明

#### 批量处理流程确认
- **批量处理逻辑**: 点击"确认并执行"后，系统会逐本处理：
  1. 写入元数据（如果格式支持，如 EPUB 和 PDF）
  2. 修改文件名
  3. 转移到目标目录（如果目标目录不为空）
- **流程稳定性**: 批量处理不会因为跳过、删除等操作而中断，只有点击"停止"按钮才会终止

---
## [v0.3.16] - 2025-11-29

### 🐛 Bug 修复

#### 顺序处理模式优化 🔄
- **修复**: 在顺序处理模式下删除图书后，现在会正确继续处理下一本图书（之前会中断流程）
- **增强**: 顺序处理按钮现在具有明确的视觉反馈和停止功能
  - 激活时显示"停止顺序处理"并变为橙色高亮
  - 点击可随时停止顺序处理流程
  - 完成所有图书后自动退出顺序模式

---
## [v0.3.15] - 2025-11-29

### ✨ 功能增强

#### 元数据锁定机制 🔒
- **新增**: 在单本分析流程中引入"元数据锁定"机制
- **逻辑**: 
  - 当用户手动修改或 AI 已识别元数据后，再次点击"开始信息及目录分析"时，系统将**锁定**当前元数据
  - AI 将仅基于当前锁定的元数据重新生成图书简介和目录建议，而**不再**尝试修改或覆盖元数据
  - 只有切换图书或显式点击"AI 识别信息"按钮，才能解除锁定并重新识别元数据
- **场景**: 完美支持"识别 -> 微调元数据 -> 重新生成简介/目录"的工作流，防止微调后的元数据被 AI 覆盖

---
## [v0.3.14] - 2025-11-29

### ⚡️ 性能与体验优化

#### 转移操作即时响应 🚀
- **优化**: 重构了图书转移后的前端处理逻辑
- **改进**: 点击"转移"后立即更新 UI 并切换到下一本书，不再等待后台文件列表同步
- **效果**: 彻底消除了点击转移按钮后的"无反应"延迟感，并防止了因重复点击导致的"源文件不存在"错误
- **机制**: 采用乐观 UI 更新策略 (Optimistic UI Update)，后台异步同步状态

---
## [v0.3.13] - 2025-11-29

### 🐛 Bug 修复

#### 转移后文件状态同步修复 🔄
- **修复**: 解决点击"转移"后再次操作提示"源文件不存在"的问题
- **原因**: 浏览器缓存了图书列表 API 的响应，导致前端未能及时感知文件已被移动
- **解决**: 在请求图书列表时添加时间戳参数，强制刷新缓存

### ✨ 功能增强

#### PDF 转移时元数据写入 📄
- **增强**: 在执行"转移"操作时，现在也支持写入 PDF 元数据（此前仅支持 EPUB）
- **一致性**: 确保"转移"操作与"仅重命名"操作在元数据处理逻辑上保持一致
- **配置**: 遵循 `enable_metadata_write_pdf` Beta 配置项

---
## [v0.3.12] - 2025-11-28

### 🎨 前端标准化与设计系统建立

#### CSS 变量系统扩展 📐
- **新增30+个CSS变量**，实现完整的设计标记系统：
  - **按钮尺寸标准**: 
    - `--btn-height-sm/md/lg` (36px/40px/44px)
    - `--btn-padding-x-sm/md/lg` (16px/20px/24px)
    - `--btn-font-size-sm/md/lg`
    - `--btn-gap` (8px)
  - **模态框尺寸标准**:
    - `--modal-width-sm/md/lg/batch` (480px/960px/1152px/800px)
    - `--modal-max-width/height/height-lg` (95%/84vh/90vh)
    - `--modal-header-padding` (20px 24px 16px 24px)
    - `--modal-body-padding` (24px)
    - `--modal-content-padding-bottom` (12px)
  - **标签页标准**:
    - `--tab-padding` (12px 24px 0 24px)
    - `--tab-gap` (8px)

#### 模态框底部间距优化 📏
- **精确控制底部按钮区域间距**:
  - 按钮上方: 10px (`--modal-footer-padding-top`)
  - 按钮下方: 6px (`--modal-footer-padding-bottom`)
  - 按钮左右: 24px (`--modal-footer-padding-x`)
  - **总高度**: 56px (10px + 40px + 6px)
  - **优化效果**: 相比原来的88px，减少约36%的空间占用

#### 所有模态框统一应用固定底部布局 🪟
- **批量处理弹窗**: 底部按钮固定，表格区域可滚动
- **AI配置弹窗**: 底部按钮固定，配置内容可滚动
- **设置弹窗**: 底部按钮固定，设置项可滚动
- **目录选择弹窗**: 底部按钮固定，目录列表可滚动

#### 样式规范化 ✨
- **替换所有硬编码值**为CSS变量:
  - 模态框宽度/高度
  - 按钮尺寸和padding
  - 内边距和间距
- **统一所有按钮样式**:
  - 使用 `var(--btn-height-md)` 替代硬编码的 `40px`
  - 使用 `var(--btn-font-size-md)` 替代硬编码的 `0.95rem`
  - 使用 `var(--btn-gap)` 控制图标与文字间距

### 📖 设计规范文档

#### 新增完整设计规范 `docs/DESIGN_GUIDE.md`
-包含以下章节：
  1. **设计原则**: 一致性、可访问性、美观性、性能优先
  2. **颜色系统**: 背景色、主题色、功能色、文字颜色（完整的CSS变量列表）
  3. **间距系统**: xs/sm/md/lg/xl (4px/8px/16px/24px/32px)
  4. **字体系统**: Inter字体，标准字号规范
  5. **按钮规范**: 三种尺寸、四种类型、图标规则、常用图标映射
  6. **模态框规范**: 四种尺寸、标准结构、间距标准、固定底部实现
  7. **动画规范**: 三种时长 (150ms/200ms/300ms)、缓动函数建议
  8. **响应式设计**: 断点、移动端调整
  9. **圆角系统**: sm/md/lg/xl (6px/8px/12px/16px)
  10. **阴影系统**: sm/md/lg/xl (四级阴影)
  11. **最佳实践**: CSS变量使用、语义化类名、一致性保持、可访问性
  12. **维护指南**: 变量修改流程、新组件添加规范

### 🔧 技术改进

#### 代码可维护性提升
- **消除重复代码**: CSS中有4处 `.modal-footer` 定义，现在全部使用统一的CSS变量
- **提高可扩展性**: 新增组件可直接使用标准化变量，无需定义新样式
- **降低维护成本**: 修改设计只需在 `:root` 中调整变量值

#### 响应式优化
- **移动端适配**: 为移动端单独定义footer padding (8px 16px 5px)
- **自动适配**: 模态框宽度使用 max-width 确保在小屏幕自动缩放

### 📝 文档更新
- 新增 `docs/DESIGN_GUIDE.md` - 完整的前端设计规范文档
- 更新 `CHANGELOG.md` - 记录本次标准化工作

### 💡 设计理念
- **标准化优先**: 所有UI组件遵循统一的设计标记系统
- **可维护性**: 使用CSS变量提高代码可维护性
- **一致性**: 确保整个应用的视觉和交互一致性
- **文档化**: 完整的设计规范文档，方便团队协作

---

## [v0.3.11] - 2025-11-28

### 🎨 UI/UX 优化

#### 封面预览界面优化 🖼️
- **关闭按钮布局修复**: 将封面预览的关闭按钮移至控制栏内
  - 与缩放、重置、放大、新窗口打开等按钮对齐在同一行
  - 使用 `margin-left: auto` 将关闭按钮推至右侧
  - 改进视觉层次和操作流畅性

#### 按钮样式统一化 🔘
- **统一按钮尺寸**: 所有控制按钮统一为 40px × 40px
- **统一圆角**: 使用 `var(--radius-md)` (8px) 圆角
- **统一交互效果**:
  - Hover 状态: 向上移动 2px + 阴影效果
  - 过渡动画: 统一使用 `0.2s ease`
  - 阴影增强: `0 4px 12px rgba(color, 0.2)`

#### 颜色方案优化 🎨
- **缩放按钮**: 
  - 背景: `rgba(59, 130, 246, 0.15)` (主色调蓝色)
  - 边框: `rgba(59, 130, 246, 0.3)`
  - Hover: `rgba(59, 130, 246, 0.25)`
- **关闭按钮**:
  - 背景: `rgba(239, 68, 68, 0.15)` (危险色红色)
  - 边框: `rgba(239, 68, 68, 0.3)`
  - Hover: `rgba(239, 68, 68, 0.25)`
- **控制栏容器**:
  - 背景: `rgba(30, 41, 59, 0.9)` (玻璃拟态)
  - 模糊效果: `blur(12px)`
  - 边框: `1px solid var(--glass-border)`

### 🔧 技术改进

#### HTML 结构优化
- 将 `.btn-close-zoom` 移入 `.zoom-controls` 容器
- 使用 Font Awesome 图标替代纯文本 "×"
- 改进 Flexbox 布局，确保按钮对齐

#### CSS 样式重构
- 移除 `position: absolute` 定位
- 使用 Flexbox 自动布局
- 统一按钮尺寸和间距
- 优化容器 padding 和 margin

### 📝 文档更新
- 更新 `CHANGELOG.md` - 记录本次优化
- 更新 `DESIGN_SYSTEM.md` - 添加封面预览按钮规范

### 💡 设计理念
- **一致性**: 所有按钮遵循统一的设计系统
- **清晰性**: 视觉层次分明，操作直观
- **美观性**: 现代化玻璃拟态设计，精致专业
- **高效性**: 减少视觉干扰，提升操作效率

---

## [v0.3.10] - 2025-11-27

### ✨ 新增功能

#### 1. 分析中断功能 🛑
- **强制停止分析**: 在单本分析或顺序处理时，可随时点击按钮中止正在进行的分析
- **智能状态切换**: 
  - 正常状态：蓝色，显示"开始信息及目录分析"
  - 分析中状态：橙色脉冲动画，显示"停止分析"
- **技术实现**: 使用 `AbortController` API 优雅中断fetch请求
- **用户体验**: 即时响应，点击即停止，状态自动恢复

### 📐 设计系统建立

#### 完整设计规范文档
- **文档位置**: `docs/DESIGN_SYSTEM.md` (约600行)
- **内容包括**:
  - 设计原则（一致性、清晰性、高效性、美观性）
  - 颜色系统（主色调、辅助色、语义色、背景色、文字颜色）
  - 间距系统（xs/sm/md/lg/xl）
  - 圆角系统（sm/md/lg/xl）
  - 阴影系统（sm/md/lg/xl）
  - 动画时长（fast/base/slow）
  - 组件规范（按钮、表单、模态窗口、标签页、表格等）
  - 图标规范（Font Awesome使用指南）
  - 响应式规则
  - 组件使用清单

### 🎨 UI统一优化

#### CSS变量系统扩展
- **新增40+个CSS变量**:
  - 背景色变量
  - 主色调及hover状态
  - 辅助色及hover状态（success、warning、danger等）
  - 文字颜色层级（main、secondary、muted、disabled）
  - 标准圆角（sm/md/lg/xl）
  - 标准阴影（sm/md/lg/xl）
  - 标准间距（xs/sm/md/lg/xl）
  - 标准动画时长（fast/base/slow）

#### 按钮系统统一
- **全面重构按钮样式**:
  - `.btn-primary` - 主要操作（蓝色）
  - `.btn-secondary` - 次要操作（灰色透明）
  - `.btn-success` - 成功/确认（绿色）  
  - `.btn-danger` - 危险/删除（红色）
  - `.btn-icon` - 图标按钮（透明）
  - `.btn-icon.btn-labeled` - 带标签图标按钮
  - `.btn-sm` - 小尺寸按钮
  - `.btn-close` - 关闭按钮
- **统一特性**:
  - 所有按钮hover效果（向上移动1px + 阴影）
  - 所有按钮active效果
  - 统一的padding、border-radius、font-size
  - 统一的过渡动画时长

#### 表单系统统一
- **统一所有表单组件样式**:
  - 输入框（text、number、password、email、url）
  - 文本域（textarea）
  - 下拉框（select，带自定义SVG箭头）
  - 标签（label）
  - 表单组（.form-group）
  - 表单行（.form-row，两列布局）
  - 帮助文本（.help-text）
- **Focus状态**: 蓝色边框 + 蓝色阴影光晕

#### 模态窗口统一
- **标准化结构**: header + body + footer
- **统一样式**:
  - 玻璃拟态背景 + 模糊效果
  - 标题栏：图标+标题+关闭按钮，底部边框分隔
  - 主体区：可滚动内容
  - 底栏：右对齐操作按钮组

#### 标签页系统统一
- **统一组件**:
  - 标签栏容器（.settings-tabs、.ai-tabs）
  - 标签按钮（.tab-btn）
  - 激活状态（蓝色文字 + 底部蓝色边条）
  - 状态指示点（.status-dot，绿色发光表示激活）

#### 表格系统统一
- **统一特性**:
  - 表头：蓝色背景、sticky定位、白色字体
  - 单元格：统一padding、底部细线分隔
  - Hover效果：行背景轻微变亮
  - 表格容器：固定高度、可滚动、圆角边框

### 🛠️ 工具类添加

#### 文字工具类
- `.text-muted`、`.text-primary`、`.text-success`、`.text-warning`、`.text-danger`
- `.font-semibold`、`.font-medium`

#### 间距工具类
- `margin-bottom`: `.mb-xs/sm/md/lg/xl`
- `margin-top`: `.mt-xs/sm/md/lg/xl`

### 🔧 其他优化

- ✓ 自定义滚动条样式（8px宽，圆角，半透明）
- ✓ 加载旋转动画组件
- ✓ 进度条组件
- ✓ 信息/警告/成功提示框组件
- ✓ 响应式优化（移动端模态窗口全屏显示）

### 📝 文档更新

- 新增 `docs/DESIGN_SYSTEM.md` - 完整设计系统规范（约600行）
- 新增 `docs/UI_UNIFICATION_PLAN.md` - UI统一优化计划
- 新增 `docs/releases/v0.3.10.md` - 详细版本说明

### 📊 代码统计

- CSS新增：约480行
- 新增CSS变量：40+个
- 新增/优化组件：15+个
- 新增工具类：20+个

---

## [v0.3.9] - 2025-11-27

### ✨ 新增功能

#### 1. 批量处理增强 🚀
- **AI 简介预览**: 在批量处理列表中，每本书的文件名后新增绿色文档图标 📄
  - 悬停图标可查看 AI 生成的完整图书简介
  - 方便用户在执行转移前快速了解图书内容
- **智能重复检测**: 优化重复图书检测逻辑
  - 采用智能书名提取算法（去除副标题、标点等）
  - 确保批量模式下的重复检测与单本模式完全一致
  - 提高重复检测的准确率

#### 2. 界面体验优化 🎨
- **全局悬浮提示框 (Tooltip)**: 
  - 重构提示框实现，使用全局定位策略
  - 彻底解决提示框被表格边缘截断的问题
  - 智能边缘检测，自动调整显示位置
  - 统一 AI 简介（深色）和重复警告（黄色）的视觉风格
- **重复警告优化**: 
  - 增加提示框宽度，支持多行显示
  - 优化排版，清晰展示重复文件的路径信息

### 🔧 逻辑改进

- **AI 输出控制**: 
  - 修复后端逻辑，确保 `summary_max_chars` 配置项正确生效
  - 统一单本分析、批量分析和自动分析的提示词生成逻辑
  - 确保用户设定的字数限制（如 200 字）被严格执行

### 🐛 Bug 修复

- **批量分析一致性**: 修复批量分析时重复检测逻辑与单本分析不一致的问题
- **UI 截断**: 修复批量处理列表中长文本提示框被容器裁剪的问题

### 📝 文档更新
- 新增 `docs/releases/v0.3.9.md` - 详细的版本发布说明

---

## [v0.3.8] - 2025-11-27

### ✨ 新增功能

#### 1. 批量处理弹窗全面重构 🔄

**界面优化**
- **弹窗尺寸增加50%**: 宽度从800px增加到1200px，高度从80vh增加到85vh
- **视觉风格统一**: 表头使用蓝色主题色，与主界面风格一致
- **表格优化**: 容器高度从300px增加到400px，列宽优化为 30% / 45% / 25%

**多路径选择**
- **下拉选择框**: 将"建议目标"列从文本输入框改为`<select>`下拉框
- **显示所有推荐**: 支持显示和选择AI推荐的多个路径
- **默认选择**: 自动选中第一个推荐路径
- **智能切换**: 选择路径时自动将状态从"跳过"切换到"移动"

**重名检测与警告**
- **自动检测**: 批量分析时自动检测目标目录中的重复图书
- **警告图标**: 显示黄色警告图标 ⚠️
- **详细信息**: 悬停显示tooltip，展示重复文件的完整路径
- **API集成**: 调用 `/api/find_similar` 接口进行重名检测

**操作按钮重构**
- **移除"移动"按钮**: 简化操作流程
- **新增"跳过"按钮**: 
  - 支持切换状态（跳过 ↔ 取消跳过）
  - 图标和文字动态变化
  - 跳过状态下整行变灰、删除线、下拉框禁用
- **新增"删除"按钮**: 
  - 从批量处理列表中移除（不物理删除文件）
  - 红色系样式，带垃圾桶图标
  - 操作前显示确认对话框

**全局操作优化**
- **新增"取消"按钮**: 
  - 关闭弹窗并重置所有状态
  - 清空 `batchPlan` 数据
- **"确认并执行"优化**: 
  - 批量处理所有未跳过的记录
  - 读取下拉框中选定的最终路径
  - 传递元数据和简介到后端

**详细文档**: `docs/BATCH_PROCESS_REFACTOR.md`

#### 2. 图书简介字数可配置化 📝

**配置位置**
- AI配置 → 内容与搜索控制 → AI输出控制（第一项）

**配置功能**
- **配置项**: 图书简介字数限制（汉字）
- **可调范围**: 50-500字
- **默认值**: 100字
- **输入验证**: HTML5 number input，自动限制范围

**技术实现**
- **前端**: 
  - 新增配置输入框 `ctrl-summary-max-chars`
  - 更新配置加载、保存和重置逻辑
- **后端**: 
  - 在默认AI配置中添加 `summary_max_chars` 字段
  - 更新 `get_common_prompt()` 从配置读取字数限制
  - 更新 `get_unified_analysis()` 从配置读取字数限制
- **持久化**: 配置保存到用户配置文件 `~/.book_organizer_config.json`

**应用范围**
- 单本书分析
- 批量处理
- 所有AI分析场景

**详细文档**: `docs/SUMMARY_CONFIG.md`

### 🔧 优化改进

#### 批量处理
- 优化日志显示和进度条样式
- 改进错误处理和用户反馈
- 添加悬停效果和过渡动画
- 优化按钮布局和间距

#### AI配置界面
- 在"内容与搜索控制"标签页新增"AI输出控制"配置块
- 优化配置项布局和说明文字
- 改进配置加载、保存和重置逻辑

#### 代码质量
- 重构批量处理相关函数（`renderBatchReview`, `updateRowStatus`, `startBatchAnalysis`）
- 提高代码可维护性和可读性
- 优化函数职责划分

### 🐛 Bug 修复

- **批量处理**: 修复列表项渲染的bug
- **API调用**: 修正`find_similar`接口参数不一致问题（`title` → `query`）
- **UI更新**: 修复跳过状态下UI更新不正确的问题
- **状态管理**: 修复取消按钮的状态重置逻辑

### 📝 技术细节

#### 修改的文件
1. `static/index.html` - 批量处理弹窗HTML结构、AI配置界面
2. `static/style.css` - 批量处理样式（新增240行CSS代码）
3. `static/app.js` - 批量处理逻辑函数
4. `static/ai_config.js` - AI配置管理逻辑
5. `src/book_organizer.py` - 默认AI配置、提示词生成逻辑

#### 新增的文件
1. `docs/BATCH_PROCESS_REFACTOR.md` - 批量处理重构完整文档
2. `docs/SUMMARY_CONFIG.md` - 图书简介配置化文档

#### 新增CSS类
- `.batch-modal-content` - 批量处理弹窗样式
- `.filename-cell` - 文件名单元格
- `.duplicate-warning` - 重名警告图标
- `.tooltip` - 提示框
- `.target-select` - 目标路径下拉框
- `.action-buttons-group` - 操作按钮组
- `.btn-skip.active` - 激活状态的跳过按钮
- `.skipped` - 跳过状态的行

### 🧪 测试建议

#### 批量处理测试
1. 测试弹窗尺寸和响应式布局
2. 测试多路径下拉选择功能
3. 测试重名检测和警告显示
4. 测试跳过/删除按钮功能
5. 测试取消按钮和状态重置
6. 测试批量执行逻辑

#### 图书简介配置测试
1. 测试配置保存和加载
2. 测试不同字数限制下的AI输出
3. 测试边界值（50字、500字）
4. 测试默认值恢复功能
5. 测试配置持久化

---

## [v0.3.7] - 2025-11-26

### ✨ 新增功能

#### 内容与搜索控制可配置模块 ⚙️
- **AI 配置第5个标签页**: 新增"内容与搜索控制"配置模块
  - 位置：AI 配置弹窗 → 第5个标签页
  - 顶部状态指示器新增第5个绿点
  - 实现"非空即绿"状态灯逻辑
  
- **原始读取限制配置**:
  - PDF 最大预读取页数 (默认: 10页)
  - EPUB 最大预读取章节数 (默认: 10章)
  - 原始扫描字符总上限 (默认: 3000字符)
  
- **文本提取策略配置**:
  - 标准模式投喂字数 (默认: 1500字符) - 不开启搜索时使用
  - 搜索模式投喂字数 (默认: 800字符) - 开启搜索时使用
  - 智能截取开关 (默认: 启用) - 掐头去尾策略
  - 头部保留字符数 (默认: 500字符)
  - 尾部保留字符数 (自动计算)
  
- **搜索参数控制**:
  - 引用搜索结果条数 (默认: 3条，范围: 1-10)
  - 滑块控件实时显示

### 🔧 后端重构

#### 配置结构扩展
- 在 `get_default_ai_config()` 中新增 `content_and_search_control` 模块
- 包含10个可配置参数，所有参数支持动态配置
- 完整的默认值定义，确保向后兼容

#### 核心函数重构
1. **`extract_core_content()`**
   - 从配置动态读取所有提取参数
   - 实现防御性编程：配置无效时自动回退到安全默认值
   - 参数验证：确保所有值为正数
   - 配置异常不会导致主流程崩溃
   
2. **`identify_book_metadata()`**
   - 根据 `online_search_enabled` 状态动态选择提取字数
   - 场景A（无搜索）：使用 `standard_mode_chars`
   - 场景B（有搜索）：使用 `search_mode_chars`
   - 异常时回退到硬编码默认值
   
3. **`search_book_online()`**
   - 从配置读取 `search_result_count`
   - 自动限制在 1-10 范围内
   - 防御性默认值处理

### 🎨 前端实现

#### HTML 改进
- 新增第5个标签页及完整的配置表单
- 3个配置区域：原始读取限制、文本提取策略、搜索参数控制
- 滑块控件用于搜索结果数量选择
- 帮助文本详细说明每个参数的作用

#### CSS 样式
- 新增 `.config-section` 配置区域样式
- 新增 `.form-row` 双列表单布局
- 新增 `.help-text` 帮助文本样式
- 新增 `.range-input-group` 范围控件样式
- 与现有UI风格完全一致

#### JavaScript 功能
- 修改 `updateAIStatusIndicators()` 支持第5个标签状态更新
- 修改 `switchAITab()` 支持 `content-search` 标签切换
- 修改 `populateAIConfigUI()` 填充新配置项
- 新增 `saveContentSearchControl()` 保存配置到服务器
- 新增 `resetContentSearchControl()` 恢复默认值
- 新增 `updateSearchCountDisplay()` 更新显示文本

### 💡 关键特性

#### 1. 场景分支判断
严格按照用户需求实现两种场景：
- **场景A (单书处理未开启搜索)**：系统读取 `standard_mode_chars` (默认1500字符)
- **场景B (单书处理手动开启搜索)**：系统读取 `search_mode_chars` (默认800字符) + 引用 N 条搜索结果

#### 2. 防御性编程
- 所有配置读取都包含 try-except 块
- 配置无效或缺失时自动回退到硬编码的安全默认值
- 配置模块异常绝对不会导致图书识别主流程崩溃
- 参数范围验证（如：搜索结果1-10条）

#### 3. 向后兼容
- 对于未配置的历史环境，自动加载并使用默认值
- 无需用户手动迁移配置
- 系统平滑升级，用户无感知

#### 4. 状态指示灯逻辑
- 遵循"非空即绿"原则
- 只要配置存在有效数据（无论是用户修改过的，还是系统初始化的默认值），指示灯即显示为绿色
- 与其他4个标签页保持一致的视觉风格

### 📖 文档更新
- 新增 `docs/CONTENT_SEARCH_CONTROL_IMPLEMENTATION.md` - 完整实现总结
- 新增 `docs/CONTENT_SEARCH_CONTROL_TEST_GUIDE.md` - 详细测试指南
- 包含配置结构、重构函数、UI实现和关键特性说明

### ✅ 测试验证
- ✅ Python 代码语法检查通过
- ✅ 所有函数逻辑完成重构
- ✅ UI/UX 完全集成
- ✅ 配置保存和加载功能正常
- ✅ 默认值回退机制正常
- ✅ 状态指示器正确显示

### 🔨 技术细节
- **配置键名**: `content_and_search_control`
- **前端标签ID**: `ai-tab-content-search`
- **状态指示器ID**: `ai-status-content-search`
- **配置API**: 通过现有的 `/api/ai_config` 端点保存和加载

---

## [v0.3.6] - 2025-11-25

### ✨ 新增功能

#### PDF 完整支持 📄
- **PDF 封面提取**: 自动从PDF第一页生成封面图片
  - 使用 PyMuPDF (fitz) 库渲染第一页
  - 150 DPI 高清渲染，PNG 格式
  - 在图书列表和详情页正常显示
  
- **PDF 元数据读取增强**: 完整支持PDF元数据读取
  - 优先使用 PyMuPDF 读取（更强大、更准确）
  - 降级支持 PyPDF2（兼容性）
  - 支持字段：title, author, tags, publisher, series
  - 自动识别 keywords 中的丛书信息（"丛书:"前缀）
  
- **PDF 元数据写入**: 支持将元数据写入PDF文件
  - 使用 PyMuPDF 增量保存
  - 支持字段：title, author, publisher, tags, series
  - 自动备份和恢复机制
  - 字段映射：
    - publisher → creator
    - tags → subject
    - series → keywords（带"丛书:"前缀）

#### [Unreleased]
### Added
- **并行分析优化**: "识别信息" (单本) 与 "批量处理" 现已支持增强简介与元数据分析的并行执行，显著提升响应速度。
- **增强简介解析优化**: 采用更稳健的关键词与正则匹配逻辑，完美解决简介内容冗余、重复标题及多余标点符号的问题。
- **界面美化**: 统一了增强简介区域的 CSS 样式，去除冗余代码，优化了夜间模式下的视觉体验。

### Fixed
- **数据持久化修复**: 修复了“保存更改”时数据库未能正确保存增强简介的问题，确保数据在不同操作（如移动、重命名）间的完整性。
- **代码规范**: 清理了 server.py 和 CSS 中的冗余代码与注释。
#### Beta 功能优化 🔧
- **元数据写入分离**: 将"元数据写入 (EPUB/PDF)"分成两个独立开关
  - ✅ EPUB 元数据写入（独立控制）
  - ✅ PDF 元数据写入（独立控制）
  - 位置：系统设置 → 测试功能 (Beta)
  - 配置键：`enable_metadata_write_epub`, `enable_metadata_write_pdf`

### 🎨 用户体验改进

#### 封面查看优化
- **点击背景关闭弹窗**: 除了点击 X 按钮外，现在也可以点击弹窗外部区域关闭放大图片
- **更符合用户习惯**: 减少操作步骤，提升使用效率

### 🔧 技术实现

#### 前端改进
- 恢复元数据编辑区域为原始设计（只保留"AI 识别信息"按钮）
- 在 Beta 功能区域添加两个独立的元数据写入开关
- 更新 Beta 配置的加载和保存逻辑
- 在封面缩放模态窗口添加背景点击事件

#### 后端改进
- 扩展 `get_cover_image()` 函数支持 PDF
  - 使用 PyMuPDF 渲染第一页为图片
  - PNG 格式，150 DPI
  
- 增强 `extract_metadata()` 函数
  - 优先使用 PyMuPDF 读取 PDF 元数据
  - 支持 tags, publisher, series 字段提取
  - 自动识别 keywords 中的丛书信息
  
- 新增 `update_pdf_metadata()` 函数
  - 使用 PyMuPDF 写入元数据
  - 增量保存模式
  - 完整的备份和恢复机制
  
- 更新 `rename_only` 端点
  - 根据文件类型使用不同的 beta 配置
  - EPUB 使用 `enable_metadata_write_epub`
  - PDF 使用 `enable_metadata_write_pdf`

### 📖 文档更新
- 新增 `releases/RELEASE_v0.3.6.md` - 详细的版本说明
- 包含完整的功能说明和测试结果

### ✅ 测试验证
- ✅ PDF 封面成功提取和显示
- ✅ PDF 元数据完整读取（所有字段）
- ✅ PDF 元数据成功写入
- ✅ Beta 功能正确分离
- ✅ 点击背景关闭弹窗功能正常

### 🔨 依赖更新
- PyMuPDF (fitz): v1.26.6
  - 用于 PDF 封面提取和元数据读写
  - 已包含在 requirements.txt

---

## [v0.3.5] - 2025-11-25

### ✨ 新增功能

#### 图书转移记录功能 📝
- **转移记录目录配置**: 在"基本设置 → 通用设置"中新增"转移记录目录"配置项
  - 可选配置，留空则不记录
  - 支持通过浏览按钮选择目录
  
- **自动记录转移历史**: 完成图书转移时，自动在转移记录目录生成 `图书转移记录.md` 文件
  - ✅ **单本手动转移**: 完成一条写入一条
  - ✅ **批量转移**: 点击转移后按顺序批量写入
  
- **记录内容**:
  - 📊 **序号**: 自动递增的记录序号
  - ⏰ **转移时间**: 精确到秒的时间戳
  - 📁 **文件信息**: 原文件名和新文件名
  - 📍 **目标目录**: 转移到的分类目录
  - 📚 **图书基本信息**: 作者、出版社、丛书/系列、标签
  - 📖 **图书简介**: AI 生成的图书介绍（界面显示的那段话）
  
- **美观排版**:
  - Markdown 格式，易于阅读
  - 不同图书之间用分隔符隔开
  - 自动生成文件头部说明

#### 记录文件示例
```markdown
# 图书转移记录

> 本文件记录了所有通过 Book Organizer 完成的图书转移操作

## 1. 时代的喧嚣

**转移时间**: 2025-11-25 16:30:45  
**原文件名**: `时代的喧嚣 - [俄] 曼德尔施塔姆.epub`  
**新文件名**: `时代的喧嚣 - [俄] 曼德尔施塔姆.epub`  
**转移到目录**: `文学/外国文学/俄罗斯文学`

### 图书基本信息

**作者**: [俄] 曼德尔施塔姆  
**出版社**: 上海译文出版社  
**标签**: 诗歌, 俄罗斯文学, 现代主义

### 图书简介

这是一本收录了俄罗斯诗人曼德尔施塔姆代表作的诗集...

---
```

### 🔧 技术实现

#### 前端改进
- 添加 `currentBookSummary` 全局变量存储当前书籍简介
- 在 `analyzeBook` 函数中保存 summary
- 在 `moveBook` 函数中传递 summary 到后端
- 批量处理中保存和传递每本书的 summary
- 切换书籍时自动清空 summary
- 新增转移记录目录的配置保存和加载逻辑

#### 后端改进
- 新增 `write_transfer_log()` 函数处理记录写入
- 修改 `rename_and_move_book()` 函数，在转移成功后调用记录功能
- 更新 API 模型，添加 `transfer_log_dir` 和 `summary` 字段
- 智能序号管理，自动识别最后一条记录的序号

### 📖 使用说明

1. **配置转移记录目录**:
   - 打开"设置" → "通用设置"
   - 填写"转移记录目录"或点击"浏览"选择
   - 留空则禁用记录功能

2. **自动记录**:
   - 转移图书时自动记录
   - 无需额外操作
   - 可随时查看 `图书转移记录.md` 文件

3. **记录管理**:
   - 记录以追加方式写入，不会覆盖
   - 定期备份记录文件
   - 可手动编辑或删除记录

### 💡 特性

- ✅ 非侵入式设计，不影响主要逻辑
- ✅ 可选功能，留空配置即可关闭
- ✅ 支持单本和批量转移
- ✅ Markdown 格式，易于阅读和编辑
- ✅ 完整的元数据和简介记录
- ✅ 自动化处理，无需手动干预

---

## [v0.3.4] - 2025-11-25

### 🐛 Bug 修复

#### EPUB 元数据读取和写入增强 📚
- **修复**: 完善了 EPUB 文件的元数据读取和写入功能
- **新增支持字段**:
  - ✅ **Tags (标签)**: 现在可以正确读取和写入 DC:subject 字段
  - ✅ **Series (丛书)**: 现在可以正确读取和写入 Calibre 的 series 元数据
- **兼容性**: 与 Calibre 完全兼容，可以正确识别和更新元数据

#### 技术细节
- **读取功能** (`extract_metadata`):
  - 添加了 DC:subject 的读取，将多个 subject 合并为逗号分隔的 tags
  - 添加了 calibre:series 的读取，从 OPF meta 标签中提取丛书信息
  
- **写入功能** (`update_epub_metadata`):
  - 添加了 tags 到 DC:subject 的写入，支持逗号分隔的标签列表
  - 添加了 series 到 calibre:series 的写入，使用 OPF meta 标签格式
  - 自动清除旧数据，避免重复

### 📖 文档更新
- 新增 `docs/technical/metadata-fix-report.md` - 详细的修复报告和测试结果
- 包含完整的测试用例和验证过程

### ✅ 测试验证
- ✅ 成功读取 EPUB 文件的 tags 和 series 字段
- ✅ 成功写入 tags 和 series 到 EPUB 文件
- ✅ 写入的元数据可以被 Calibre 正确识别
- ✅ 所有测试通过

---

## [v0.3.3] - 2025-11-25

### ✨ 功能重构

#### Beta 功能位置调整 🔧
- **移动位置**: 将测试功能从 AI 配置移至主设置界面
- **独立管理**: Beta 功能现在有独立的配置存储
- **更好的可见性**: 在设置中更容易找到和管理

#### 相似图书搜索优化 🔍
- **功能修复**: 修复了 `/api/find_similar` 端点 404 错误
- **优化显示**: 
  - 黄色背景和橙色边框，更醒目
  - 显示在图书基本信息下方
  - 多个匹配时显示数量徽章 (+N)
- **智能搜索**: 自动提取书名核心部分进行匹配

### 🐛 Bug 修复

#### 配置保存问题
- **修复**: Beta 功能开关无法保存
- **原因**: `ConfigUpdate` 模型缺少 `beta_features` 字段
- **解决**: 添加字段定义，现在可以正确保存

#### Tab 切换失效
- **修复**: 点击 Beta 标签没有高亮效果
- **原因**: `switchTab` 函数硬编码了 tab 索引
- **解决**: 改为动态识别 tab

#### 配置缓存问题
- **修复**: 重新打开设置时显示旧配置
- **原因**: 浏览器缓存了 GET 请求
- **解决**: 添加时间戳参数防止缓存

#### 启动脚本错误
- **修复**: `start_web.sh` 无法找到模块
- **原因**: Uvicorn 直接加载时路径问题
- **解决**: 改为直接运行 `server.py`

### 🔧 技术改进

- **EPUB 元数据写入**: 改进了标题和作者的更新逻辑
- **开发模式**: 新增 `run_dev.sh` 脚本，显示完整日志
- **代码清理**: 移除了调试日志，优化了代码结构

### 📖 文档更新

- 新增 `docs/releases/v0.3.3.md` - 详细的版本说明
- 更新 `docs/README.md` - 文档索引
- 更新 `docs/releases/README.md` - 版本历史

---

## [v0.3.2] - 2025-11-23

### ⚡ 性能优化

#### 动态 Token 策略 📉
- **智能调整**: 根据是否启用在线搜索，动态调整内容提取量
- **默认模式**: 提取前 1500 字符（原 3000），减少约 50% Token 消耗
- **搜索模式**: 提取前 800 字符，利用搜索结果补充信息，减少约 70% Token 消耗
- **效果**: 显著降低 API 成本，提升识别速度，同时保持高准确率

### 📖 文档更新
- 新增 `docs/technical/optimization-token-strategy.md` - 详细的优化报告

---

## [v0.3.2] - 2025-11-23

### ✨ 新增功能

#### 扩展文件格式支持 📚
- **新增支持格式**: 添加 13 种主流电子书和文档格式
  - Kindle 格式: AZW
  - 学术文献: DJVU
  - 电子书格式: FB2, LIT, CHM
  - 漫画格式: CBR, CBZ, CB7, CBT
  - 文档格式: RTF, DOC, DOCX

- **智能识别**: 对于无法提取元数据的格式，通过文件名进行 AI 识别
- **分类支持**: 所有格式都支持 AI 分类和文件移动

### 📖 文档更新
- 新增 `docs/user/supported-formats.md` - 详细的格式支持说明
- 更新 README.md - 完善支持格式列表
- 更新用户文档索引

### 🔧 技术改进
- 扩展 `valid_exts` 列表，支持更多文件扩展名
- 优化文件识别逻辑
- 添加详细的格式支持文档

---

## [v0.3.1] - 2025-11-23

### ✨ 新增功能

#### 文件名长度智能截断 📏
- **自动截断**: 确保文件名不超过255字节，兼容macOS和群晖Drive
- **智能策略**: 按优先级截断（多余作者 → 副标题 → 括号内容 → 主标题）
- **透明处理**: 在确认修改或转移时自动执行，用户无感知
- **保留信息**: 优先保留书名和主要作者，删除次要信息

#### 截断策略详解
1. **多作者处理**: 保留前2个作者，其余用"等"代替
   - 示例：`作者1 & 作者2 & 作者3 & 作者4` → `作者1 & 作者2 等`
2. **副标题删除**: 移除冒号或破折号后的内容
   - 示例：`书名：副标题` → `书名`
3. **括号内容删除**: 移除圆括号、方括号内容（保留国别标记）
   - 示例：`书名（版本说明）` → `书名`
4. **主标题截断**: 直接截断并添加"..."
   - 示例：`超长书名...` → `超长书...`

### 🔧 优化改进

#### 后端改进
- 新增 `truncate_filename_smart()` 函数（第644-740行）
- 在 `rename_and_move_book()` 中应用截断（第774行）
- 在 `rename_only()` 中应用截断（第488行）
- 精确的UTF-8字节计算，确保不截断到半个字符

#### 用户体验
- 自动化处理，无需用户干预
- 保持文件名可读性
- 元数据信息完整保留
- 支持手动调整后再次截断

### 📖 文档更新
- 新增 `FILENAME_LENGTH_LIMIT.md` - 详细的功能说明和使用示例
- 包含测试用例和技术参考
- 说明各系统的文件名长度限制

### 🐛 修复问题
- 解决文件名过长导致无法上传到群晖Drive的问题
- 防止文件系统操作失败
- 确保跨平台兼容性

---

## [v0.3.0] - 2025-11-23

### ✨ 新增功能

#### 多作者国别标记优化 🌍
- **新格式**: 每个作者单独标注国别，用 `&` 分隔
  - 示例：`[美] 白德瑞 & 王锐 & [美] 罗伯特S.韦斯特曼`
- **避免重复**: 彻底解决 `[[美]]` 双层括号问题
- **简化界面**: 移除独立的"国家"输入字段
- **国别信息**: 直接包含在作者字段中

#### 外国人名间隔号统一 ·
- **自动替换**: 将 `•`、`●`、`・` 等各种间隔号统一替换为中文间隔号 `·` (U+00B7)
- **后处理机制**: 在 AI 识别结果返回前自动处理
- **确保一致性**: 所有文件名使用统一的间隔号格式
- **示例转换**: `罗伯特•史密斯` → `罗伯特·史密斯`

### 🔧 优化改进

#### AI 提示词优化
- 更新 `author_prompt`: 明确多作者标注规则和间隔号使用规范
- 更新 `filename_prompt`: 提供多作者文件名示例，强调避免双层括号
- 移除单独的"国家"提取要求，简化数据模型

#### 后端改进
- 新增间隔号后处理函数（第625-638行）
- 自动检测并替换各种间隔号符号
- 同时处理作者字段和文件名字段
- 确保输出的一致性和规范性

#### 前端优化
- 移除 `meta-country` 字段的所有引用
- 简化文件名模板处理逻辑
- 更新帮助文档和AI配置说明
- 在作者字段添加格式提示

### 📖 文档更新
- 新增 `MULTI_AUTHOR_SOLUTION.md` - 详细说明解决方案
- 更新用户界面的提示文本
- 完善帮助文档中的示例
- 更新 AI 配置页面的变量说明

### 🐛 修复问题
- 修复多作者时国别标记重复的问题
- 统一外国人名间隔号的显示
- 优化文件名生成的一致性

---

## [v0.2.6] - 2025-12-21

### ✨ 新增功能

#### 工具优化
- **脚本重组**: 将实用工具脚本统一整理至 `scripts/utils/` 目录。
- **重复文件管理**:
  - 增强版去重报告生成器 (`generate_duplicate_report.py`)，支持智能系列识别。
  - 交互式清理工具 (`delete_unchecked_duplicates.py`)，支持批量删除。
  - 文档支持 (`docs/user/utility_tools.md`)。

### 🎨 UI/UX 改进

#### 前端界面
- **Header 按钮优化**: 采用幽灵按钮风格，默认透明背景，悬停显示主题色。
- **CSS 架构**:
  - 全面引入 CSS 变量，统一颜色、字体和圆角。
  - 新增 RGB 变量定义，支持透明度调整。
  - 移除硬编码颜色值，提升可维护性。

---

## [v0.2.5] - 2025-11-23

### ✨ 新增功能

#### 图书信息增强
- **文件详情显示**: 在查看图书详情时，现在会显示文件的实际大小（自动格式化为 KB/MB/GB）和最后修改时间。
- **API 升级**: `/api/books` 接口增加 `size` 和 `mtime` 字段返回。

---

## [v0.2.2] - 2025-11-21

### ✨ 新增功能

#### 构建系统
- **Mac 构建脚本** (`scripts/build_standalone.sh`)
  - 完整的 PyInstaller 构建流程
  - 自动检测和处理图标文件
  - 支持 .icns 和 .png 格式图标
  - 友好的错误提示和进度反馈
  - 自动清理旧构建文件

- **图标转换工具** (`scripts/convert_icon.sh`)
  - 将 PNG 图标转换为 macOS ICNS 格式
  - 自动生成多种尺寸的图标
  - 完整的错误处理

#### 文档
- **完整的中文 README** (`README.md`)
  - 详细的项目介绍
  - 安装和使用指南
  - 多种运行方式说明
  - 配置示例和说明
  - 常见问题解答
  - 安全注意事项
  - 开发指南

- **构建与部署指南** (`docs/BUILD_DEPLOY_GUIDE.md`)
  - Mac 和 Windows 平台构建步骤
  - 完整的测试流程
  - 多种部署方式
  - 常见问题解决方案
  - 版本发布检查清单

### 🔧 优化改进

#### 脚本优化
- **启动脚本** (`scripts/start_web.sh`)
  - 增强的错误处理
  - 自动检测虚拟环境
  - 自动安装缺失依赖
  - 美化的输出信息
  - 中文界面提示

- **快捷方式创建** (`scripts/create_app.sh`)
  - 增强的错误处理
  - 详细的创建过程反馈
  - 成功后的使用指南
  - 中文界面提示

#### 构建流程
- 支持可选图标文件
- 完整的隐藏导入列表
- 支持所有 AI 引擎（Gemini、DeepSeek、Ollama）
- 脚本使用 `set -e` 确保错误时退出
- 详细的错误提示和用户反馈

### 📖 文档更新
- 更新 `PROJECT_STRUCTURE.md` - 添加新脚本和文档说明
- 更新 `REFACTORING_SUMMARY.md` - 添加最新更新内容
- 创建 `CHANGELOG.md` - 版本更新日志

### 🐛 修复问题
- 修复图标文件路径问题
- 优化构建脚本的兼容性
- 改进错误提示的准确性

---

## [v0.2.1] - 2025-11-20

### 🎯 重构优化

#### 目录结构重组
- 创建 `src/` 目录存放源代码
- 创建 `scripts/` 目录存放脚本
- 创建 `docs/` 目录存放文档
- 创建 `data/` 目录存放用户数据
- 创建 `tests/` 目录预留测试

#### 文件移动
- `book_organizer.py` → `src/book_organizer.py`
- `server.py` → `src/server.py`
- 所有脚本移至 `scripts/`
- 所有文档移至 `docs/`
- 配置文件移至 `data/`

#### 更新 .gitignore
- 增强的 Python 相关忽略规则
- 操作系统文件忽略
- IDE 配置文件忽略
- 构建产物忽略
- 用户数据保护

#### 脚本路径更新
- 所有脚本适配新目录结构
- 添加自动导航到项目根目录
- 更新模块导入路径

### 📝 新增文档
- `PROJECT_STRUCTURE.md` - 项目结构说明
- `README.md` - 项目说明文档
- `data/README.md` - 数据目录说明
- `tests/README.md` - 测试说明

---

## [v0.2.4] - 2025-11-22

### ✨ 新增功能

#### 封面查看增强
- **封面放大查看**: 点击图书封面可弹出大图查看窗口
- **缩放控制**: 支持放大、缩小和重置缩放级别
- **高清预览**: 方便查看封面上的标题和备注信息

#### 用户体验优化
- **使用说明**: 新增帮助按钮，提供完整的使用指南
- **状态同步**: 修复 AI 配置状态点在主界面和弹窗间的同步问题
- **重命名保持选中**: 修改文件名后自动保持图书选中状态

### 🐛 修复问题
- **正则表达式错误**: 彻底修复文件名净化时的正则表达式问题
- **文件名修改**: 解决"确认修改图书信息"功能的所有已知问题

### 🔧 优化改进
- **代码质量**: 全面测试和验证核心功能
- **错误处理**: 改进文件重命名的错误提示

---

## [v0.2.3] - 2025-11-22

### ✨ 新增功能

#### 智能元数据与文件名管理
- **自定义文件名模板**: 支持用户自定义文件名生成规则（如 `{title} - [{country}] {author}`）。
- **国家字段支持**: 新增作者国家字段提取与编辑，支持智能处理（如中国自动留空）。
- **实时预览**: 编辑元数据时，文件名预览会根据模板实时更新。
- **智能书名提取**: 优化 AI 提示词，确保提取完整的书名（包含副标题）。
- **单本图书 AI 识别**: 支持对单本图书进行 AI 元数据识别和编辑。
- **智能内容提取**: 仅提取图书前 3000 字进行 AI 分析，提高效率。

#### UI/UX 改进
- **元数据编辑器**: 在主界面集成完整的元数据编辑表单。
- **文件名预览**: 可编辑的文件名预览框，支持手动微调。
- **AI 配置优化**: 改进 AI 配置界面，支持字段提取规则的精细化配置。

### 🔧 优化改进
- **自动重命名逻辑**: 转移图书时自动应用新的文件名规则。
- **构建系统**: 优化构建脚本，确保生成完整的应用程序包。

---

## [v0.2.2] - 2025-11-21

### ✨ 新增功能

#### AI 配置系统
- **AI 配置界面**
  - 核心规则编辑
  - 附加规则管理（CRUD）
  - 历史数据参考配置
  - AI 引擎选择和配置

- **规则优先级**
  - 核心规则优先级最高
  - 启用的附加规则次之
  - 历史记录参考最后

- **AI 优化功能**
  - 使用 AI 优化附加规则
  - 智能建议和改进

#### UI 增强
- **图标和描述**
  - 所有按钮添加彩色图标
  - 添加文字描述提升可读性

- **统计信息**
  - 显示总图书数
  - 显示待处理数量
  - 显示已跳过数量

- **封面预览**
  - EPUB 图书封面提取
  - 缩略图显示
  - 点击查看大图

### 🐛 修复问题
- 修复图书加载失败的 bug
- 优化文件读取性能
- 改进错误处理

### 📖 文档
- `AI_CONFIG_QUICKSTART.md` - AI 配置快速入门
- `AI_CONFIG_IMPLEMENTATION.md` - AI 配置实现说明
- `AI_CONFIG_CHANGES.md` - AI 配置变更记录
- `TESTING_DEPLOYMENT_GUIDE.md` - 测试和部署指南

---

## [v0.1.0] - 初始版本

### ✨ 核心功能
- 图书自动分类
- AI 智能判断
- Web 界面操作
- 多 AI 引擎支持
  - Google Gemini
  - DeepSeek
  - Ollama

### 📚 支持格式
- EPUB
- PDF
- MOBI
- AZW3
- TXT

### 🔧 基础功能
- 源目录和目标目录选择
- 图书列表展示
- 手动移动图书
- 跳过图书处理
- 历史记录保存

---

## 版本说明

### 版本号规则
- **主版本号 (Major)**: 重大架构变更或不兼容更新
- **次版本号 (Minor)**: 新功能添加
- **修订号 (Patch)**: Bug 修复和小优化

### 更新类型标识
- ✨ 新增功能
- 🔧 优化改进
- 🐛 修复问题
- 📖 文档更新
- 🎯 重构优化
- 🔒 安全更新
- ⚡ 性能优化
- 🎨 UI/UX 改进

---

## 下一步计划

### v0.3.0 (计划中)
- [ ] 添加单元测试
- [ ] 添加集成测试
- [ ] 创建 CI/CD 流程
- [ ] 支持更多图书格式
- [ ] 批量操作优化
- [ ] 多语言支持

### v0.4.0 (规划中)
- [ ] 插件系统
- [ ] 自定义分类规则 DSL
- [ ] 图书元数据编辑
- [ ] 云同步功能
- [ ] 移动端支持

---

**维护者**: BookOrganizer Team  
**最后更新**: 2025-11-21
