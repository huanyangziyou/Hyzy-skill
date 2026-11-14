#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批次核验器：对一批新建/补强笔记做结构与引用体检。

检查项：
  文件到位 / 必备小节齐全 / 小节顺序 / 图片断链 / wikilink 越界 /
  来源行 / 「多书对照」>=N 本 / 「插图」节内混入 H3 / 空文件

用法：
    # 1) 先写批次清单 JSON（见下），再跑
    python verify_notes.py --base "<库根>" --batch "batch-P4.json" \
        --img-root "<库根>/<素材区>" --img-root "<素材目录>"

批次清单 JSON 格式：
    {
      "NEW":   { "45-通信与网络": ["以太网协议与帧结构", "UDP 协议与硬件实现"] },
      "PATCH": [ "70-图像与视频/视频接口.md" ]
    }
    （也接受顶层直接是数组 —— 视为 PATCH 路径清单）

安全说明：只读笔记与图片目录；不写任何文件；不联网；不删除任何文件。
"""
import argparse
import glob
import io
import json
import os
import re
import sys

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass

STD_DEFAULT = ["## 一句话解释", "## 类比", "## 细节", "## 多书对照", "## 插图",
               "## 什么时候会用到", "## 容易混淆的点", "## 本机适配 / 赛题关联", "## 参考"]
OPT_DEFAULT = ["## 多书对照", "## 插图"]
MAP_HINTS = ("概念地图", "总览与分类索引", "总览", "索引")


def norm(s):
    """归一化分隔符差异（· / 空格），用于识别同名节的旧写法。"""
    return re.sub(r"[·/\s]", "", s)


def load_batch(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return {}, list(data)
    new = data.get("NEW", data.get("new", {})) or {}
    patch = data.get("PATCH", data.get("patch", [])) or []
    files = list(patch)
    for dom, names in new.items():
        for n in names:
            files.append(("%s/%s" % (dom, n)) if dom else n)
    return new, files, patch


def find_map(base, explicit):
    if explicit:
        return explicit if os.path.exists(explicit) else ""
    cands = []
    for f in sorted(os.listdir(base)):
        if not f.endswith(".md"):
            continue
        if any(h in f for h in MAP_HINTS):
            cands.append(os.path.join(base, f))
    return cands[0] if cands else ""


def auto_img_roots(base):
    """默认把「库根 + 库的上一级」作为图片搜索根。

    短嵌入图片通常不在概念笔记目录内，而在同级/上层的素材区（<素材区>、<教材目录>等）。
    只搜库根会导致**全量假断图**。上一级若已是盘根则不加。
    """
    roots = [base]
    parent = os.path.dirname(base)
    if parent and os.path.dirname(parent) != parent and os.path.isdir(parent):
        roots.append(parent)
    return roots


def build_img_index(roots):
    imgs = set()
    for root in roots:
        if not os.path.isdir(root):
            print("⚠️ 图片根不存在，已跳过：%s" % root)
            continue
        for dp, dn, fn in os.walk(root):
            for f in fn:
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                    imgs.add(f)
    return imgs


def main():
    ap = argparse.ArgumentParser(description="批次笔记核验器")
    ap.add_argument("--base", required=True, help="概念笔记库根目录")
    ap.add_argument("--batch", required=True, help="批次清单 JSON")
    ap.add_argument("--map", default="", help="总索引文件（默认自动在库根查找）")
    ap.add_argument("--img-root", action="append", default=[],
                    help="图片搜索根（可重复；默认自动加入库根与其上一级）")
    ap.add_argument("--no-img-auto", action="store_true",
                    help="关闭图片根自动推断（只认 --img-root）")
    ap.add_argument("--extra-whitelist", action="append", default=[],
                    help="额外允许的 wikilink 目标（辅助页等，可重复）")
    ap.add_argument("--sections", default="", help="覆盖必备小节（逗号分隔）")
    ap.add_argument("--optional", default="", help="可省略小节（逗号分隔）")
    ap.add_argument("--min-books", type=int, default=2,
                    help="「多书对照」至少几本书（默认2；设 0 关闭该项）")
    ap.add_argument("--book-regex", default=r"\b([A-Za-z]{1,3}\d{1,2})\b",
                    help="书目编号正则，用于统计「多书对照」覆盖数")
    args = ap.parse_args()

    base = os.path.abspath(args.base)
    if not os.path.isdir(base):
        print("库根不存在：%s\n按 references/env-adapt.md：先向用户确认 <库根>（概念笔记库根目录），不要自己猜。" % base)
        return 2
    std = [s.strip() for s in args.sections.split(",") if s.strip()] or STD_DEFAULT
    opt = [s.strip() for s in args.optional.split(",") if s.strip()]
    if not args.sections:
        opt = OPT_DEFAULT
    std_norm = [norm(s) for s in std]

    mapf = find_map(base, args.map)
    white = {"000-概念地图", "00-总览与分类索引"}
    if mapf:
        txt = open(mapf, encoding="utf-8", errors="replace").read()
        white |= set(re.findall(r"\[\[([^\]]+)\]\]", txt))
        print("白名单来源：%s（%d 条）" % (os.path.basename(mapf), len(white)))
    else:
        print("⚠️ 未找到总索引，wikilink 越界检查将只认 --extra-whitelist 指定的目标")
    white |= set(args.extra_whitelist)

    roots = ([] if args.no_img_auto else auto_img_roots(base)) + list(args.img_root)
    seen = set()
    roots = [r for r in roots if not (r in seen or seen.add(r))]
    imgs = build_img_index(roots)
    print("图片索引：%d 个文件，搜索根 %d 个" % (len(imgs), len(roots)))
    for r in roots:
        print("   · %s" % r)

    if not os.path.isfile(args.batch):
        print("批次清单不存在：%s\n先按 SKILL.md Stage 5 写出 batch-*.json，再跑核验。" % args.batch)
        return 2
    new, files, patch = load_batch(args.batch)
    if not files:
        print("批次清单为空。")
        return 1

    print("\n=== 核验 %d 篇 ===" % len(files))
    bad_count = 0
    for rel in files:
        rel = rel if rel.endswith(".md") else rel + ".md"
        p = os.path.join(base, rel.replace("\\", "/"))
        if not os.path.exists(p):
            print("❌ 缺失: %s" % rel)
            bad_count += 1
            continue
        t = open(p, encoding="utf-8", errors="replace").read()
        nlines = t.count("\n") + 1
        msgs = []
        if not t.strip():
            msgs.append("空文件")
        hs = [l.strip() for l in t.split("\n") if l.startswith("## ")]
        seq = [norm(h) for h in hs if norm(h) in std_norm]
        missing = [std[std_norm.index(n)] for n in std_norm
                   if n not in seq and std[std_norm.index(n)] not in opt]
        if missing:
            msgs.append("缺小节 %s" % missing)
        idxs = [std_norm.index(n) for n in seq]
        if idxs != sorted(idxs):
            msgs.append("小节顺序错乱")
        unknown = [h for h in hs if norm(h) not in std_norm]
        if unknown:
            msgs.append("非标准 H2 %s" % unknown)
        imgs_in = re.findall(r"!\[\[([^\]]+)\]\]", t)
        broken = [i for i in imgs_in if i not in imgs]
        if broken:
            msgs.append("断图 %s" % broken[:5])
        links = [l for l in re.findall(r"\[\[([^\]]+)\]\]", t) if l not in imgs_in]
        outside = sorted(set(l for l in links if l not in white))
        if outside:
            msgs.append("越界链接 %s" % outside)
        if not ("> 来源：" in t or re.search(r"^来源:", t, re.M)):
            msgs.append("缺来源行")
        if args.min_books > 0:
            m = re.search(r"## 多书对照(.*?)(?=\n## |\Z)", t, re.S)
            if m:
                books = set(re.findall(args.book_regex, m.group(1)))
                if len(books) < args.min_books:
                    msgs.append("多书对照仅 %s 本（规范要求 >=%d）"
                                % (sorted(books) or 0, args.min_books))
        mi = re.search(r"## 插图(.*?)(?=\n## |\Z)", t, re.S)
        if mi and re.search(r"^### ", mi.group(1), re.M):
            msgs.append("插图节内含 H3（H3 应归「细节」节）")
        flag = "✅" if not msgs else "⚠️"
        if msgs:
            bad_count += 1
        print("%s %s  (%d行, 图%d, 链%d)%s"
              % (flag, rel, nlines, len(imgs_in), len(links),
                 "  | " + "; ".join(msgs) if msgs else ""))

    print("\n---- 汇总 ----")
    print("通过 %d / %d，问题 %d 篇" % (len(files) - bad_count, len(files), bad_count))
    if bad_count:
        print("修正纪律：把上述所有问题**合并成一轮**回派修正后重跑，不要发现一个改一个。")
        print("若大面积为「断图」：先核对上面的搜索根是否覆盖素材区，补 --img-root 后重跑。")
    return 1 if bad_count else 0


if __name__ == "__main__":
    sys.exit(main())
