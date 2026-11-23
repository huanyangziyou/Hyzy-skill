#!/usr/bin/env python3
"""把 v1 平铺理解物 md 无损改写为 v2 四层折叠结构。

只做结构重排，不改动正文内容：原句、表格、公式记法、SVG 全部原样保留。
用于把 2026-11-23 之前生成的 v1 产物升级到风格基线 v2。

用法：python upgrade_v1_to_v2.py <file.md> [--out <dest.md>]

仅用标准库，无网络、无写盘副作用（除显式 --out 或同名覆盖目标）、无删除。
"""

import argparse
import re
import sys

BLOCKS = ["通俗直觉", "核心定义与对比", "硬核推导", "知识关联", "交互自测"]
BADGE = {"通俗直觉": "直觉", "核心定义与对比": "定义", "硬核推导": "推导",
         "知识关联": "关联", "交互自测": "自测"}
CN_NUM = "一二三四五六七"

# 自动摘要过弱时的人工覆盖键：(文件名, 模块序号) -> 结论句
OVERRIDES = {
    ("验证-MOSFET双网局部学习.md", 4): "输出、钳位、乘法器、栅压逐项标定后再开环",
    ("验证-MOSFET双网局部学习.md", 6): "按三项实验逐关留证，禁学对照同等时长",
    ("验证-参考文档互动理解物.md", 2): "想要什么交互就点名，不点名只给默认值",
    ("验证-参考文档互动理解物.md", 4): "锁定来源集合，内容只在来源内生成",
    ("验证-参考文档互动理解物.md", 5): "只有公网一键托管分享没有本地等价",
    ("验证-参考文档互动理解物.md", 6): "把托管网页换成自包含本地文件，内核不变",
    ("验证-差分电导网络.md", 1): "电容存状态与权重，两次稳态之差驱动更新",
    ("验证-差分电导网络.md", 4): "自由相与教学相的端点乘积比较后冻结权重",
    ("验证-差分电导网络.md", 5): "势差与预测误差不总一致，必须分开报告",
    ("验证-差分电导网络.md", 6): "数值核验只验公式符号，不验接线与实物",
    ("验证-留出RBM原位学习.md", 1): "方案停在纸上，首板器件与节点数尚未定",
    ("验证-留出RBM原位学习.md", 2): "五模块各自单独验，三类量不可混读",
    ("验证-留出RBM原位学习.md", 5): "先交三条电路行为曲线，再谈扩规模",
    ("验证-量子力学表象.md", 2): "坐标与动量波函数由傅里叶变换唯一互求",
    ("验证-量子力学表象.md", 4): "平均值、本征值与薛定谔方程均可代数化",
    ("示范-带图形层理解物.md", 2): "坐标与动量波函数由傅里叶变换唯一互求",
    ("示范-带图形层理解物.md", 4): "平均值、本征值与薛定谔方程均可代数化",
}


def sentences(text):
    parts = re.split(r"(?<=[。！？；])", " ".join(text.split()))
    return [p.strip() for p in parts if p.strip()]


def clip(text, n=40):
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= n else text[:n - 1] + "…"


def safe_clip(text, n=26):
    """摘要截断时不在上下标记法或行内码中间断开。"""
    out = clip(text, n)
    for mk in ("_(", "^("):
        p = out.rfind(mk)
        if p >= 0 and ")" not in out[p:]:
            out = out[:p]
    if out.count("`") % 2:
        out = out[:out.rfind("`")]
    out = out.rstrip("，。；、· …`")
    return out or clip(text, 20)


def block_body(section, name):
    """取某个 ### 块的正文（不含标题），返回行列表。"""
    m = re.search(r"^### " + re.escape(name) + r"\s*\n(.*?)(?=^### |\Z)",
                  section, re.M | re.S)
    if not m:
        return []
    lines = m.group(1).splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def unwrap_details(lines):
    """剥掉 v1 的 <details><summary>…</summary> 外壳，取回正文行。"""
    out = []
    for ln in lines:
        s = ln.strip()
        if s in ("<details>", "</details>") or s.startswith("<summary>"):
            continue
        out.append(ln)
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return out


def table_rows(lines):
    rows = []
    for ln in lines:
        s = ln.strip()
        if not s.startswith("|") or re.fullmatch(r"[|:\-\s]+", s):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        rows.append(cells)
    return rows


