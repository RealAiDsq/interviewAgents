from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from src.services.markdowner import blocks_to_markdown

import markdown as mdlib


class ExportRequest(BaseModel):
    blocks: list[Dict[str, Any]]
    title: str | None = None


router = APIRouter(prefix="/export", tags=["export"])


def _docx_bytes_from_markdown(md: str, title: str | None) -> bytes:
    try:
        from docx import Document as DocxDocument  # type: ignore
        from docx.shared import Pt, RGBColor, Inches  # type: ignore
        from docx.oxml.ns import qn  # type: ignore
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"docx 依赖缺失: {e}")

    doc = DocxDocument()
    # 设置默认字体为常见的 CJK 友好字体（若系统未安装，仍可能 fallback）
    try:
        normal = doc.styles["Normal"]
        normal.font.name = "Noto Sans CJK SC"
        normal.font.size = Pt(12)
        # 设置东亚字体，避免中文显示为方框
        normal._element.rPr.rFonts.set(qn('w:eastAsia'), "Noto Sans CJK SC")
        normal.font.color.rgb = RGBColor(0, 0, 0)
    except Exception:
        pass

    for h in ("Heading 1", "Heading 2", "Heading 3"):
        try:
            st = doc.styles[h]
            st.font.name = "Noto Sans CJK SC"
            st._element.rPr.rFonts.set(qn('w:eastAsia'), "Noto Sans CJK SC")
            st.font.color.rgb = RGBColor(0, 0, 0)
        except Exception:
            pass
    # 简单样式：标题 + 段落
    if title:
        doc.add_heading(title, level=0)
    # 段落左边框（近似 Markdown 引用左竖线）
    def set_left_border(paragraph, color_hex: str = "D1D5DB", size: int = 18, space: int = 6):
        try:
            from docx.oxml import OxmlElement  # type: ignore
        except Exception:
            return
        p = paragraph._p
        pPr = p.pPr
        if pPr is None:
            pPr = OxmlElement('w:pPr')
            p.append(pPr)
        pBdr = pPr.find(qn('w:pBdr'))
        if pBdr is None:
            pBdr = OxmlElement('w:pBdr')
            pPr.append(pBdr)
        left = pBdr.find(qn('w:left'))
        if left is None:
            left = OxmlElement('w:left')
            pBdr.append(left)
        left.set(qn('w:val'), 'single')
        left.set(qn('w:sz'), str(size))
        left.set(qn('w:space'), str(space))
        left.set(qn('w:color'), color_hex)

    for line in md.splitlines():
        if line.startswith("### "):
            doc.add_heading(line[4:], level=3)
        elif line.startswith("# "):
            doc.add_heading(line[2:], level=1)
        elif line.startswith(">"):
            # 引用段落：去除前缀 ">" 与空格，使用 Quote 样式
            txt = line.lstrip(">").lstrip()
            paragraph = None
            try:
                paragraph = doc.add_paragraph(txt, style="Quote")
            except Exception:
                paragraph = doc.add_paragraph(txt)
            set_left_border(paragraph)
            try:
                paragraph.paragraph_format.left_indent = Inches(0.15)
            except Exception:
                pass
        elif line.strip():
            doc.add_paragraph(line)
        else:
            doc.add_paragraph("")
    bio = io.BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio.getvalue()


def _which(bin_name: str) -> str:
    p = shutil.which(bin_name)
    return p or ""


def _load_markdown_css(for_pdf: bool = False) -> str:
    # 优先使用 backend/assets/markdown.css；若不存在，使用内置最小样式
    # 同时尝试附加前端 styles.css（确保与页面同类 CSS 一致）
    candidates = [
        Path(__file__).resolve().parent.parent.parent / "assets" / "markdown.css",
        Path(os.getcwd()) / "backend" / "assets" / "markdown.css",
    ]
    # 读取后端与前端 CSS；PDF 场景严格最小化，避免前端变量污染
    be_css = ""
    fe_css = ""
    # backend css
    for p in candidates:
        if p.exists():
            try:
                be_css = p.read_text(encoding="utf-8")
                break
            except Exception:
                pass
    if not for_pdf:
        # 非 PDF：可以附加前端样式，保持同类视觉
        fe_candidates = [
            Path(os.getcwd()) / "frontend" / "src" / "styles.css",
            Path(__file__).resolve().parents[4] / "frontend" / "src" / "styles.css",
        ]
        for fp in fe_candidates:
            if fp.exists():
                try:
                    fe_css = fp.read_text(encoding="utf-8")
                    break
                except Exception:
                    pass
        if be_css or fe_css:
            return (be_css + "\n\n" + fe_css)
    else:
        # PDF：仅使用后端 CSS，并附加静态覆盖，避免变量和复杂布局污染
        css = be_css
        css += (
            "\n/* pdf minimal overrides */\n"
            "body{background:#ffffff !important;}\n"
            ".markdown{background:#ffffff !important;color:#111827;}\n"
            ".markdown blockquote{background:transparent !important;border-left:4px solid #e5e7eb !important;padding-left:12px;margin:12px 0;color:#6b7280;}\n"
            ".markdown blockquote p{margin:6px 0;}\n"
            ".markdown h1{font-size:28pt !important;font-weight:700;margin:0 0 12pt 0;}\n"
        )
        return css
    return (
        ".markdown{font-family: -apple-system,Segoe UI,Roboto,Helvetica,Arial,'Noto Sans CJK SC','Noto Sans CJK',sans-serif; color:#111; line-height:1.6;}\n"
        ".markdown h1,.markdown h2,.markdown h3{margin-top:1.2em;}\n"
        ".markdown p{line-height:1.6;}\n"
        "@page { size: A4; margin: 20mm; }\n"
        "body{margin:0;}\n"
    )


