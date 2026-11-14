#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hyzy-HDLtoSVG&Explain -- SVG / Markdown 渲染规范校验器

用途：在交付「代码 -> SVG 图形化链路 + 解释文档」的 md 之前，一次性扫出会返工的硬问题。

用法：
    python validate_svg.py <路径.md 或 路径.svg> [...]     # 校验指定文件
    python validate_svg.py --dir <目录>                     # 扫目录下所有 .md / .svg
    python validate_svg.py <路径> -q                        # 静默通过项，只列问题

退出码：0 = 无 ERROR（可有 WARN）；1 = 存在 ERROR；2 = 参数或文件问题

检查项：
  E1  viewBox 宽度不是 680（宿主会拒绝渲染，最高频返工原因）
  E2  缺少 width="100%"
  E3  缺少 role="img"
  E4  缺少 <title> 或 <desc>
  E5  标签不闭合 / 交叉嵌套
  E6  url(#id) 引用的 id 未在 <defs> 中定义
  E7  使用了 marker 却没有 <defs>
  E8  rect / line 坐标越出 0~680 画布（水平方向）
  E9  md 里出现 <!DOCTYPE>/<html>/<body>（宿主只吃裸 SVG 片段）
  E10 <svg> / </svg> 数量不匹配，或某个 <svg> 提前闭合导致图形元素落在 svg 之外
  W1  文本出现字面下标（u_c / u_{c} / LaTeX 命令）——应改用 tspan baseline-shift
  W2  文本估算宽度溢出所属矩形
  W3  文本估算宽度溢出画布
  W4  使用了规范色板之外的颜色
  W5  疑似流程节点数 > 14（建议拆图）
  W6  md 缺 H1 / 缺 H2 分节 / 无 svg 块
  W7  残留占位符（TODO / FIXME / xxx / ???）

说明：宽度为**估算值**（CJK 按 1.0em、其余按 0.55em）。W2/W3 是提示，可能需要人工确认；
E 级问题必须修完再交付。
"""

import os
import re
import sys

VIEWBOX_W = 680.0
CANVAS_RIGHT = 680.0
TEXT_RIGHT_PADDING = 8.0

# 规范色板（按职责分段，见 SKILL.md 3.3）
PALETTE_PRIMARY = {
    "#E6F1FB", "#185FA5", "#0C447C",   # 接收/物理段
    "#E1F5EE", "#0F6E56", "#085041",   # 处理段
    "#FAEEDA", "#854F0B", "#633806",   # 存取段
    "#F1EFE8", "#5F5E5A", "#444441",   # 存储/外部
    "#EEEDFE", "#534AB7", "#3C3489",   # 输出段
    "#888780",                          # 箭头/连线
}
# 扩展容差色（教材电路图口径 + 通用中性色，不报警）
PALETTE_TOLERATED = {
    "#FFFFFF", "#FFF", "#000000", "#000", "#B9C2D0", "#C83C3C",
    "#7846AA", "#536DAA", "#888",
}

TAG_RE = re.compile(r'<\s*(/?)\s*([A-Za-z][\w:.\-]*)((?:"[^"]*"|\'[^\']*\'|[^>"\'])*?)(/?)\s*>', re.S)
VOID_TAGS = {"path", "line", "rect", "circle", "ellipse", "polygon", "polyline", "use", "stop", "image"}
SVG_BLOCK_RE = re.compile(r'<svg\b.*?</svg>', re.S | re.I)
# 图形元素：用于判断某个 <svg> 块是不是"空壳"（只有 title/desc/defs）
SHAPE_TAG_RE = re.compile(
    r"<(rect|circle|ellipse|line|polyline|polygon|path|text|tspan|g|image|use|foreignObject)\b",
    re.I)


class Issue:
    __slots__ = ("level", "code", "line", "msg")

    def __init__(self, level, code, line, msg):
        self.level = level      # "ERROR" / "WARN"
        self.code = code
        self.line = line
        self.msg = msg

    def __str__(self):
        loc = ("第 %d 行 " % self.line) if self.line else ""
        return "[%-5s] %-3s %s%s" % (self.level, self.code, loc, self.msg)


# ---------------------------------------------------------------- 工具函数

def line_of(content, pos):
    return content.count("\n", 0, pos) + 1


def attr(tag_text, name, default=None):
    m = re.search(r'\b%s\s*=\s*"([^"]*)"' % re.escape(name), tag_text)
    if not m:
        m = re.search(r"\b%s\s*=\s*'([^']*)'" % re.escape(name), tag_text)
    return m.group(1) if m else default


def fnum(tag_text, name, default=0.0):
    v = attr(tag_text, name)
    if v is None:
        return default
    try:
        return float(re.sub(r"[^0-9eE+\-.]", "", v))
    except ValueError:
        return default


def unescape(s):
    return (s.replace("&lt;", "<").replace("&gt;", ">")
             .replace("&quot;", '"').replace("&apos;", "'").replace("&amp;", "&"))


def strip_tags(s):
    return unescape(re.sub(r"<[^>]*>", "", s))


def est_width(s, size):
    """估算文本渲染宽度（保守偏大，宁可误报不漏报）。"""
    w = 0.0
    for ch in s:
        o = ord(ch)
        if o >= 0x2E80 or o in (0x00B7, 0x2013, 0x2014):
            w += size            # CJK / 全角 / 间隔号
        elif ch == " ":
            w += size * 0.28
        else:
            w += size * 0.55     # ASCII
    return w


def text_width(inner, base_size):
    total = 0.0
    pos = 0
    for m in re.finditer(r"<tspan([^>]*)>(.*?)</tspan>", inner, re.S):
        total += est_width(strip_tags(inner[pos:m.start()]), base_size)
        fs = attr(m.group(1), "font-size")
        try:
            size = float(re.sub(r"[^0-9.]", "", fs)) if fs else base_size
        except ValueError:
            size = base_size
        total += est_width(strip_tags(m.group(2)), size)
        pos = m.end()
    total += est_width(strip_tags(inner[pos:]), base_size)
    return total


# ---------------------------------------------------------------- 单项检查

def check_svg(content, svg, base_pos, issues):
    def rep(code, pos, msg, level="ERROR"):
        issues.append(Issue(level, code, line_of(content, base_pos + pos), msg))

    def fpos(sub):
        i = svg.find(sub)
        return i if i >= 0 else 0

    body = re.sub(r"<!--.*?-->", "", svg, flags=re.S)

    # --- E1 viewBox 宽度
    mv = re.search(r'viewBox\s*=\s*"([^"]+)"', svg)
    if not mv:
        rep("E1", 0, "缺少 viewBox（必须为 viewBox=\"0 0 680 H\"）")
    else:
        parts = re.split(r"[\s,]+", mv.group(1).strip())
        try:
            w = float(parts[2])
        except (IndexError, ValueError):
            rep("E1", mv.start(), "viewBox 无法解析：%r" % mv.group(1))
        else:
            if abs(w - VIEWBOX_W) > 0.5:
                rep("E1", mv.start(),
                    "viewBox 宽度为 %g，必须是 680（宿主会拒绝渲染）" % w)

    # --- E2 width="100%" / E3 role="img" / E4 title|desc
    svg_tag = svg[:svg.find(">") + 1]
    if not re.search(r'width\s*=\s*"100%"', svg_tag):
        rep("E2", 0, "根 <svg> 缺少 width=\"100%\"")
    if not re.search(r'role\s*=\s*"img"', svg_tag):
        rep("E3", 0, "根 <svg> 缺少 role=\"img\"（无障碍属性）")
    if not re.search(r"<title\b", body, re.I):
        rep("E4", 0, "缺少 <title>")
    if not re.search(r"<desc\b", body, re.I):
        rep("E4", 0, "缺少 <desc>")

    # --- E5 标签闭合
    stack = []
    for m in TAG_RE.finditer(body):
        closing, name, _attrs, selfclose = m.group(1), m.group(2).lower(), m.group(3), m.group(4)
        if name in ("br",):
            continue
        if closing:
            if not stack:
                rep("E5", m.start(), "多余的闭合标签 </%s>" % name)
            elif stack[-1][0] != name:
                rep("E5", m.start(), "标签交叉嵌套：期望 </%s>，实际 </%s>" % (stack[-1][0], name))
                while stack and stack[-1][0] != name:
                    stack.pop()
                if stack:
                    stack.pop()
            else:
                stack.pop()
        elif selfclose or name in VOID_TAGS:
            continue
        else:
            stack.append((name, m.start()))
    for name, pos in stack:
        rep("E5", pos, "标签 <%s> 未闭合" % name)

    # --- E6/E7 marker 与 url(#id)
    refs = set(re.findall(r"url\(\s*#([^)\s]+)\s*\)", body))
    ids = set(re.findall(r'\bid\s*=\s*"([^"]+)"', body))
    if refs:
        if not re.search(r"<defs\b", body, re.I):
            rep("E7", 0, "使用了 url(#%s) 但没有 <defs> 定义区" % sorted(refs)[0])
        missing = sorted(refs - ids)
        if missing:
            rep("E6", 0, "url(#%s) 引用的 id 未定义" % ", #".join(missing))

    # --- E8 坐标越界 + 收集矩形（给 W2 用）
    rects = []
    for m in re.finditer(r"<rect\b((?:\"[^\"]*\"|'[^']*'|[^>\"'])*?)/?>", body, re.S):
        t = m.group(1)
        x, y = fnum(t, "x"), fnum(t, "y")
        w, h = fnum(t, "width"), fnum(t, "height")
        rects.append((x, y, w, h))
        if x < -0.01 or x + w > CANVAS_RIGHT + 0.01:
            rep("E8", m.start(), "rect 水平越界：x=%g + width=%g 超出 0~680" % (x, w))
        if y < -0.01:
            rep("E8", m.start(), "rect 的 y=%g 为负" % y)
    for m in re.finditer(r"<line\b((?:\"[^\"]*\"|'[^']*'|[^>\"'])*?)/?>", body, re.S):
        t = m.group(1)
        for k in ("x1", "x2"):
            v = fnum(t, k)
            if v < -0.01 or v > CANVAS_RIGHT + 0.01:
                rep("E8", m.start(), "line 的 %s=%g 越出 0~680" % (k, v))

    # --- W1 字面下标（只抓短标识，避免误伤 I_clk_hs_p 这类合法信号名）
    lit_sub = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]_[A-Za-z0-9](?![A-Za-z0-9_])")
    for m in re.finditer(r"<text\b[^>]*>(.*?)</text>", body, re.S):
        raw = m.group(1)
        plain = strip_tags(raw)
        if lit_sub.search(plain):
            rep("W1", m.start(), "文本含字面下标「%s」——应改用 "
                                 "<tspan baseline-shift=\"sub\">" % lit_sub.search(plain).group(0),
                "WARN")
        if re.search(r"\\[A-Za-z]+|_\{", plain):
            rep("W1", m.start(), "文本含 LaTeX 残留（%s）——SVG 不渲染 LaTeX"
                % re.search(r"\\[A-Za-z]+|_\{", plain).group(0), "WARN")

    # --- W2/W3 文本溢出
    for m in re.finditer(r"<text\b((?:\"[^\"]*\"|'[^']*'|[^>\"'])*?)>(.*?)</text>", body, re.S):
        t, inner = m.group(1), m.group(2)
        x = fnum(t, "x")
        y = fnum(t, "y")
        fs = attr(t, "font-size")
        try:
            size = float(re.sub(r"[^0-9.]", "", fs)) if fs else 12.0
        except ValueError:
            size = 12.0
        w = text_width(inner, size)
        anchor = (attr(t, "text-anchor") or "start").lower()
        start = x - w / 2.0 if anchor == "middle" else (x - w if anchor == "end" else x)
        right = start + w

        if right > CANVAS_RIGHT:
            rep("W3", m.start(), "文本估算宽 %.0fpx，右端到 %.0f（超出画布 %.0fpx）：%s"
                % (w, right, right - CANVAS_RIGHT, strip_tags(inner)[:36]), "WARN")
            continue
        holder = None
        for (rx, ry, rw, rh) in rects:
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                if holder is None or rw < holder[2]:
                    holder = (rx, ry, rw, rh)
        if holder is not None:
            limit = holder[0] + holder[2] - TEXT_RIGHT_PADDING
            if right > limit:
                rep("W2", m.start(), "文本溢出所在矩形 %.0fpx（右端 %.0f > 边界 %.0f）：%s"
                    % (right - limit, right, limit, strip_tags(inner)[:36]), "WARN")

    # --- W4 非规范色
    colors = set()
    for m in re.finditer(r'(?:fill|stroke)\s*=\s*"([^"]+)"', body):
        colors.add(m.group(1).strip().upper())
    for c in sorted(colors):
        if c in ("NONE", "CURRENTCOLOR", "CONTEXT-STROKE") or c.startswith("URL("):
            continue
        if c in PALETTE_PRIMARY or c in PALETTE_TOLERATED:
            continue
        rep("W4", 0, "使用了规范色板之外的颜色 %s" % c, "WARN")

    # --- W5 节点数
    node_like = [r for r in rects if r[2] >= 100]
    if len(node_like) > 14:
        rep("W5", 0, "疑似流程节点 %d 个（>14），建议拆图，不要硬塞" % len(node_like), "WARN")


def check_md(content, issues):
    total_lines = content.count("\n") + 1
    if not re.search(r"^#\s+\S", content, re.M):
        issues.append(Issue("WARN", "W6", 0, "md 缺少 H1 标题"))
    h2 = len(re.findall(r"^##\s+\S", content, re.M))
    blocks = list(SVG_BLOCK_RE.finditer(content))
    if not blocks:
        issues.append(Issue("WARN", "W6", 0, "md 内没有找到 <svg> 块"))
    if h2 < 3:
        issues.append(Issue("WARN", "W6", 0, "md 仅 %d 个 H2 分节，解释文档通常需要 3 节以上" % h2))
    for m in re.finditer(r"<!DOCTYPE|<html\b|<body\b", content, re.I):
        issues.append(Issue("ERROR", "E9", line_of(content, m.start()),
                            "md 内出现 %s——宿主只接受裸 <svg> 片段" % m.group(0)))
    for m in re.finditer(r"\bTODO\b|\bFIXME\b|\bxxx\b|\?\?\?", content):
        issues.append(Issue("WARN", "W7", line_of(content, m.start()),
                            "残留占位符 %r" % m.group(0)))

    # E10：<svg> / </svg> 配对，以及"提前闭合"（图形掉在 svg 之外 -> 渲染成裸文本）
    n_open = len(re.findall(r"<svg\b", content, re.I))
    n_close = len(re.findall(r"</svg\s*>", content, re.I))
    if n_open != n_close:
        issues.append(Issue("ERROR", "E10", 0,
                            "<svg> 开标签 %d 个 与 </svg> 闭标签 %d 个不匹配——多出的 </svg> "
                            "会把后面的图形元素挤出 svg 之外" % (n_open, n_close)))
    for i, b in enumerate(blocks):
        if SHAPE_TAG_RE.search(b.group(0)):
            continue                      # 块内已有图形，正常
        # 本块是"空壳"：看它之后到下一个 <svg>（或文件尾）之间有没有孤儿图形
        gap_start = b.end()
        gap_end = blocks[i + 1].start() if i + 1 < len(blocks) else len(content)
        gap = re.sub(r"<!--.*?-->", "", content[gap_start:gap_end], flags=re.S)
        m = SHAPE_TAG_RE.search(gap)
        if m:
            issues.append(Issue("ERROR", "E10", line_of(content, gap_start + m.start()),
                                "第 %d 个 <svg> 块疑似提前闭合：其后的 <%s> 落在 svg 元素之外，"
                                "不会被当作图形渲染" % (i + 1, m.group(1))))

    del total_lines
    return blocks


# ---------------------------------------------------------------- 主流程

def validate_file(path, quiet=False):
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            content = f.read()
    except OSError as e:
        print("  ! 无法读取：%s" % e)
        return 1

    issues = []
    is_md = path.lower().endswith((".md", ".markdown"))

    if is_md:
        blocks = check_md(content, issues)
        for b in blocks:
            check_svg(content, b.group(0), b.start(), issues)
    else:
        for m in SVG_BLOCK_RE.finditer(content):
            check_svg(content, m.group(0), m.start(), issues)

    errors = [i for i in issues if i.level == "ERROR"]
    warns = [i for i in issues if i.level == "WARN"]

    print("\n=== %s ===" % path)
    if is_md:
        print("  md 结构：%d 个 svg 块 / %d 个 H2 分节"
              % (len(SVG_BLOCK_RE.findall(content)), len(re.findall(r"^##\s+\S", content, re.M))))
    if not issues:
        if not quiet:
            print("  OK - 未发现问题")
    else:
        for i in issues:
            print("  " + str(i))
    if not quiet or issues:
        print("  小结：%d 个错误，%d 个警告" % (len(errors), len(warns)))
    return 1 if errors else 0


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("-")]
    quiet = any(a in ("-q", "--quiet") for a in argv[1:])
    targets = []

    if "--dir" in argv[1:]:
        idx = argv.index("--dir")
        if idx + 1 >= len(argv):
            print("用法：--dir <目录>")
            return 2
        root = argv[idx + 1]
        if not os.path.isdir(root):
            print("不是目录：%s" % root)
            return 2
        for dirpath, _dirs, files in os.walk(root):
            for fn in sorted(files):
                if fn.lower().endswith((".md", ".svg")):
                    targets.append(os.path.join(dirpath, fn))
        args = [a for a in args if a != root]
    else:
        targets = args

    if not targets:
        print(__doc__)
        return 2

    rc = 0
    for t in targets:
        if not os.path.isfile(t):
            print("\n=== %s ===\n  ! 文件不存在" % t)
            rc = 2
            continue
        if validate_file(t, quiet) and rc == 0:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
