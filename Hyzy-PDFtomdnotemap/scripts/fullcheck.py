#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全库终校：对概念笔记库做一次全量体检，输出 A（本次需关注）/ B（历史遗留）两类。

检查项：
  九小节顺序（容忍分隔符差异）/ 缺必备小节 / 图片断链 / wikilink 越界 /
  来源行 / 「多书对照」>=N 本 / 「插图」节内混入 H3 / 空文件

用法：
    python fullcheck.py --base "<库根>"
    python fullcheck.py --base "..." --hist "## <自定义对照节>" --min-books 2
    python fullcheck.py --base "..." --exclude "<归档区>" --exclude "<素材区>"

输出解读：
    A 类（需关注）= 缺陷里有「非历史成因」的篇目  -> 本次融合范围内必须修到 0
    B 类（历史遗留）= 缺陷全部由「口径确立前」的原因造成 -> 列表交用户裁定，不擅自批量改

安全说明：只读笔记与图片目录；不写任何文件；不联网；不删除任何文件。
"""
import argparse
import collections
import io
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
# 这些前缀的缺陷 = 历史成因（口径确立前的旧写法），归 B 类
LEGACY_PREFIX = ("历史写法", "多书对照仅", "非标准 H2", "旧分隔符写法")
# 辅助页/模板，不遵循概念笔记规范，跳过
AUX_HINTS = ("术语与资源对照", "术语对照", "README", "模板", "总览与分类索引", "概念地图")
MAP_HINTS = ("概念地图", "总览与分类索引", "总览", "索引")


def norm(s):
    return re.sub(r"[·/\s]", "", s)


def find_map(base, explicit):
    if explicit:
        return explicit if os.path.exists(explicit) else ""
    for f in sorted(os.listdir(base)):
        if f.endswith(".md") and any(h in f for h in MAP_HINTS):
            return os.path.join(base, f)
    return ""


def auto_img_roots(base):
    """默认把「库根 + 库的上一级」作为图片搜索根。

    短嵌入图片通常不在概念笔记目录内，而在同级/上层的素材区（<素材区>、<教材目录>等）。
    只搜库根会导致**全量假断图**（实测一次误报 178 篇）。上一级若已是盘根则不加。
    """
    roots = [base]
    parent = os.path.dirname(base)
    if parent and os.path.dirname(parent) != parent and os.path.isdir(parent):
        roots.append(parent)
    return roots


def main():
    ap = argparse.ArgumentParser(description="概念笔记库全量终校")
    ap.add_argument("--base", required=True, help="概念笔记库根目录")
    ap.add_argument("--map", default="", help="总索引文件（默认自动查找）")
    ap.add_argument("--sections", default="", help="覆盖必备小节（逗号分隔）")
    ap.add_argument("--optional", default="", help="可省略小节（逗号分隔）")
    ap.add_argument("--hist", action="append", default=[],
                    help="容忍的历史附加节（可重复），命中即标 legacy")
    ap.add_argument("--img-root", action="append", default=[],
                    help="图片搜索根（可重复；默认自动加入库根与其上一级）")
    ap.add_argument("--no-img-auto", action="store_true",
                    help="关闭图片根自动推断（只认 --img-root）")
    ap.add_argument("--extra-whitelist", action="append", default=[],
                    help="额外允许的 wikilink 目标（辅助页等，可重复）")
    ap.add_argument("--exclude", action="append", default=[],
                    help="跳过路径含此关键词的目录（可重复），如 <归档区>")
    ap.add_argument("--min-books", type=int, default=2,
                    help="「多书对照」至少几本书（默认2；设 0 关闭）")
    ap.add_argument("--book-regex", default=r"\b([A-Za-z]{1,3}\d{1,2})\b",
                    help="书目编号正则")
    ap.add_argument("--show-dup", type=int, default=10,
                    help="最多列出多少个被多篇引用的图片（0 关闭）")
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
    hist = set(args.hist)
    excluded = list(args.exclude)

    mapf = find_map(base, args.map)
    white = {"000-概念地图", "00-总览与分类索引"}
    if mapf:
        txt = open(mapf, encoding="utf-8", errors="replace").read()
        white |= set(re.findall(r"\[\[([^\]]+)\]\]", txt))
    else:
        print("⚠️ 未找到总索引，wikilink 越界检查只认 --extra-whitelist")
    white |= set(args.extra_whitelist)

    # 图片索引
    roots = ([] if args.no_img_auto else auto_img_roots(base)) + list(args.img_root)
    seen = set()
    roots = [r for r in roots if not (r in seen or seen.add(r))]
    imgs = set()
    for root in roots:
        if not os.path.isdir(root):
            print("⚠️ 图片根不存在，已跳过：%s" % root)
            continue
        for dp, dn, fn in os.walk(root):
            for f in fn:
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                    imgs.add(f)
    print("图片索引：%d 个文件，搜索根 %d 个" % (len(imgs), len(roots)))
    for r in roots:
        print("   · %s" % r)

    files = []
    for dp, dn, fn in os.walk(base):
        if any(k in dp for k in excluded):
            continue
        for f in sorted(fn):
            if not f.endswith(".md") or f.startswith("_"):
                continue
            if any(h in f for h in AUX_HINTS):
                continue
            files.append(os.path.join(dp, f))

    uses = collections.Counter()
    issues = []
    for p in sorted(files):
        rel = os.path.relpath(p, base)
        t = open(p, encoding="utf-8", errors="replace").read()
        bad = []
        if not t.strip():
            bad.append("空文件")
        hs = [l.strip() for l in t.split("\n") if l.startswith("## ")]
        seq = [h for h in hs if norm(h) in std_norm]
        seq_norm = [norm(h) for h in seq]
        renamed = [h for h in seq if h not in std]
        unknown = [h for h in hs if norm(h) not in std_norm and h not in hist]
        hit_hist = [h for h in hs if h in hist]
        if unknown:
            bad.append("非标准 H2 %s" % unknown)
        if hit_hist:
            bad.append("历史写法 %s" % hit_hist)
        if renamed:
            bad.append("旧分隔符写法 %s" % renamed)
        missing = [std[i] for i, n in enumerate(std_norm)
                   if n not in seq_norm and std[i] not in opt]
        if missing:
            bad.append("缺必备小节 %s" % missing)
        idxs = [std_norm.index(n) for n in seq_norm]
        if idxs != sorted(idxs):
            bad.append("小节顺序错乱")
        if not ("> 来源：" in t or re.search(r"^来源:", t, re.M)):
            bad.append("缺来源行")
        imgs_in = re.findall(r"!\[\[([^\]]+)\]\]", t)
        broken = [i for i in imgs_in if i not in imgs]
        if broken:
            bad.append("断图 %s" % broken[:3])
        for i in imgs_in:
            uses[i] += 1
        links = [l for l in re.findall(r"\[\[([^\]]+)\]\]", t) if l not in imgs_in]
        outside = sorted(set(l for l in links if l not in white))
        if outside:
            bad.append("越界链接 %s" % outside[:5])
        if args.min_books > 0:
            m = re.search(r"## 多书对照(.*?)(?=\n## |\Z)", t, re.S)
            if m:
                books = set(re.findall(args.book_regex, m.group(1)))
                if len(books) < args.min_books:
                    bad.append("多书对照仅 %s" % (sorted(books) or 0))
        mi = re.search(r"## 插图(.*?)(?=\n## |\Z)", t, re.S)
        if mi and re.search(r"^### ", mi.group(1), re.M):
            bad.append("插图节内含 H3")
        if bad:
            issues.append((rel, bad))

    A, B = [], []
    for rel, bad in issues:
        if all(b.startswith(LEGACY_PREFIX) for b in bad):
            B.append((rel, bad))
        else:
            A.append((rel, bad))

    print("\n全库概念笔记数: %d" % len(files))
    print("\n【A】本次融合范围内需关注: %d 篇" % len(A))
    for rel, bad in A:
        print("  ⚠️ %s\n      %s" % (rel, "; ".join(bad)))
    print("\n【B】历史遗留（口径确立前的旧写法）: %d 篇" % len(B))
    for rel, bad in B:
        print("  · %s\n      %s" % (rel, "; ".join(bad)))

    if args.show_dup:
        dup = sorted(((k, v) for k, v in uses.items() if v > 1), key=lambda x: -x[1])
        print("\n被多篇引用的图片: %d 个（同一图片服务多个概念属有意设计，不计入缺陷）" % len(dup))
        for k, v in dup[:args.show_dup]:
            print("   %s -> %d 次" % (k, v))

    print("\n结果: %s" % ("✅ 全库通过（A 类 0 篇）" if not A else "⚠️ A 类 %d 篇需修" % len(A)))
    broken_total = sum(1 for rel, bad in A for b in bad if b.startswith("断图"))
    if broken_total > 20:
        print("⚠️ 断图篇目偏多（%d 篇），**先怀疑图片搜索根没覆盖素材区**：" % broken_total)
        print("   核对上面的「搜索根」列表，必要时补 --img-root \"<素材目录>\"；")
        print("   若素材区与库不同盘/不同盘符层级，自动推断不会命中。")
    print("提示：B 类不得擅自批量改，须列清单交用户裁定。")
    return 1 if A else 0


if __name__ == "__main__":
    sys.exit(main())