def split_derivation(lines):
    """按行数中点切成两段，保持原顺序，不丢行。"""
    if not lines:
        return [], []
    k = max(1, (len(lines) + 1) // 2)
    return lines[:k], lines[k:]


def conclusion_for(section, name, idx):
    if (name, idx) in OVERRIDES:
        return OVERRIDES[(name, idx)]
    ss = sentences("\n".join(block_body(section, "通俗直觉")))
    cand = ss[-1] if ss else "见本模块正文"
    cand = re.sub(r"^换尺子的好处很实际：", "", cand)
    return safe_clip(cand, 42)


def build_block(section, name):
    raw = block_body(section, name)
    subs = []          # (title, lines)
    if name == "核心定义与对比":
        tbl_end = 0
        for i, ln in enumerate(raw):
            if ln.strip().startswith("|"):
                tbl_end = i
        tail = raw[tbl_end + 1:]
        body = raw[:tbl_end + 1]
        if any(x.strip() for x in tail):
            subs.append(("例外与易混点", tail))
    elif name == "硬核推导":
        inner = unwrap_details(raw)
        a, b = split_derivation(inner)
        if a:
            subs.append(("步骤与公式", a))
        if b:
            subs.append(("结论与边界条件", b))
        body = []
        raw = inner  # 摘要只取正文，不带 v1 的 <details>/<summary> 外壳
    elif name == "交互自测":
        question = [ln for ln in raw if ln.strip().startswith("**思考题**")]
        body = question
        rows = table_rows(raw)
        for i, r in enumerate(rows[1:], 1):
            if len(r) >= 2:
                subs.append((f"闪卡 {i}：{clip(r[0], 34)}", [r[1]]))
    else:
        body = raw

    # 摘要行：用正文首句做短提示，不用空话
    flat = " ".join(" ".join(x.split()) for x in (body or raw) if x.strip())
    first = sentences(flat)
    if name == "交互自测":
        hint = f"1 道思考题 + {len(subs)} 张闪卡"
    elif name == "核心定义与对比":
        n = max(0, len(table_rows(raw)) - 1)
        hint = f"横向对比 {n} 种概念" if n else (safe_clip(first[0], 24) if first else "见正文")
    elif first:
        hint = safe_clip(first[0].replace("|", ""), 26)
    else:
        hint = "见正文"

    badge = (f"[[推导×{len(subs)}]]" if name == "硬核推导" and subs
             else f"[[自测×{len(subs)}]]" if name == "交互自测" and subs
             else f"[[{BADGE[name]}]]")

    out = [f'<details class="blk">', f"<summary>{badge} {hint}</summary>", ""]
    out += [f"### {name}", ""]
    out += body
    if body and subs:
        out.append("")
    for title, sub_lines in subs:
        out += ["<details class=\"sub\">", f"<summary>{title}</summary>", ""]
        out += sub_lines
        out += ["", "</details>", ""]
    out += ["</details>", ""]
    return out, len(subs)


def build_nav(text, modules):
    m_sum = re.search(r"\*\*一句话总结\*\*：(.*)", text)
    summary = m_sum.group(1).strip() if m_sum else "见正文"
    pre_block = re.search(r"\*\*前置概念\*\*：\s*\n(.*?)(?=\*\*知识树状大纲\*\*)", text, re.S)
    pre_lines = [ln for ln in (pre_block.group(1).splitlines() if pre_block else []) if ln.strip()]

    out = ["## 全局导航", "", f"**一句话总结**：{summary}", "",
           f"**前置概念**：", "",
           f'<details class="nav">', f"<summary>前置概念（{len(pre_lines)} 条）— 点开查看</summary>", ""]
    out += pre_lines or ["- 无"]
    out += ["", "</details>", "", "**知识树状大纲**：", "",
            '<details class="nav">',
            f"<summary>知识树（{len(modules)} 模块）— 点开跳转</summary>", ""]
    for i, title in enumerate(modules, 1):
        t = re.sub(r"^[" + CN_NUM + r"]、", "", title)
        out.append(f"- [{t}](#m{i})")
        out.append("  - 通俗直觉 / 核心定义与对比 / 硬核推导 / 知识关联 / 交互自测")
    out += ["", "</details>", ""]
    return out


def convert(text, filename):
    lines = text.splitlines()
    title = re.search(r"^#\s+(.+)", text, re.M)
    page_title = re.sub(r"（v1[^）]*）", "", title.group(1).strip()) if title else "理解物"
    orig_note = re.search(r"^> 依据风格基线 v1 生成。(.*)$", text, re.M)
    note = orig_note.group(1).strip() if orig_note else "源资料见正文引用。"

    sections = re.split(r"(?=^## [" + CN_NUM + r"]、)", text, flags=re.M)
    modules = []
    for s in sections:
        m = re.match(r"^## ([" + CN_NUM + r"]、.*？)\s*$", s, re.M)
        if m:
            modules.append((m.group(1).strip(), s))

    graph = re.search(r"^## 图形层.*?(?=^## [" + CN_NUM + r"]、)", text, re.M | re.S)
    graph_text = graph.group(0).rstrip() if graph else ""

    out = [f"# {page_title}（v2）", "", "> 依据风格基线 v2 生成。" + note, "", "---", ""]
    out += build_nav(text, [t for t, _ in modules])
    if graph_text:
        out += ["---", "", graph_text, ""]
    out += ["---", ""]

    for i, (mod_title, sec) in enumerate(modules, 1):
        short = re.sub(r"^[" + CN_NUM + r"]、", "", mod_title)
        concl = conclusion_for(sec, filename, i)
        badge_counts = {}
        block_out = []
        for name in BLOCKS:
            b, n = build_block(sec, name)
            block_out += b
            badge_counts[name] = n
        summary = (f"[[{i:02d}]] {short} · 结论：{concl} "
                   f"[[直觉]][定义][推导×{badge_counts['硬核推导']}]"
                   f"[关联][自测×{badge_counts['交互自测']}]]")
        out += [f'<details class="mod" id="m{i}">', f"<summary>{summary}</summary>", ""]
        out += block_out
        out += ["</details>", "", "---", ""]

    foot = re.search(r"^## 生成说明（验收用）.*", text, re.M | re.S)
    if foot:
        out += [foot.group(0).replace("基线 v1", "基线 v2").rstrip(), ""]
    return "\n".join(out).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser(description="v1 理解物 md 无损升级到 v2 四层折叠（纯本地）")
    ap.add_argument("files", nargs="+", help="要升级的 .md 文件")
    ap.add_argument("--out", default="", help="输出文件；省略则覆盖同名源文件")
    args = ap.parse_args()

    import os
    for path in args.files:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        name = os.path.basename(path)
        result = convert(text, name)
        dest = args.out or path
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(result)
        print(f"OK  {path} -> {dest}  ({len(result)} chars)", file=sys.stderr)


if __name__ == "__main__":
    main()
