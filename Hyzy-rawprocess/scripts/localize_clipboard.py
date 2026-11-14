#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hyzy-rawprocess · 剪贴板图批量本地化

从剪贴板目录取最近 N 张截图（或显式指定源文件），按语义重命名复制到目标 images/。
替代每次手写 20 行 cp，避免图序错位。

用法：
  # 取修改时间最新的 3 张，按 @image#1..#3 顺序命名
  python localize_clipboard.py --dest "<OUT_DIR>/images" --latest 3 \
      --names "01-visual-board.jpg,02-storyboard.png,03-ui.png"

  # 显式指定源文件名（最可靠，避免 tail 误抓旧图）
  python localize_clipboard.py --dest "<OUT_DIR>/images" \
      --files "clipboard-aaa.png,clipboard-bbb.jpg" \
      --names "01-a.png,02-b.png"

  # 预览不复制
  python localize_clipboard.py --dest "<OUT_DIR>/images" --latest 3 --names "01.png,02.png,03.png" --dry-run

环境变量：
  HYZY_CLIPBOARD_DIR  覆盖剪贴板目录（默认 %USERPROFILE%/.workbuddy/clipboard-images）

约束：
  - --names 数量必须等于源文件数量，否则报错
  - 扩展名以 --names 为准
  - --latest 按修改时间升序取末尾 N 个（与粘贴时间序一致）
"""
import argparse
import os
import shutil
import sys

def _default_src() -> str:
    """剪贴板目录：环境变量优先，其次宿主默认位置。

    Git Bash 下 $HOME 常为空，故用 USERPROFILE 兜底；两处都取不到时返回
    默认位置字符串，由 --src 的目录检查给出明确报错（不静默用当前目录）。
    """
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""
    fallback = os.path.join(home, ".workbuddy", "clipboard-images")
    for c in (os.environ.get("HYZY_CLIPBOARD_DIR"), fallback):
        if c and os.path.isdir(c):
            return c
    return fallback


DEFAULT_SRC = _default_src()


def main():
    ap = argparse.ArgumentParser(description="剪贴板图批量本地化")
    ap.add_argument("--src", default=DEFAULT_SRC, help="剪贴板目录（默认 %%USERPROFILE%%/.workbuddy/clipboard-images，可用 HYZY_CLIPBOARD_DIR 覆盖）")
    ap.add_argument("--dest", required=True, help="目标 images 目录")
    ap.add_argument("--latest", type=int, help="取修改时间最新的 N 张")
    ap.add_argument("--files", help="显式源文件名列表，逗号分隔（最可靠）")
    ap.add_argument("--names", required=True, help="目标语义名列表，逗号分隔，含扩展名")
    ap.add_argument("--dry-run", action="store_true", help="只打印不复制")
    args = ap.parse_args()

    names = [n.strip() for n in args.names.split(",") if n.strip()]

    if args.files:
        src_files = [f.strip() for f in args.files.split(",") if f.strip()]
    elif args.latest:
        if not os.path.isdir(args.src):
            print(f"[ERROR] 源目录不存在: {args.src}")
            sys.exit(2)
        all_files = [f for f in os.listdir(args.src) if os.path.isfile(os.path.join(args.src, f))]
        all_files.sort(key=lambda f: os.path.getmtime(os.path.join(args.src, f)))
        src_files = all_files[-args.latest:]
    else:
        print("[ERROR] 必须指定 --latest N 或 --files list")
        sys.exit(2)

    if len(src_files) != len(names):
        print(f"[ERROR] 源文件数({len(src_files)}) != 命名数({len(names)})")
        sys.exit(2)

    os.makedirs(args.dest, exist_ok=True)
    print(f"源: {args.src}")
    print(f"目标: {args.dest}")
    print("-" * 48)
    for src, name in zip(src_files, names):
        src_path = os.path.join(args.src, src)
        dst_path = os.path.join(args.dest, name)
        if args.dry_run:
            print(f"[DRY] {src} -> {name}")
        else:
            shutil.copy2(src_path, dst_path)
            print(f"[OK ] {src} -> {name}")

    if not args.dry_run:
        print(f"\n完成: {len(names)} 张已复制到 {args.dest}")


if __name__ == "__main__":
    main()
