from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from src.schemas import Document
from src.services.parser import parse_text_to_blocks

import io
import os
import shutil
import subprocess
import tempfile


router = APIRouter(prefix="/upload", tags=["upload"])


async def _read_txt(file: UploadFile) -> str:
    data = await file.read()
    # 假设 UTF-8，必要时可尝试 chardet
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data.decode("gb18030")
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"无法解码文本: {e}")


async def _read_md(file: UploadFile) -> str:
    return await _read_txt(file)


def _read_docx_from_bytes(data: bytes) -> str:
    """将 .docx 二进制读取为纯文本（优先 mammoth，回退 python-docx）。

    若传入的数据并非有效的 .docx（非 ZIP，常见于 .doc 被误改后缀），
    则尝试按 .doc 走转换（libreoffice/pandoc）后再解析。
    """
    # 简单签名校验：docx 为 zip 容器，应以 'PK' 开头
    if not data.startswith(b"PK"):
        try:
            # 视为 .doc，尝试转换
            converted = _convert_doc_to_docx_bytes(data)
            data = converted
        except HTTPException as e:
            # 无转换工具或转换失败，按 415 返回
            raise HTTPException(
                status_code=415,
                detail=(
                    "文件不是有效的 .docx，且自动将 .doc 转 .docx 失败。"
                    "请安装 libreoffice 或 pandoc，或在本地另存为 DOCX 后再上传。"
                    f" 详细: {e.detail}"
                ),
            ) from e

    errors: list[str] = []

    # 1) mammoth 提取纯文本
    try:
        import mammoth  # type: ignore

        result = mammoth.extract_raw_text(io.BytesIO(data))
        return result.value  # type: ignore[attr-defined]
    except Exception as e:  # noqa: BLE001
        errors.append(f"mammoth: {e}")

    # 2) 回退：python-docx 逐段落合并
    try:
        from docx import Document as DocxDocument  # type: ignore

        doc = DocxDocument(io.BytesIO(data))
        paras = [p.text for p in doc.paragraphs]
        return "\n".join(paras)
    except Exception as e:  # noqa: BLE001
        errors.append(f"python-docx: {e}")

    # 统一错误输出，便于排查具体原因
    raise HTTPException(status_code=400, detail=f"DOCX 解析失败: {'; '.join(errors)}")


async def _read_docx(file: UploadFile) -> str:
    """UploadFile 读取为字节后调用 _read_docx_from_bytes。"""
    data = await file.read()
    return _read_docx_from_bytes(data)


def _which(bin_name: str) -> str:
    p = shutil.which(bin_name)
    return p or ""


def _soffice_bin() -> str:
    # 允许通过环境变量覆盖
    envp = os.getenv("SOFFICE_BIN")
    if envp and os.path.exists(envp):
        return envp
    return _which("libreoffice") or _which("soffice")


def _convert_doc_to_docx_bytes(data: bytes) -> bytes:
    """使用 libreoffice 或 pandoc 将 .doc 转换为 .docx，返回 .docx 二进制。

    优先使用 libreoffice（兼容性最佳），回退 pandoc。均不可用时抛错。
    """
    with tempfile.TemporaryDirectory(prefix="wordline_") as td:
        in_path = os.path.join(td, "input.doc")
        out_path = os.path.join(td, "input.docx")
        with open(in_path, "wb") as f:
            f.write(data)

        err_msgs: list[str] = []

        soffice = _soffice_bin()
        if soffice:
            try:
                # libreoffice --headless --convert-to docx --outdir <td> <in>
                cp = subprocess.run(
                    [
                        soffice,
                        "--headless",
                        "--convert-to",
                        "docx",
                        "--outdir",
                        td,
                        in_path,
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=60,
                    check=True,
                )
                if os.path.exists(out_path):
                    return open(out_path, "rb").read()
                err_msgs.append(f"libreoffice 未生成输出: {cp.stdout.decode(errors='ignore')}")
            except Exception as e:  # noqa: BLE001
                err_msgs.append(f"libreoffice: {e}")

        pandoc = _which("pandoc")
        if pandoc:
            try:
                cp = subprocess.run(
                    [pandoc, in_path, "-o", out_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=60,
                    check=True,
                )
                if os.path.exists(out_path):
                    return open(out_path, "rb").read()
                err_msgs.append(f"pandoc 未生成输出: {cp.stdout.decode(errors='ignore')}")
            except Exception as e:  # noqa: BLE001
                err_msgs.append(f"pandoc: {e}")

        raise HTTPException(
            status_code=500,
            detail=(
                "无法将 .doc 转换为 .docx：未检测到可用的转换工具（libreoffice/soffice 或 pandoc）。"
                f" 详细: {'; '.join(err_msgs)}"
            ),
        )


async def _read_doc(file: UploadFile) -> str:
    """读取 .doc，自动转换为 .docx 后解析为文本。"""
    data = await file.read()
    docx_bytes = _convert_doc_to_docx_bytes(data)
    return _read_docx_from_bytes(docx_bytes)


@router.post("")
async def upload_and_parse(file: UploadFile = File(...)) -> JSONResponse:
    filename = file.filename or ""
    if not filename:
        raise HTTPException(status_code=400, detail="缺少文件名")

    suffix = filename.split(".")[-1].lower()
    if suffix not in {"txt", "md", "docx", "doc"}:
        raise HTTPException(status_code=415, detail="仅支持 txt/md/docx/doc")

    if suffix == "txt":
        text = await _read_txt(file)
    elif suffix == "md":
        text = await _read_md(file)
    elif suffix == "docx":
        text = await _read_docx(file)
    else:  # doc
        text = await _read_doc(file)

    doc: Document = parse_text_to_blocks(text)
    return JSONResponse(content=doc.model_dump())
