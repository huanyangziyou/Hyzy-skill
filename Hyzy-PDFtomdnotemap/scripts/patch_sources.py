#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修补「来源行」：让顶部来源行覆盖「多书对照」节里引用的所有书目。

问题背景：笔记顶部写 `> 来源：B3《书名》4.1.1`，但「多书对照」节里引用了 B4 / T4
         —— 核验会报「来源行未覆盖」。本脚本自动从对照表第二列提取书目编号，
         与来源行求差集后追加。

用法：
    # 默认 dry-run（只打印 diff，不写文件）
    python patch_sources.py --root "<库根>/70-图像与视频"

    # 递归整个库
    python patch_sources.py --base "<库根>" --recursive

    # 真正写盘（会原地改写文件，执行前需用户确认）
    python patch_sources.py --root "..." --apply

安全说明：默认 dry-run；仅当显式传 --apply 才写盘，且只改「来源行」那一行（不删任何内容）。
         不联网；不删除任何文件。
"""
import argparse
import io
import os
import re
import sys

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass

BOOK_DEFAULT = r"\b([A-Za-z]{1,3}\d{1,2})\b"


def get_src_line(text):
    """返回 (类型, 行号索引, 原文)；类型 quote='> 来源：' yaml='来源:'"""
    lines = text.split("\n")
    for i, l in enumerate(lines):
        if l.startswith("> 来源："):
            return "quote", i, l
    for i, l in enumerate(lines):
        if l.startswith("来源:"):
            return "yaml", i, l
    return None, -1, None


def tbl_refs(text, book_rx):
    """从「多书对照」节解析 {书号: 该行第二列描述}"""
    m = re.search(r"## 多书对照(.*?)(?=\n## )", text, re.S)
    if not m:
        m = re.search(r"## 多书对照(.*)\Z", text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).split("\n"):
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2 or cells[0] in ("视角", "来源", "---"):
            continue
        if set(cells[0]) <= set("-: "):
            continue
        col = cells[1]
        for b in book_rx.findall(col):
            out.setdefault(b, col)
    return out


def clean_desc(col):
    return re.sub(r"\s+", " ", col).strip()


def collect(root, recursive, excludes):
    out = []
    if recursive:
        for dp, dn, fn in os.walk(root):
            if any(k in dp for k in excludes):
                continue
            for f in sorted(fn):
                if f.endswith(".md") and not f.startswith("_"):
                    out.append(os.path.join(dp, f))
    else:
        for f in sorted(os.listdir(root)):
            if f.endswith(".md") and not f.startswith("_"):
                out.append(os.path.join(root, f))
    return out


def main():
    ap = argparse.ArgumentParser(description="修补来源行使其覆盖「多书对照」引用书目")
    ap.add_argument("--root", default="", help="单个目录")
    ap.add_argument("--base", default="", help="库根目录（配合 --recursive）")
    ap.add_argument("--recursive", action="store_true", help="递归子目录")
    ap.add_argument("--apply", action="store_true", help="真正写盘（默认 dry-run）")
    ap.add_argument("--book-regex", default=BOOK_DEFAULT, help="书目编号正则")
    ap.add_argument("--exclude", action="append", default=[], help="跳过路径含此关键词（可重复）")
    args = ap.parse_args()

    root = args.base or args.root
    if not root or not os.path.isdir(root):
        print("请提供有效的 --root 或 --base 目录。")
        return 2
    root = os.path.abspath(root)
    book_rx = re.compile(args.book_regex)
    files = collect(root, args.recursive, list(args.exclude))

    print("扫描 %d 个 md（%s）" % (len(files), "APPLY 写盘" if args.apply else "dry-run"))
    report, changed = [], 0
    for p in files:
        rel = os.path.relpath(p, root)
        text = open(p, encoding="utf-8", errors="replace").read()
        kind, idx, old = get_src_line(text)
        if kind is None:
            report.append("⚠ %s 无来源行" % rel)
            continue
        have = set(book_rx.findall(old))
        refs = tbl_refs(text, book_rx)
        missing = [b for b in refs if b not in have]
        if not missing:
            continue
        add = " · ".join(clean_desc(refs[b]) for b in sorted(missing))
        new = old.rstrip() + " · " + add
        report.append("~ %s\n    旧: %s\n    新: %s" % (rel, old, new))
        if args.apply:
            at = text.index(old)
            text = text[:at] + new + text[at + len(old):]
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
        changed += 1

    print("\n".join(report) if report else "（无需修补）")
    print("\n共 %d 篇%s" % (changed, "已修补" if args.apply else "待修补（dry-run，加 --apply 才写盘）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
