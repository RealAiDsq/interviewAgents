# 采访稿处理助手 - 开发计划

## 技术栈选择

### 前端技术栈
- **框架**: Vue.js 3 + TypeScript
- **UI组件库**: Element Plus
- **Markdown编辑器**: @vueup/vue-quill 或 mavon-editor
- **文件上传**: vue-upload-component
- **HTTP客户端**: Axios
- **状态管理**: Pinia
- **路由**: Vue Router 4
- **构建工具**: Vite

### 后端技术栈
- **框架**: FastAPI (Python)
- **异步处理**: asyncio + Celery (可选)
- **文档解析**:
- python-docx (Word文档)
- PyPDF2 (PDF读取，如需要)
- python-markdown (Markdown)
- **自然语言处理**:
- jieba (中文分词)
- re (正则表达式)
- **文档生成**:
- python-docx (Word生成)
- weasyprint (PDF生成)
- markdown (Markdown处理)
- **数据库**: SQLite/PostgreSQL (可选，用于日志和配置)
- **Web服务器**: Uvicorn

### 开发工具
- **API文档**: FastAPI自动生成的Swagger UI
- **代码管理**: Git
- **依赖管理**: Poetry (Python) + npm/yarn (Node.js)
- **容器化**: Docker (可选)

## 系统架构设计

### 整体架构
前端 (Vue.js) ←→ API网关 ←→ 后端服务 (FastAPI)
                                ↓
                        文档处理引擎
                                ↓
                        文件存储系统

### 核心模块设计

#### 1. 文档解析服务 (DocumentParser)
- **输入**: 各种格式的文档文件
- **输出**: 结构化的JSON数据
- **核心类**:
- `DocxParser`: Word文档解析器
- `TxtParser`: 文本文件解析器
- `MarkdownParser`: Markdown解析器
- `InterviewParser`: 采访稿结构识别器

#### 2. 语义处理服务 (SemanticProcessor)
- **输入**: 结构化的对话数据
- **输出**: 清理后的对话数据
- **核心类**:
- `FillerWordsRemover`: 口癖清理器
- `PunctuationNormalizer`: 标点规范化
- `ContentOptimizer`: 内容优化器

#### 3. 格式转换服务 (FormatConverter)
- **输入**: 处理后的结构化数据
- **输出**: 各种格式的文档
- **核心类**:
- `MarkdownGenerator`: Markdown生成器
- `WordGenerator`: Word文档生成器
- `PDFGenerator`: PDF生成器

#### 4. 前端组件设计
- **FileUploader**: 文件上传组件
- **ProcessingStepper**: 步骤导航组件
- **MarkdownPreview**: Markdown预览组件
- **ExportPanel**: 导出操作面板

## 开发阶段规划

### 阶段一：基础框架搭建 (1-2周)
- [x] 项目初始化和环境配置
- [ ] 前端基础框架搭建
- [ ] 后端API框架搭建
- [ ] 基础的文件上传功能
- [ ] 简单的前后端通信

### 阶段二：文档解析功能 (2-3周)
- [ ] 实现各种格式文档的解析
- [ ] 采访稿结构识别算法
- [ ] JSON数据结构设计和生成
- [ ] 前端解析结果展示
- [ ] 基础的Markdown预览功能

### 阶段三：语义处理功能 (2-3周)
- [ ] 口癖识别和清理算法
- [ ] 标点符号规范化
- [ ] 批量处理功能
- [ ] 处理进度显示
- [ ] 处理前后对比展示

### 阶段四：导出功能 (1-2周)
- [ ] Markdown导出
- [ ] Word文档生成
- [ ] PDF生成
- [ ] 样式统一和优化
- [ ] 文件下载功能

### 阶段五：界面优化和测试 (1-2周)
- [ ] 响应式界面优化
- [ ] 用户体验改进
- [ ] 错误处理和异常情况
- [ ] 性能优化
- [ ] 全面测试和bug修复

### 阶段六：扩展功能预留 (1周)
- [ ] 插件化架构设计
- [ ] 配置管理系统
- [ ] API文档完善
- [ ] 部署和运维优化

## API接口设计

### 核心接口
POST /api/upload - 文档上传
POST /api/parse - 文档解析
POST /api/process - 语义处理POST /api/export - 导出文档
GET /api/preview - 预览结果

## 数据流设计
1. 文档上传 → 临时存储
2. 文档解析 → JSON结构化数据
3. 语义处理 → 优化后的JSON数据
4. 格式转换 → 目标格式文档
5. 文件下载 → 客户端保存

## 风险评估和缓解策略
- **文档解析准确性**: 多种测试样本验证，用户反馈优化
- **性能问题**: 异步处理，进度显示，分批处理
- **格式兼容性**: 详细测试各种文档格式
- **扩展性**: 模块化设计，接口标准化

## 预计开发周期
**总计**: 8-12周（2-3个月）

根据项目复杂度和团队规模，可以适当调整开发周期和优先级。