def _markdown_to_html(md_text: str, title: str | None, for_pdf: bool = False) -> str:
    html = mdlib.markdown(md_text, extensions=["extra", "sane_lists", "toc", "tables"])  # gfm 近似
    css = _load_markdown_css(for_pdf=for_pdf)
    title_html = f"<title>{title}</title>" if title else ""
    return (
        f"<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>{title_html}<style>{css}</style></head>"
        f"<body><div class='markdown'>{html}</div></body></html>"
    )


def _html_to_pdf_via_wkhtmltopdf(html: str) -> bytes:
    exe = os.getenv("WKHTMLTOPDF_BIN") or _which("wkhtmltopdf")
    if not exe:
        raise HTTPException(status_code=500, detail="未找到 wkhtmltopdf，可设置环境变量 WKHTMLTOPDF_BIN 或安装系统包。")
    with tempfile.TemporaryDirectory(prefix="wordline_pdf_") as td:
        in_path = os.path.join(td, "in.html")
        out_path = os.path.join(td, "out.pdf")
        Path(in_path).write_text(html, encoding="utf-8")
        try:
            subprocess.run([
                exe,
                "-s", "A4",
                "--margin-top", "20mm",
                "--margin-bottom", "20mm",
                "--margin-left", "20mm",
                "--margin-right", "20mm",
                "--disable-smart-shrinking",
                in_path,
                out_path
            ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"wkhtmltopdf 失败: {e}")
        if not os.path.exists(out_path):
            raise HTTPException(status_code=500, detail="wkhtmltopdf 未生成 PDF")
        return Path(out_path).read_bytes()


def _html_to_pdf_via_chrome(html: str) -> bytes:
    # 支持常见 chrome/chromium 名称与环境变量 CHROME_BIN
    chrome = (
        os.getenv("CHROME_BIN")
        or _which("google-chrome-stable")
        or _which("google-chrome")
        or _which("chromium-browser")
        or _which("chromium")
    )
    if not chrome:
        raise HTTPException(status_code=500, detail="未找到 Chrome/Chromium，可设置 CHROME_BIN 或安装浏览器。")
    with tempfile.TemporaryDirectory(prefix="wordline_pdf_") as td:
        in_path = os.path.join(td, "in.html")
        out_path = os.path.join(td, "out.pdf")
        Path(in_path).write_text(html, encoding="utf-8")
        url = f"file://{in_path}"
        try:
            subprocess.run([
                chrome,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                f"--print-to-pdf={out_path}",
                url,
            ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"Chrome headless 失败: {e}")
        if not os.path.exists(out_path):
            raise HTTPException(status_code=500, detail="Chrome 未生成 PDF")
        return Path(out_path).read_bytes()


def _detect_engines() -> dict:
    chrome = (
        os.getenv("CHROME_BIN")
        or _which("google-chrome-stable")
        or _which("google-chrome")
        or _which("chromium-browser")
        or _which("chromium")
        or ""
    )
    wk = os.getenv("WKHTMLTOPDF_BIN") or _which("wkhtmltopdf") or ""
    css_candidates = [
        Path(__file__).resolve().parent.parent.parent / "assets" / "markdown.css",
        Path(os.getcwd()) / "backend" / "assets" / "markdown.css",
    ]
    css_found = ""
    for p in css_candidates:
        if p.exists():
            css_found = str(p)
            break
    return {
        "chrome": {"found": bool(chrome), "bin": chrome},
        "wkhtmltopdf": {"found": bool(wk), "bin": wk},
        "css": {"found": bool(css_found), "path": css_found},
    }


@router.get("/engines")
def engines():
    return _detect_engines()


@router.post("")
def export(req: ExportRequest, fmt: str = Query(pattern=r"^(md|docx|pdf)$")):
    fmt = fmt.lower()
    md = blocks_to_markdown(req.blocks, title=req.title)

    if fmt == "md":
        return PlainTextResponse(content=md, media_type="text/markdown")

    if fmt == "docx":
        data = _docx_bytes_from_markdown(md, req.title)
        bio = io.BytesIO(data)
        return StreamingResponse(
            bio,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": 'attachment; filename="export.docx"'
            },
        )

    if fmt == "pdf":
        # 直接从 Markdown 生成 HTML，再用浏览器引擎渲染为 PDF，尽量与前端样式一致
        html = _markdown_to_html(md, req.title, for_pdf=True)
        pdf_bytes: bytes | None = None
        errors: list[str] = []
        # 优先 Chrome（与前端渲染更一致）
        try:
            pdf_bytes = _html_to_pdf_via_chrome(html)
        except HTTPException as e:
            errors.append(str(e.detail))
        except Exception as e:  # noqa: BLE001
            errors.append(f"chrome: {e}")
        # 回退 wkhtmltopdf
        if pdf_bytes is None:
            try:
                pdf_bytes = _html_to_pdf_via_wkhtmltopdf(html)
            except HTTPException as e:
                errors.append(str(e.detail))
            except Exception as e:  # noqa: BLE001
                errors.append(f"wkhtmltopdf: {e}")
        if pdf_bytes is None:
            raise HTTPException(status_code=500, detail=f"无法生成 PDF（需要 Chrome/Chromium 或 wkhtmltopdf）。详情: {'; '.join(errors)}")
        bio = io.BytesIO(pdf_bytes)
        return StreamingResponse(
            bio,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="export.pdf"'
            },
        )

    raise HTTPException(status_code=400, detail="不支持的导出格式")
