# 如何使用

1) 安装依赖

```bash
cd backend
poetry install
# 若处理文件上传需要：确保安装 python-multipart
```

2) 启动服务

```bash
poetry run python src/server.py  # http://localhost:8000
```

3) 健康检查

```bash
curl http://localhost:8000/api/health
```

4) 采访稿解析/处理/导出接口（最小可用）

- 上传并解析：

```bash
curl -F "file=@/path/to/sample.docx" http://localhost:8000/api/upload
```

- 语义处理：

```bash
curl -X POST http://localhost:8000/api/process   -H 'Content-Type: application/json'   -d '{"blocks": [{"id": "1", "speaker": "张三", "content": "额 然后 我觉得可以", "processed": false}]}'
```

- 预览（Markdown）：

```bash
curl -X POST 'http://localhost:8000/api/preview?mode=raw'   -H 'Content-Type: application/json'   -d '{"title":"示例","blocks":[{"id":"1","speaker":"张三","content":"内容","processed":false}]}'
```

- 导出：

```bash
# Markdown
curl -X POST 'http://localhost:8000/api/export?fmt=md'   -H 'Content-Type: application/json'   -d '{"title":"示例","blocks":[{"id":"1","speaker":"张三","content":"内容","processed":false}]}'

# Word（依赖 python-docx）
curl -X POST 'http://localhost:8000/api/export?fmt=docx'   -H 'Content-Type: application/json'   -d '{"title":"示例","blocks":[{"id":"1","speaker":"张三","content":"内容","processed":false}]}' --output export.docx
```

PDF 导出：默认未启用，建议安装 weasyprint 或 wkhtmltopdf 后在 `routes/export.py` 中接入统一 HTML->PDF 管道。

安全提示：`src/config/Settings.py` 中存在硬编码的 API Key，请改为使用环境变量或 `.env` 文件管理，避免泄露。
