#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「章节 -> 行号」素材定位表。

用途：并行子任务靠行号 Read --offset/--limit 精确取段，绝不整篇读源 md。
产物：一张 md 表，每本书一节，含 文件路径 / 图片目录+命名前缀 / 页数 / 标题行号表。

用法：
    python build_locator.py --src "<素材目录>" --out "<素材目录>/_素材定位表.md"

    # 带标签/书名/页数（推荐：标签是后续「来源行」的锚）
    # tagmap.csv 格式（无表头，UTF-8）：
    #   stem,T1,Verilog 语法入门,111
    python build_locator.py --src "..." --out "..." --tag-map "tagmap.csv"

安全说明：只读源文件，只写 --out 指定的一个文件；不联网；不删除任何文件。
"""
import argparse
import csv
import io
import os
import re
import sys

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass

# pymupdf4llm 图片名形如 <前缀>-0037-08.png；前缀从真实文件反推，不要硬编码
DEFAULT_IMG_RE = r"(.*?)-\d{4}-\d{2}\.png$"


def load_tagmap(path):
    m = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.reader(f):
            if len(row) < 2 or not row[0].strip():
                continue
            stem = row[0].strip()
            tag = row[1].strip()
            name = row[2].strip() if len(row) > 2 else stem
            pages = row[3].strip() if len(row) > 3 else ""
            m[stem] = (tag, name, pages)
    return m


def infer_img_prefix(imgdir, pattern):
    if not os.path.isdir(imgdir):
        return "?", 0
    pngs = sorted(f for f in os.listdir(imgdir) if f.lower().endswith((".png", ".jpg", ".jpeg")))
    if not pngs:
        return "?", 0
    rx = re.compile(pattern)
    for f in pngs:
        m = rx.match(f)
        if m:
            return m.group(1), len(pngs)
    return pngs[0], len(pngs)


def find_books(src, recursive):
    """返回 [(stem, md_abs, imgdir)]，约定 <src>/<stem>/<stem>.md"""
    out = []
    for entry in sorted(os.listdir(src)):
        d = os.path.join(src, entry)
        if not os.path.isdir(d):
            continue
        md = os.path.join(d, entry + ".md")
        if os.path.exists(md):
            out.append((entry, md, os.path.join(d, "images")))
        elif recursive:
            for sub, subs, files in os.walk(d):
                for f in sorted(files):
                    if f.lower().endswith(".md") and os.path.splitext(f)[0] == os.path.basename(sub):
                        out.append((os.path.splitext(f)[0], os.path.join(sub, f),
                                    os.path.join(sub, "images")))
    return out


def main():
    ap = argparse.ArgumentParser(description="生成素材章节行号定位表")
    ap.add_argument("--src", required=True, help="素材根目录（下含 <stem>/<stem>.md）")
    ap.add_argument("--out", required=True, help="输出定位表路径")
    ap.add_argument("--tag-map", default="", help="CSV: stem,tag,显示名,页数")
    ap.add_argument("--tag-prefix", default="S", help="无 tag-map 时的标签前缀（默认 S -> S1,S2…）")
    ap.add_argument("--img-regex", default=DEFAULT_IMG_RE, help="图片名页码正则")
    ap.add_argument("--recursive", action="store_true", help="递归查找 <stem>/<stem>.md")
    ap.add_argument("--title", default="素材定位表", help="定位表标题")
    args = ap.parse_args()

    src = os.path.abspath(args.src)
    tagmap = load_tagmap(args.tag_map) if args.tag_map else {}
    books = find_books(src, args.recursive)
    if not books:
        print("未找到任何 <stem>/<stem>.md，请确认 --src 与目录约定。")
        return 1

    L = []
    L.append("# %s" % args.title)
    L.append("")
    L.append("> 各书章节标题 + 行号索引。**子任务用 Read --offset/--limit 定位原文，不要整篇读。**")
    L.append("> 生成脚本：`skills/Hyzy-PDFtomdnotemap/scripts/build_locator.py`")
    L.append("")

    idx = 0
    total = 0
    for stem, md, imgdir in books:
        idx += 1
        if stem in tagmap:
            tag, disp, pages = tagmap[stem]
        else:
            tag, disp, pages = "%s%d" % (args.tag_prefix, idx), stem, ""
        prefix, nimg = infer_img_prefix(imgdir, args.img_regex)
        L.append("## %s《%s》" % (tag, disp))
        L.append("")
        L.append("- 文件：`%s`" % md)
        L.append("- 图片目录：`%s`（%d 张，文件名形如 `%s-<4位页>-<2位序>.png`）"
                 % (imgdir, nimg, prefix))
        L.append("- 页数：%s" % (pages if pages else "（未提供）"))
        L.append("")
        L.append("| 行号 | 层级 | 标题 |")
        L.append("|---|---|---|")
        n = 0
        with open(md, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                s = line.rstrip("\n")
                if s.startswith("### "):
                    L.append("| %d | H3 | %s |" % (i, s[4:].strip()))
                elif s.startswith("## "):
                    L.append("| %d | H2 | %s |" % (i, s[3:].strip()))
                elif s.startswith("# "):
                    L.append("| %d | H1 | %s |" % (i, s[2:].strip()))
                else:
                    continue
                n += 1
        total += n
        L.append("")
        L.append("> 共 %d 个标题。" % n)
        L.append("")

    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("已写入 %s" % out)
    print("  书 %d 本 / 标题 %d 个 / %d bytes" % (len(books), total, os.path.getsize(out)))
    print("  提示：页码反推规律(<4位数字>=页号)并非对所有书成立，首次使用前务必抽一张已知页的图核对。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
