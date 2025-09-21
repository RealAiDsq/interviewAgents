# WordLine · 采访稿处理助手（全栈骨架）

本项目依据 `demand.md` 实现了一个可运行的前后端最小版本：
- 后端（FastAPI / Python）：上传与解析（.txt/.md/.doc/.docx）、语义处理、Markdown 预览、导出（Markdown/Word/PDF）。
- 前端（Vite + React + TypeScript）：左侧操作区（上传/处理/导出），右侧实时 Markdown 预览。

==============================
一、各平台安装指南（Windows / macOS / Linux）
==============================

A. 后端运行环境
- Python 3.11+、Poetry 2.x（推荐），或使用 venv + pip 方案
- 必备 Python 包（若用 pip）：fastapi uvicorn python-multipart markdown python-docx mammoth
- .doc → .docx 自动转换可选工具（任装其一）：LibreOffice(soffice) 或 Pandoc
- Markdown → PDF（尽量与前端样式一致，任装其一）：Chrome/Chromium 或 wkhtmltopdf
- 中文字体（推荐）：Noto Sans CJK / Noto Serif CJK

B. 前端运行环境
- Node.js 18+、npm（Vite 5 需要较新的 Node）

-----
Windows（PowerShell）
-----
# 1) 安装 Python 3.11（如未安装）
winget install -e --id Python.Python.3.11

# 2) 安装 Poetry（或使用 venv+pip 见下）
py -3.11 -m pip install --user poetry
# 重新打开终端，确保 %APPDATA%\Python\Python311\Scripts 在 PATH 中

# 3) 安装 Node.js LTS
winget install -e --id OpenJS.NodeJS.LTS

# 4)（可选）安装 LibreOffice 或 Pandoc（用于 .doc → .docx）
winget install -e --id TheDocumentFoundation.LibreOffice
# 或
winget install -e --id JohnMacFarlane.Pandoc

# 5)（可选）安装 Chrome 或 wkhtmltopdf（用于 Markdown → PDF）
winget install -e --id Google.Chrome
# 或
winget install -e --id wkhtmltopdf.wkhtmltopdf

# 6)（可选）安装中文字体 Noto（建议手动下载安装包并安装）

# 7) 启动后端（Poetry 方式）
cd backend
poetry install
poetry run python src/server.py

# 7b) 启动后端（venv + pip 方式）
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install fastapi uvicorn python-multipart markdown python-docx mammoth
python src/server.py

# 8) 启动前端
cd ..\frontend
npm i
npm run dev

# 9) 如需手动指定 Chrome 或 wkhtmltopdf 路径（示例）
$env:CHROME_BIN = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
$env:WKHTMLTOPDF_BIN = "C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe"
cd ..\backend; poetry run python src/server.py

-----
macOS（Homebrew）
-----
# 1) 安装 Python/Poetry（或使用 venv+pip 见下）
brew install python@3.11
curl -sSL https://install.python-poetry.org | python3 -
# 重新打开终端，确保 ~/.local/bin 在 PATH 中

# 2) 安装 Node.js
brew install node@18

# 3)（可选）安装 LibreOffice 或 Pandoc
brew install --cask libreoffice
# 或
brew install pandoc

# 4)（可选）安装 Chrome 或 wkhtmltopdf
brew install --cask google-chrome
# 或
brew install wkhtmltopdf

# 5)（推荐）安装中文字体（Noto Sans CJK）
brew tap homebrew/cask-fonts
brew install --cask font-noto-sans-cjk-sc

# 6) 启动后端（Poetry 方式）
cd backend
poetry install
poetry run python src/server.py

# 6b) 启动后端（venv + pip 方式）
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install fastapi uvicorn python-multipart markdown python-docx mammoth
python src/server.py

# 7) 启动前端
cd ../frontend
npm i
npm run dev

# 8) 如需手动指定 Chrome 或 wkhtmltopdf 路径（示例）
export CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
export WKHTMLTOPDF_BIN="/usr/local/bin/wkhtmltopdf"
cd ../backend; poetry run python src/server.py

-----
Linux（Debian/Ubuntu）
-----
# 1) 安装 Python/Poetry
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3-pip curl
curl -sSL https://install.python-poetry.org | python3 -
# 重新打开终端，确保 ~/.local/bin 在 PATH 中

# 2) 安装 Node.js（简易方式；如需更高版本可用 nvm）
sudo apt-get install -y nodejs npm

# 3)（可选）安装 LibreOffice 或 Pandoc
sudo apt-get install -y libreoffice
# 或
sudo apt-get install -y pandoc

# 4)（可选）安装 Chrome/Chromium 或 wkhtmltopdf
sudo apt-get install -y chromium-browser
# 或
sudo apt-get install -y wkhtmltopdf

# 5)（推荐）安装中文字体
sudo apt-get install -y fonts-noto-cjk

# 6) 启动后端（Poetry 方式）
cd backend
poetry install
poetry run python src/server.py

# 6b) 启动后端（venv + pip 方式）
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install fastapi uvicorn python-multipart markdown python-docx mammoth
python src/server.py

