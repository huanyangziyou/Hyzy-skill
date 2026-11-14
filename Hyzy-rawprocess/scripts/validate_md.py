#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hyzy-rawprocess · 单文件 Markdown 校验（合并版）

一次性输出：
  - 标题层级计数（H1/H2/H3）
  - 图片引用总数 + 本地引用能否解析到真实文件（逐条 [OK]/[MISS]）
  - 残留「[图片]」占位符数
  - 缺图标注数（统一约定词）
  - 代码块围栏对数（是否成对）
  - 文件大小
  - 弱校验：空 alt 图片引用数（建议补图注）

用法：
    python validate_md.py <md_path> [--rel <图片基准目录>]

不传 --rel 时，图片引用按 md 所在目录相对解析。
退出码：0=通过，1=存在需修复项，2=文件不存在。

注意：本脚本只校验「文件是否存在 / 结构是否闭合」，不保证图片内容与正文语义一致。
"""
import argparse
import os
import re
import sys

MISSING_NOTE_RE = re.compile(r"配图未随文本提供|原文此处有配图但未随文本提供")
IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def main():
    ap = argparse.ArgumentParser(description="Hyzy-rawprocess 单文件校验")
    ap.add_argument("md", help="待校验的 Markdown 文件路径")
    ap.add_argument("--rel", help="图片基准目录，默认用 md 所在目录")
    args = ap.parse_args()

    md = os.path.abspath(args.md)
    if not os.path.isfile(md):
        print(f"[ERROR] 文件不存在: {md}")
        sys.exit(2)

    base = os.path.abspath(args.rel) if args.rel else os.path.dirname(md)
    with open(md, "r", encoding="utf-8") as f:
        text = f.read()
    lines = text.split("\n")

    # 忽略代码块内的标题统计（ fenced code blocks ）
    in_code = False
    body_lines = []
    for l in lines:
        if l.strip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            body_lines.append(l)

    h1 = sum(1 for l in body_lines if re.match(r"^# ", l))
    h2 = sum(1 for l in body_lines if re.match(r"^## ", l))
    h3 = sum(1 for l in body_lines if re.match(r"^### ", l))

    img_refs = IMG_RE.findall(text)
    missing = []
    for alt, ref in img_refs:
        if ref.startswith("http://") or ref.startswith("https://"):
            continue
        path = os.path.normpath(os.path.join(base, ref))
        ok = os.path.exists(path)
        flag = "OK " if ok else "MISS"
        alt_disp = alt if alt.strip() else "空"
        print(f"  [{flag}] {ref}  (alt={alt_disp})")
        if not ok:
            missing.append(ref)

    residual = len(re.findall(r"\[图片\]", text))
    missing_note = len(MISSING_NOTE_RE.findall(text))
    fences = sum(1 for l in lines if l.strip().startswith("```"))
    fence_ok = fences % 2 == 0
    empty_alt = sum(1 for alt, _ in img_refs if not alt.strip())
    size = os.path.getsize(md)

    print("=" * 48)
    print(f"H1={h1}  H2={h2}  H3={h3}")
    print(f"图片引用总数: {len(img_refs)}（本地缺失: {len(missing)}）")
    print(f"残留 [图片] 占位符: {residual}")
    print(f"缺图标注数: {missing_note}")
    print(f"代码块围栏数: {fences}  ({'成对' if fence_ok else '不成对!'})")
    if empty_alt:
        print(f"[弱校验] 空 alt 图片引用: {empty_alt}（建议补图注留痕）")
    print(f"文件大小: {size} 字节")
    print("-" * 48)
    print("声明：存在性校验通过 ≠ 图片内容与正文语义一致，图义正确性需人工/模型核对。")

    if missing or not fence_ok or residual:
        print("结论: 存在需要修复的项")
        sys.exit(1)
    print("结论: 通过")


if __name__ == "__main__":
    main()
