#!/usr/bin/env python3
"""校验 v2 互动理解物是否符合风格基线的可检查结构。

md 源检查项（对应基线 v2 第七节）：
  1. 疑问句模块标题数量 3-7；五个固定块数量逐项相等
  2. 四层折叠契约：L1 mod = 模块数；L2 blk = 5×模块数；L3 sub 每模块 ≥3
  3. details 开闭配对、嵌套深度恰为 3、过程中深度不为负
  4. 全局导航三段齐全，前置概念与知识树均为折叠块，树节点可跳转到各模块
  5. 无外链、无盘符绝对路径

html 交付物检查项：
  1. data-lv 含 1/2/3 三级；details 开闭配对
  2. 四档展开控制条齐全；sub 标签真实渲染
  3. 无 http/https 外链、无裸 ** 或 ## 标记残留

仅用标准库，无网络、无写盘、无删除。退出码 0=全通过，1=有失败。
"""

import argparse
import re
import sys

BLOCKS = ["通俗直觉", "核心定义与对比", "硬核推导", "知识关联", "交互自测"]
NAV = ["一句话总结", "前置概念", "知识树状大纲"]
BUTTONS = ["仅主干", "展开到块", "全部展开", "全部收起"]


TOKEN = re.compile(r"<details(?:\s[^>]*)?>|</details>")


def depth_profile(text):
    """按标签 token 扫描（同一行可含多个 details），返回 (最大深度, 负深度?, 开数, 闭数)。"""
    depth = 0
    max_depth = 0
    negative = False
    opens = closes = 0
    for m in TOKEN.finditer(text):
        if m.group(0).startswith("</"):
            depth -= 1
            closes += 1
            if depth < 0:
                negative = True
        else:
            depth += 1
            opens += 1
            max_depth = max(max_depth, depth)
    return max_depth, negative, opens, closes


def check_md(text):
    reasons = []
    # v2：模块疑问句写在 L1 卡片 summary 中，不再是 ## 标题
    mod_n = len(re.findall(r'<details\s+class="mod"', text))
    modules = mod_n
    question_titles = len(re.findall(r"<summary>\[\[\d+\]\][^\n]*？[^\n]*· 结论：", text))
    counts = [len(re.findall(r"^### " + b, text, re.M)) for b in BLOCKS]
    nav_ok = all(x in text for x in NAV)

    max_depth, negative, d_open, d_close = depth_profile(text)
    blk_n = len(re.findall(r'<details\s+class="blk"', text))
    sub_n = len(re.findall(r'<details\s+class="sub"', text))
    nav_n = len(re.findall(r'<details\s+class="nav"', text))
    anchors = len(re.findall(r'id="m\d+"', text))
    jumps = len(re.findall(r"\]\(#m\d+\)", text))
    external = len(re.findall(r"https?://|(?<![A-Za-z])[A-Za-z]:[\\/](?!/)", text))

    # 每个模块内的 L3 细项数
    chunks = re.split(r'(?=^<details\s+class="mod")', text, flags=re.M)[1:]
    per_mod = [len(re.findall(r'<details\s+class="sub"', c)) for c in chunks]

    if not 3 <= modules <= 7:
        reasons.append(f"modules={modules} 不在 3-7")
    if not all(c == modules for c in counts):
        reasons.append(f"五块数量不齐 blocks={counts} modules={modules}")
    if not nav_ok:
        _missing = [x for x in NAV if x not in text]
        reasons.append("导航三段缺失，缺：" + "、".join(_missing))
    if d_open != d_close or negative or max_depth != 3:
        reasons.append(f"details 异常 open={d_open} close={d_close} maxdepth={max_depth} negative={negative}")
    if question_titles != modules:
        reasons.append(f"疑问句模块摘要 {question_titles} != modules={modules}")
    if blk_n != 5 * modules:
        reasons.append(f"L2 blk={blk_n} != 5×{modules}")
    if sub_n < 3 * modules or any(x < 3 for x in per_mod):
        reasons.append(f"L3 sub 不足 total={sub_n} per_mod={per_mod}")
    if nav_n < 2:
        reasons.append(f"折叠导航块不足 nav={nav_n}")
    if anchors != modules or jumps < modules:
        reasons.append(f"大纲跳转不齐 anchors={anchors} jumps={jumps} modules={modules}")
    if external:
        reasons.append(f"外链或盘符路径 {external} 处")

    detail = (
        f"modules={modules} blocks={counts} L1/L2/L3={mod_n}/{blk_n}/{sub_n} "
        f"per_mod={per_mod} depth={max_depth} details={d_open}/{d_close} "
        f"nav={nav_ok}/{nav_n} jumps={jumps} external={external}"
    )
    return not reasons, detail, reasons


def check_html(text):
    reasons = []
    max_depth, negative, d_open, d_close = depth_profile(text)
    lvs = set(re.findall(r'data-lv="([0-9]+)"', text))
    external = len(re.findall(r"https?://", text))
    bare = len(re.findall(r"(?<!<)\*\*[^*]+\*\*|^## ", text, re.M))

    if not {"1", "2", "3"}.issubset(lvs):
        reasons.append(f"data-lv 层级不全 {sorted(lvs)}")
    if d_open != d_close or negative:
        reasons.append(f"details 开闭异常 {d_open}/{d_close} negative={negative}")
    if any(b not in text for b in BUTTONS):
        reasons.append("四档展开控制条不齐")
    raw_notation = len(re.findall(r"_\(|\^\(", text))
    if raw_notation:
        reasons.append(f"未渲染的上下标记法 {raw_notation} 处")
    if external:
        reasons.append(f"外链 {external} 处")
    if bare:
        reasons.append(f"裸标记残留 {bare} 处")

    detail = (
        f"levels={sorted(lvs)} depth={max_depth} details={d_open}/{d_close} "
        f"buttons={sum(b in text for b in BUTTONS)}/4 sub={text.count('<sub>')} "
        f"raw_notation={raw_notation} external={external} bare={bare}"
    )
    return not reasons, detail, reasons


def main():
    ap = argparse.ArgumentParser(description="校验理解物结构（纯本地，无外发）")
    ap.add_argument("files", nargs="+", help="要校验的 .md 源或 .html 交付物")
    args = ap.parse_args()

    failed = False
    for path in args.files:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        ok, detail, reasons = check_html(text) if path.lower().endswith(".html") else check_md(text)
        name = path.replace("\\", "/").split("/")[-1]
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")
        for r in reasons:
            print(f"      - {r}")
        if not ok:
            failed = True
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