# 7) 启动前端
cd ../frontend
npm i
npm run dev

# 8) 如需手动指定浏览器或 wkhtmltopdf（示例）
export CHROME_BIN=/usr/bin/chromium-browser
export WKHTMLTOPDF_BIN=/usr/bin/wkhtmltopdf
cd ../backend; poetry run python src/server.py

==============================
二、项目结构
==============================

- backend/  Python 后端（FastAPI）
- frontend/ Vite + React 前端
- backend/assets/markdown.css  PDF 导出用样式（与前端 .markdown 对齐）
- demand.md  需求文档

==============================
三、运行与验证
==============================

# 后端启动成功后：
# 健康检查
curl http://localhost:8000/api/health

# PDF 渲染引擎探测（需要 Chrome/Chromium 或 wkhtmltopdf 至少一个）
curl http://localhost:8000/api/export/engines

# 上传并解析（支持 .txt/.md/.docx/.doc）
curl -F "file=@/path/to/sample.docx" http://localhost:8000/api/upload

# 语义处理
a='{"blocks":[{"id":"1","speaker":"张三","content":"额 然后 我觉得可以","processed":false}]}'
curl -X POST http://localhost:8000/api/process -H 'Content-Type: application/json' -d "$a"

# 预览（返回 Markdown）
b='{"title":"示例","blocks":[{"id":"1","speaker":"张三","content":"内容","processed":false}]}'
curl -X POST 'http://localhost:8000/api/preview?mode=raw' -H 'Content-Type: application/json' -d "$b"

# 导出 Markdown
curl -X POST 'http://localhost:8000/api/export?fmt=md' -H 'Content-Type: application/json' -d "$b"

# 导出 Word（python-docx）
curl -X POST 'http://localhost:8000/api/export?fmt=docx' -H 'Content-Type: application/json' -d "$b" --output export.docx

# 直接导出 PDF（Markdown → HTML → PDF，经 Chrome/Chromium 优先，回退 wkhtmltopdf）
curl -X POST 'http://localhost:8000/api/export?fmt=pdf' -H 'Content-Type: application/json' -d "$b" --output export.pdf

# 前端：
# http://localhost:5173 打开页面，上传 .txt/.md/.doc/.docx → 解析 → 处理 → 预览 → 导出

==============================
四、环境变量（可选）
==============================

- SOFFICE_BIN：指定 LibreOffice/soffice 可执行文件，用于 .doc → .docx 转换（上传解析链路）
  - Windows (PowerShell)：$env:SOFFICE_BIN = 'C:\\Program Files\\LibreOffice\\program\\soffice.exe'
  - macOS/Linux：export SOFFICE_BIN=/usr/bin/soffice
- CHROME_BIN：指定 Chrome/Chromium 可执行路径，用于 HTML → PDF（优先使用）
  - Windows：$env:CHROME_BIN = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
  - macOS：export CHROME_BIN='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
  - Linux：export CHROME_BIN=/usr/bin/chromium-browser
- WKHTMLTOPDF_BIN：指定 wkhtmltopdf 可执行路径（HTML → PDF 回退）
  - Windows：$env:WKHTMLTOPDF_BIN = 'C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe'
  - macOS/Linux：export WKHTMLTOPDF_BIN=/usr/local/bin/wkhtmltopdf

==============================
五、常见问题排查
==============================

- “Form data requires \"python-multipart\"”
  - 安装：cd backend && poetry run pip install python-multipart

- 导出 PDF 返回 500
  - 访问 GET /api/export/engines 检查渲染器是否被检测到（chrome/bin 与 wkhtmltopdf/bin）
  - 若未检测到：安装 Chrome/Chromium 或 wkhtmltopdf，并用上述环境变量指定绝对路径
  - 中文显示异常：安装 CJK 字体（Noto Sans CJK / Noto Serif CJK）

- 上传 .doc 或 “把 .doc 改后缀为 .docx” 报错
  - 已内置自动转换：需要系统安装 LibreOffice(soffice) 或 Pandoc，确保在 PATH 或设置 SOFFICE_BIN

==============================
六、已覆盖的需求要点与后续迭代
==============================

- 已覆盖：
  - 文档导入：.txt / .md / .docx / .doc
  - 结构化解析：自动识别“说话人/可选时间戳/内容”，输出 JSON blocks
  - 语义处理：去口癖、标点规范化、基础句式优化（规则可扩展）
  - 实时预览：右侧 Markdown 视图，支持原始/处理后切换
  - 导出：Markdown（内置）、Word（python-docx）、PDF（Chrome/wkhtmltopdf）

- 建议迭代：
  1) 解析鲁棒性：适配更多采访稿体裁（多语种、括注、行内时间码等）
  2) 处理可视化：块内差异高亮（原文 vs 处理后）
  3) 插件化 Pipeline：services 层抽象处理管线，支持自定义规则与模型改写
  4) 导出统一：以 HTML 为中介，一套 CSS 同时出 Word/PDF，风格一致
  5) 会话存储：数据库存储文档与处理版本，支持协作与历史回溯
