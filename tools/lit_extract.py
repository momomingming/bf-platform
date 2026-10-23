# -*- coding: utf-8 -*-
"""
文献正文抽取器（替代之前损坏的 extract_pdf*.py 输出）
=================================================
用法:
  python tools/lit_extract.py <源目录或PDF> [输出目录]

- 用 PyMuPDF 抽取文本，远比旧脚本干净（无 000001 页码噪声）。
- 若给定输出目录：每个 PDF 抽到 <输出目录>/<相对路径>.txt（UTF-8）。
- 若未给定输出目录：直接打印每个 PDF 前 4000 字符预览。

后续由人工/LLM 从这些干净正文里按 schema 抽取结构化样本。
"""
from __future__ import annotations
import sys, os, re, glob


def extract_text(pdf_path: str) -> str:
    import pymupdf
    doc = pymupdf.open(pdf_path)
    parts = [page.get_text() for page in doc]
    doc.close()
    text = "\n".join(parts)
    # 合并过多空行，保留段落结构
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: lit_extract.py <src pdf or dir> [out dir]")
        sys.exit(1)
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None

    if os.path.isdir(src):
        pdfs = sorted(glob.glob(os.path.join(src, "**", "*.pdf"), recursive=True))
    else:
        pdfs = [src]

    for p in pdfs:
        try:
            txt = extract_text(p)
        except Exception as e:  # noqa
            print(f"ERR {p}: {e}", file=sys.stderr)
            continue
        if out:
            rel = os.path.relpath(p, src) if os.path.isdir(src) else os.path.basename(p)
            op = os.path.join(out, rel + ".txt")
            os.makedirs(os.path.dirname(op), exist_ok=True)
            with open(op, "w", encoding="utf-8") as f:
                f.write(txt)
            print(f"OK  {op}  ({len(txt)} chars)")
        else:
            print(f"===== {p} =====")
            print(txt[:4000])


if __name__ == "__main__":
    main()
