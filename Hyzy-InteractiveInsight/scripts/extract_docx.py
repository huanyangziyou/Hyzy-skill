#!/usr/bin/env python3
"""按段落顺序还原 docx 正文，保留 OMML 数学公式的上下标结构。

普通文本提取（python-docx 的 p.text 或只读 m:t）会把公式拍平成歧义 ASCII，
例如 V 下标 ref 变成 Vref、V 下标 h± 变成 Vh±。本脚本递归解析 OMML：
  - m:sSub / m:sSup / m:sSubSup -> 基_{下}^{上} 记法
  - m:f（分式）-> (分子)/(分母)
  - m:rad（根式）-> sqrt(...)
  - m:d（定界符/括号）-> (...)
  - m:nary（求和/积分）-> Σ_{下}^{上} ...
其余 m:t 原样拼接。仅用标准库，无网络、无写盘、无删除。
"""

import argparse
import sys
import zipfile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"


def render_math(node):
    if node.tag == M + "t":
        return node.text or ""
    parts = []
    for child in node:
        tag = child.tag
        if tag == M + "t":
            parts.append(child.text or "")
        elif tag == M + "sSub":
            base = "".join(render_math(c) for c in child if c.tag == M + "e")
            sub = "".join(render_math(c) for c in child if c.tag == M + "sub")
            parts.append(base + "_(" + sub + ")")
        elif tag == M + "sSup":
            base = "".join(render_math(c) for c in child if c.tag == M + "e")
            sup = "".join(render_math(c) for c in child if c.tag == M + "sup")
            parts.append(base + "^(" + sup + ")")
        elif tag == M + "sSubSup":
            base = "".join(render_math(c) for c in child if c.tag == M + "e")
            sub = "".join(render_math(c) for c in child if c.tag == M + "sub")
            sup = "".join(render_math(c) for c in child if c.tag == M + "sup")
            parts.append(base + "_(" + sub + ")^(" + sup + ")")
        elif tag == M + "f":
            num = "".join(render_math(c) for c in child if c.tag == M + "num")
            den = "".join(render_math(c) for c in child if c.tag == M + "den")
            parts.append("(" + num + ")/(" + den + ")")
        elif tag == M + "rad":
            body = "".join(render_math(c) for c in child if c.tag == M + "e")
            parts.append("√(" + body + ")")
        elif tag == M + "d":
            body = "".join(render_math(c) for c in child if c.tag == M + "e")
            parts.append("(" + body + ")")
        elif tag == M + "nary":
            chr_node = child.find(M + "naryPr/" + M + "chr")
            op = chr_node.get(M + "val") if chr_node is not None else "∑"
            sub = "".join(render_math(c) for c in child if c.tag == M + "sub")
            sup = "".join(render_math(c) for c in child if c.tag == M + "sup")
            body = "".join(render_math(c) for c in child if c.tag == M + "e")
            parts.append(op + "_(" + sub + ")^(" + sup + ")" + body)
        else:
            parts.append("".join(render_math(c) for c in child))
    return "".join(parts)


def extract(path):
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    lines = []
    for p in root.iter(W + "p"):
        parts = []
        for node in p:
            if node.tag == W + "r":
                t = node.find(W + "t")
                if t is not None and t.text:
                    parts.append(t.text)
            elif node.tag == M + "oMath":
                parts.append(render_math(node))
        text = "".join(parts).strip()
        if text:
            lines.append(text)
    return lines


def main():
    ap = argparse.ArgumentParser(description="还原 docx 正文与 OMML 公式（含上下标，纯本地）")
    ap.add_argument("file", help="要提取的 .docx 文件")
    ap.add_argument("--stats", action="store_true", help="输出段落数与字符数统计")
    args = ap.parse_args()
    lines = extract(args.file)
    if args.stats:
        print(f"[stats] paragraphs={len(lines)} chars={len(chr(10).join(lines))}", file=sys.stderr)
    for line in lines:
        print(line)


if __name__ == "__main__":
    main()
