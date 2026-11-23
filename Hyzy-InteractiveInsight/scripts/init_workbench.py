#!/usr/bin/env python3
"""在任意目录铺开可移植工作台模板（工作台 + 空清单 + 使用说明）。

用法：python init_workbench.py <目标目录>

行为：从 skill 的 templates/workbench.html 复制为 知识理解工作台.html；
若目标目录没有 manifest.js，则写入空的 window.WORKBENCH_MANIFEST = [];
已有文件一律不覆盖，打印 SKIP。无网络、无删除。
"""

import argparse
import os
import sys

TEMPLATE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "templates", "workbench.html")
EMPTY = "// 由 register_workbench.py 维护，勿手工改动格式。\nwindow.WORKBENCH_MANIFEST = [];\n"


def main():
    ap = argparse.ArgumentParser(description="初始化可移植理解物工作台（纯本地）")
    ap.add_argument("target", help="目标目录（理解物所在目录）")
    args = ap.parse_args()
    dest = os.path.abspath(args.target)
    os.makedirs(dest, exist_ok=True)

    wb = os.path.join(dest, "知识理解工作台.html")
    if os.path.exists(wb):
        print(f"SKIP  已存在 {wb}", file=sys.stderr)
    else:
        with open(TEMPLATE, encoding="utf-8") as fh:
            text = fh.read()
        with open(wb, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"OK    {wb}", file=sys.stderr)

    mf = os.path.join(dest, "manifest.js")
    if os.path.exists(mf):
        print(f"SKIP  已存在 {mf}", file=sys.stderr)
    else:
        with open(mf, "w", encoding="utf-8") as fh:
            fh.write(EMPTY)
        print(f"OK    {mf}", file=sys.stderr)

    print(f"READY {dest}", file=sys.stderr)


if __name__ == "__main__":
    main()
