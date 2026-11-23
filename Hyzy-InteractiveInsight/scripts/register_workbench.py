#!/usr/bin/env python3
"""把理解物 HTML 登记进工作台索引 manifest.js（可复用平台载体的入库端）。

从 HTML 解析：标题 / 一句话总结 / 疑问模块数 / 图形层；主题可用 --topic 指定，
否则沿用同名旧条目，再否则归为「未分类」。按文件名去重，保留已有条目顺序。

用法：
  python register_workbench.py <file.html> [...] --manifest <dir>/manifest.js [--topic 主题名]

manifest.js 形如：window.WORKBENCH_MANIFEST = [ {...}, ... ];
用 .js 而非 .json 是为了在 file:// 下用 <script src> 加载（fetch 本地 JSON 会被同源策略拦）。

仅用标准库，无网络、无删除、不改动理解物本身。
"""

import argparse
import html
import json
import os
import re
import sys


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def parse_html(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", text, re.I | re.S)
    title = strip_tags(m.group(1)) if m else os.path.basename(path)
    title = re.sub(r"（v\d+[^）]*）", "", title).strip()
    d = (re.search(r"一句话总结</strong>[:：]([\s\S]*?)</p>", text, re.I | re.S)
         or re.search(r"<blockquote>([\s\S]*?)</blockquote>", text, re.I | re.S))
    desc = strip_tags(d.group(1)) if d else "本地理解物。"
    mods = len(re.findall(r'<details[^>]*class="mod"', text))
    svg = "<svg" in text
    meta = f"{mods} 个疑问模块 · 四层折叠" + (" · 含图形层" if svg else "")
    return title, desc, meta


def load(manifest):
    if not os.path.exists(manifest):
        return []
    with open(manifest, encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(r"=\s*(\[[\s\S]*\])\s*;", text)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        print(f"WARN  manifest 解析失败，将重建：{manifest}", file=sys.stderr)
        return []


def main():
    ap = argparse.ArgumentParser(description="登记理解物到工作台索引（纯本地）")
    ap.add_argument("files", nargs="+", help="要登记的 .html 理解物")
    ap.add_argument("--manifest", default="manifest.js", help="manifest.js 路径")
    ap.add_argument("--topic", default="", help="主题标签名；省略则沿用旧条目或归为未分类")
    args = ap.parse_args()

    base = os.path.dirname(os.path.abspath(args.manifest))
    entries = load(args.manifest)
    by_file = {e.get("file"): i for i, e in enumerate(entries)}

    added = updated = 0
    for path in args.files:
        if not os.path.exists(path):
            print(f"SKIP  文件不存在 {path}", file=sys.stderr)
            continue
        name = os.path.basename(path)
        rel = "./" + name
        title, desc, meta = parse_html(path)
        old = entries[by_file[rel]] if rel in by_file else {}
        topic = args.topic or old.get("topicLabel") or "未分类"
        item = {"file": rel, "title": title, "desc": desc,
                "meta": meta, "topicLabel": topic}
        if rel in by_file:
            entries[by_file[rel]].update(item)
            updated += 1
        else:
            by_file[rel] = len(entries)
            entries.append(item)
            added += 1

    out = ("// 由 register_workbench.py 生成，勿手工改动格式。\n"
           "window.WORKBENCH_MANIFEST = "
           + json.dumps(entries, ensure_ascii=False, indent=2) + ";\n")
    with open(args.manifest, "w", encoding="utf-8") as fh:
        fh.write(out)
    print(f"OK  manifest={args.manifest} total={len(entries)} added={added} updated={updated}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
