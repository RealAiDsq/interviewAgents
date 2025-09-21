async def main(args: Args) -> Output:
    import re

    p = args.params or {}

    # ---------- 工具：统一转字符串 ----------
    def to_text(v):
        if isinstance(v, str):
            return v
        if isinstance(v, (list, tuple)):
            return "\n".join("" if x is None else str(x) for x in v)
        if isinstance(v, dict):
            cand = v.get("text") or v.get("content") or v.get("data")
            if isinstance(cand, str):
                return cand
            if cand is None:
                paras = v.get("paragraphs")
                if isinstance(paras, (list, tuple)):
                    return "\n".join("" if x is None else str(x) for x in paras)
            return str(cand)
        return "" if v is None else str(v)

    text = to_text(p.get("data") or p.get("text") or "").replace("\r\n", "\n").replace("\r", "\n")

    # ---------- 参数读取与兜底 ----------
    def to_int(val, default):
        try:
            return int(val)
        except Exception:
            return default

    target        = to_int(p.get("target_chunk_chars"), 10000)
    min_turns     = to_int(p.get("min_turns_per_chunk"), 3)
    fb_size       = to_int(p.get("fallback_chunk_chars"), 3500)
    fb_overlap    = to_int(p.get("fallback_overlap_chars"), 200)
    allow_name_only = True if p.get("allow_name_only_header") is None else bool(p.get("allow_name_only_header"))

    if target <= 0:
        target = 10000
    if min_turns < 1:
        min_turns = 1
    if fb_size <= 0:
        fb_size = 3500
    if fb_overlap < 0:
        fb_overlap = 0

    # ---------- 正则：允许全角/半角冒号及后续任意内容 ----------
    time_header_re = re.compile(
        r'''^\s*(?P<name>[\u4e00-\u9fffA-Za-z0-9_.·\-（）()“”'"\s]{1,30})
        \s+(?P<time>\d{1,2}:\d{2}(?::\d{2})?)          # 时间
        \s*[：:]*                                       # 允许冒号
        .*$''', re.X)
    header_patterns_used = [f'builtin_time:{time_header_re.pattern}']

    # ---------- 空文本早退 ----------
    if not text.strip():
        return {
            "chunks": [], "chunks_count": 0, "turns_count": 0, "total_chars": 0,
            "speakers": [], "chunk_meta": [], "preamble": "",
            "header_patterns_used": header_patterns_used, "name_only_headers_used": 0
        }

    # ---------- 清理下划线 ----------
    lines = [re.sub(r'_+', '', ln) for ln in text.split("\n")]

    # ---------- 匹配时间码头部 ----------
    headers = []
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s:
            continue
        m = time_header_re.fullmatch(s)
        if m:
            name = m.group("name").strip()
            tm = m.group("time").strip()
            headers.append({"i": i, "speaker": name, "time": tm, "kind": "time"})

    # ---------- 启发式：纯姓名头部 ----------
    name_only_used = 0
    def is_name_only_header(idx: int) -> str:
        s = lines[idx].strip()
        if not s or len(s) > 20 or len(s) < 1:
            return ""
        if re.search(r'[。！？!?,，；;：:…]', s) or re.search(r'\d', s):
            return ""
        if not re.fullmatch(r'[\u4e00-\u9fffA-Za-z·\-\._（）()]{1,20}', s):
            return ""
        if idx > 0 and lines[idx - 1].strip():
            return ""
        if idx + 1 >= len(lines):
            return ""
        nxt = lines[idx + 1].strip()
        if not nxt or time_header_re.fullmatch(nxt) or len(nxt) < 3:
            return ""
        return s

    if allow_name_only:
        taken = {h["i"] for h in headers}
        for i in range(len(lines)):
            if i in taken or not lines[i].strip():
                continue
            name = is_name_only_header(i)
            if name:
                headers.append({"i": i, "speaker": name, "time": "", "kind": "name"})
                name_only_used += 1
        if name_only_used:
            header_patterns_used.append("name_only:heuristic")

    # ---------- 无头部：回退切分 ----------
    if not headers:
        chunks, n = [], len(text)
        start = 0
        effective_overlap = min(fb_overlap, max(fb_size - 1, 0))
        while start < n:
            end = min(start + fb_size, n)
            chunks.append(text[start:end])
            if end >= n:
                break
            next_start = end - effective_overlap
            start = next_start if next_start > start else start + 1
        return {
            "chunks": chunks, "chunks_count": len(chunks), "turns_count": 0,
            "total_chars": sum(len(c) for c in chunks), "speakers": [],
            "chunk_meta": [{"from_turn_index": None, "to_turn_index": None,
                            "char_count": len(c), "turns_count": None} for c in chunks],
            "preamble": "", "header_patterns_used": header_patterns_used,
            "name_only_headers_used": 0
        }

    # ---------- 构造 turns ----------
    headers.sort(key=lambda x: x["i"])
    preamble_lines = lines[:headers[0]["i"]] if headers[0]["i"] > 0 else []
    turns = []
    for idx, h in enumerate(headers):
        start_i = h["i"]
        end_i = headers[idx + 1]["i"] - 1 if idx + 1 < len(headers) else len(lines) - 1
        content_lines = lines[start_i + 1: end_i + 1]
        content = "\n".join(content_lines).rstrip("\n")
        header_line = lines[start_i].strip()
        block = header_line + (("\n" + content) if content else "")
        turns.append({
            "speaker": h["speaker"], "time": h["time"], "kind": h["kind"],
            "header_line": header_line, "block_text": block, "chars": len(block)
        })

    # ---------- 贪心打包 chunks ----------
    chunks, chunk_meta = [], []
    buf, buf_chars, from_turn = [], 0, 0
    for i, t in enumerate(turns):
        b, blen = t["block_text"], len(t["block_text"])
        sep = 1 if buf else 0
        projected = buf_chars + sep + blen

        if not buf and blen >= target:          # 超长单段独立成块
            chunks.append(b)
            chunk_meta.append({"from_turn_index": i, "to_turn_index": i,
                               "char_count": blen, "turns_count": 1})
            from_turn = i + 1
            buf, buf_chars = [], 0
            continue

        if buf and projected > target and len(buf) >= min_turns:  # 封块
            chunk_text = "\n".join(buf)
            chunks.append(chunk_text)
            chunk_meta.append({"from_turn_index": from_turn,
                               "to_turn_index": i - 1,
                               "char_count": len(chunk_text),
                               "turns_count": len(buf)})
            from_turn, buf, buf_chars = i, [b], blen
        else:
            if buf:
                buf_chars += sep
            buf.append(b)
            buf_chars += blen

    if buf:                                       # 收尾
        chunk_text = "\n".join(buf)
        chunks.append(chunk_text)
        chunk_meta.append({"from_turn_index": from_turn,
                           "to_turn_index": from_turn + len(buf) - 1,
                           "char_count": len(chunk_text),
                           "turns_count": len(buf)})

    total_chars = sum(m["char_count"] for m in chunk_meta)
    speakers_order = []
    for t in turns:
        s = t["speaker"]
        if s not in speakers_order:
            speakers_order.append(s)

    # ---------- 返回：全部基本类型 ----------
    return {
        "chunks": chunks,
        "chunks_count": len(chunks),
        "turns_count": len(turns),
        "total_chars": total_chars,
        "speakers": speakers_order,
        "chunk_meta": chunk_meta,
        "preamble": "\n".join(preamble_lines).strip(),
        "header_patterns_used": header_patterns_used,   # 仅字符串列表
        "name_only_headers_used": name_only_used
    }