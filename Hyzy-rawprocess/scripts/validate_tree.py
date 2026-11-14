#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hyzy-rawprocess · 整树图片引用校验（relink 模式）

复制 / 移动整树后，扫描目标目录下所有 .md，校验每个 md 的图片引用
是否都能解析到真实文件。替代手动遍历引用查断链。

用法：
    python validate_tree.py <root_dir>

退出码：0=全部可解析，1=存在缺失，2=目录不存在。
"""
import os
import re
import sys

IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def main():
    if len(sys.argv) < 2:
        print("用法: python validate_tree.py <root_dir>")
        sys.exit(2)
    root = os.path.abspath(sys.argv[1])
    if not os.path.isdir(root):
        print(f"[ERROR] 目录不存在: {root}")
        sys.exit(2)

    md_files = []
    for dirpath, _, files in os.walk(root):
        for fn in files:
            if fn.lower().endswith(".md"):
                md_files.append(os.path.join(dirpath, fn))
    md_files.sort()

    total_missing = 0
    print(f"扫描 {len(md_files)} 个 md 文件 under {os.path.relpath(root) or '.'}\n")
    for md in md_files:
        base = os.path.dirname(md)
        with open(md, "r", encoding="utf-8") as f:
            text = f.read()
        refs = IMG_RE.findall(text)
        local = [r for r in refs if not r.startswith(("http://", "https://"))]
        miss = []
        for r in local:
            if not os.path.exists(os.path.normpath(os.path.join(base, r))):
                miss.append(r)
        total_missing += len(miss)
        status = "OK " if not miss else "ERR"
        rel = os.path.relpath(md, root)
        print(f"[{status}] {rel}  本地引用{len(local)} 缺失{len(miss)}")
        for r in miss:
            print(f"       缺失: {r}")

    print("=" * 48)
    print(f"总 md 数: {len(md_files)}")
    print(f"总本地图片缺失: {total_missing}")
    if total_missing:
        print("结论: 存在断链，需修复")
        sys.exit(1)
    print("结论: 全部图片引用可解析")


if __name__ == "__main__":
    main()
