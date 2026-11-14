#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hyzy-KnowtoMethPath -- 方法路径文档校验器

用途：在交付「知识 -> 方法路径文档」之前，一次性扫出会返工的结构 / SVG / LaTeX / 表格问题。

用法：
    python verify_methpath.py <文档.md>            # 校验单篇
    python verify_methpath.py --dir <目录>          # 扫目录下所有 .md（跳过 _verify-log.md）
    python verify_methpath.py <文档.md> -q          # 静默通过项，只列问题
    python verify_methpath.py <文档.md> --json      # 输出 JSON（供其他工具消费）

退出码：0 = 无 ERROR（可有 WARN）；1 = 存在 ERROR；2 = 参数或文件问题

检查项（E = ERROR 必须清零，W = WARN 人工判断）：
  E1   viewBox 宽度不是 680（宿主会拒绝渲染）
  E2   根 <svg> 缺 width="100%"
  E3   根 <svg> 缺 role="img"
  E4   SVG 标签不闭合 / 交叉嵌套
  E5   rect / line 水平越出 0~680，或 y 为负
  E6   md 内出现 <!DOCTYPE> / <html> / <body>（宿主只吃裸 SVG 片段）
  E7   <svg> 与 </svg> 数量不匹配
  E8   md 缺少 H1 标题
  E9   $$ 数量为奇数（公式块未闭合）
  E10  表格各行列数不一致
  E11  表格的公式内出现裸竖线 | （应写 \\lvert ... \\rvert）
  E12  总览表中的路径字母在正文无对应「路径 X」章节
  E13  总览表中的子类型（A1/A2…）在正文无对应 ### 标题
  E14  ## N. 章节编号不连续 / 跳号 / 重号
  E15  \\begin{} 与 \\end{} 数量不匹配，或存在嵌套 cases
  E16  子类型标题格式不合规（应为 "### A1 名称"，不带章节数字前缀）
  W1   文本估算宽度溢出所在矩形
  W2   缺少「路径总览」表（表头需含：路径 + 触发条件）
  W3   缺少「判定链」表（表头需含：步 + 判据）
  W4   案例小节内缺少 \\boxed 结果
  W5   <svg> 缺 <title> 或 <desc>
  W6   案例数少于子类型数（覆盖不全）
  W7   残留占位符（TODO / FIXME / xxx / ???）
  W8   文件不在 ".../method path/" 目录下

说明：文本宽度为**估算值**（CJK 1.0em、ASCII 0.55em、空格 0.28em），保守偏大；
W1 命中后需人工看一眼，E 级问题必须修完再交付。
"""

import json
import os
import re
import sys

CANVAS_W = 680.0
PAD = 8.0

TAG_RE = re.compile(r'<\s*(/?)\s*([A-Za-z][\w:.\-]*)((?:"[^"]*"|\'[^\']*\'|[^>"\'])*?)(/?)\s*>', re.S)
VOID_TAGS = {"path", "line", "rect", "circle", "ellipse", "polygon", "polyline",
             "use", "stop", "image"}
CONTAINER_TAGS = {"svg", "defs", "marker", "g", "text", "tspan", "title", "desc"}
SVG_BLOCK_RE = re.compile(r'<svg\b.*?</svg>', re.S | re.I)
SHAPE_RE = re.compile(r"<(rect|circle|ellipse|line|polyline|polygon|path|text|g|image|use)\b", re.I)


class Issue:
    __slots__ = ("level", "code", "line", "msg")

    def __init__(self, level, code, line, msg):
        self.level, self.code, self.line, self.msg = level, code, line, msg

    def __str__(self):
        loc = ("第 %d 行 " % self.line) if self.line else ""
        return "[%-5s] %-4s %s%s" % (self.level, self.code, loc, self.msg)

    def as_dict(self):
        return {"level": self.level, "code": self.code, "line": self.line, "msg": self.msg}


# ------------------------------------------------------------------ 基础工具

def line_of(content, pos):
    return content.count("\n", 0, pos) + 1


def attr(tag, name, default=None):
    m = re.search(r'\b%s\s*=\s*"([^"]*)"' % re.escape(name), tag)
    if not m:
        m = re.search(r"\b%s\s*=\s*'([^']*)'" % re.escape(name), tag)
    return m.group(1) if m else default


def fnum(tag, name, default=0.0):
    v = attr(tag, name)
    if v is None:
        return default
    try:
        return float(re.sub(r"[^0-9eE+\-.]", "", v))
    except ValueError:
        return default


def strip_tags(s):
    s = (s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
          .replace("&apos;", "'").replace("&amp;", "&"))
    return re.sub(r"<[^>]*>", "", s)


def est_width(s, size):
    w = 0.0
    for ch in s:
        if ord(ch) >= 0x2E80:
            w += size
        elif ch == " ":
            w += size * 0.28
        else:
            w += size * 0.55
    return w


def text_width(inner, base):
    total, pos = 0.0, 0
    for m in re.finditer(r"<tspan([^>]*)>(.*?)</tspan>", inner, re.S):
        total += est_width(strip_tags(inner[pos:m.start()]), base)
        fs = attr(m.group(1), "font-size")
        try:
            size = float(re.sub(r"[^0-9.]", "", fs)) if fs else base
        except ValueError:
            size = base
        total += est_width(strip_tags(m.group(2)), size)
        pos = m.end()
    total += est_width(strip_tags(inner[pos:]), base)
    return total


# ------------------------------------------------------------------ SVG 检查

def check_svg(content, svg, base_pos, issues):
    def rep(code, pos, msg, level="ERROR"):
        issues.append(Issue(level, code, line_of(content, base_pos + pos), msg))

    body = re.sub(r"<!--.*?-->", "", svg, flags=re.S)

    # E1 viewBox
    mv = re.search(r'viewBox\s*=\s*"([^"]+)"', svg)
    if not mv:
        rep("E1", 0, '缺少 viewBox（必须为 viewBox="0 0 680 H"）')
    else:
        parts = re.split(r"[\s,]+", mv.group(1).strip())
        try:
            w = float(parts[2])
        except (IndexError, ValueError):
            rep("E1", mv.start(), "viewBox 无法解析：%r" % mv.group(1))
        else:
            if abs(w - CANVAS_W) > 0.5:
                rep("E1", mv.start(), "viewBox 宽度 %g，必须为 680" % w)

    # E2 / E3 / W5
    head = svg[:svg.find(">") + 1]
    if not re.search(r'width\s*=\s*"100%"', head):
        rep("E2", 0, '根 <svg> 缺 width="100%"')
    if not re.search(r'role\s*=\s*"img"', head):
        rep("E3", 0, '根 <svg> 缺 role="img"')
    if not re.search(r"<title\b", body, re.I):
        rep("W5", 0, "缺 <title>", "WARN")
    if not re.search(r"<desc\b", body, re.I):
        rep("W5", 0, "缺 <desc>", "WARN")

    # E4 标签闭合
    stack = []
    for m in TAG_RE.finditer(body):
        closing, name, selfclose = m.group(1), m.group(2).lower(), m.group(4)
        if name == "br":
            continue
        if closing:
            if not stack:
                rep("E4", m.start(), "多余的闭合标签 </%s>" % name)
            elif stack[-1][0] != name:
                rep("E4", m.start(), "标签交叉嵌套：期望 </%s>，实际 </%s>" % (stack[-1][0], name))
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
        rep("E4", pos, "标签 <%s> 未闭合" % name)

    # E5 坐标越界 + 收集矩形
    rects = []
    for m in re.finditer(r"<rect\b((?:\"[^\"]*\"|'[^']*'|[^>\"'])*?)/?>", body, re.S):
        t = m.group(1)
        x, y = fnum(t, "x"), fnum(t, "y")
        w, h = fnum(t, "width"), fnum(t, "height")
        rects.append((x, y, w, h))
        if x < -0.01 or x + w > CANVAS_W + 0.01:
            rep("E5", m.start(), "rect 水平越界：x=%g + w=%g 超出 0~680" % (x, w))
        if y < -0.01:
            rep("E5", m.start(), "rect 的 y=%g 为负" % y)
    for m in re.finditer(r"<line\b((?:\"[^\"]*\"|'[^']*'|[^>\"'])*?)/?>", body, re.S):
        t = m.group(1)
        for k in ("x1", "x2"):
            v = fnum(t, k)
            if v < -0.01 or v > CANVAS_W + 0.01:
                rep("E5", m.start(), "line 的 %s=%g 越出 0~680" % (k, v))

    # W1 文字溢出
    for m in re.finditer(r"<text\b((?:\"[^\"]*\"|'[^']*'|[^>\"'])*?)>(.*?)</text>", body, re.S):
        t, inner = m.group(1), m.group(2)
        x, y = fnum(t, "x"), fnum(t, "y")
        fs = attr(t, "font-size")
        try:
            size = float(re.sub(r"[^0-9.]", "", fs)) if fs else 12.0
        except ValueError:
            size = 12.0
        w = text_width(inner, size)
        anchor = (attr(t, "text-anchor") or "start").lower()
        left = x - w / 2.0 if anchor == "middle" else (x - w if anchor == "end" else x)
        right = left + w
        if right > CANVAS_W:
            rep("W1", m.start(), "文本右端到 %.0f，超出画布：%s"
                % (right, strip_tags(inner)[:30]), "WARN")
            continue
        holder = None
        for (rx, ry, rw, rh) in rects:
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                if holder is None or rw < holder[2]:
                    holder = (rx, ry, rw, rh)
        if holder:
            limit = holder[0] + holder[2] - PAD
            if right > limit:
                rep("W1", m.start(), "文本溢出矩形 %.0fpx（右端 %.0f > 界限 %.0f）：%s"
                    % (right - limit, right, limit, strip_tags(inner)[:30]), "WARN")


# ------------------------------------------------------------------ 表格检查

def iter_tables(content):
    """产出 (起始行号, 表头行, 数据行列表, 原始块)。识别连续的以 | 开头的行。"""
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|"):
            j = i
            blk = []
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                blk.append(lines[j])
                j += 1
            if len(blk) >= 2:
                yield i + 1, blk[0], blk[2:], blk
            i = j
        else:
            i += 1


def split_cells(row):
    r = row.strip()
    if r.startswith("|"):
        r = r[1:]
    if r.endswith("|"):
        r = r[:-1]
    r = r.replace("\\|", "\x00")
    return [c.replace("\x00", "\\|").strip() for c in r.split("|")]


def check_tables(content, issues):
    overview = None
    chain = None
    for ln, header, rows, blk in iter_tables(content):
        hdr = split_cells(header)
        # E10 列数一致
        counts = {}
        for k, row in enumerate(blk):
            if re.match(r"^\|[\s:\-|]+\|?\s*$", row):
                continue
            cells = split_cells(row)
            counts.setdefault(len(cells), []).append(ln + k)
        if len(counts) > 1:
            major = max(counts, key=lambda c: len(counts[c]))
            for c, lns in counts.items():
                if c != major:
                    issues.append(Issue("ERROR", "E10", lns[0],
                                        "表格列数不一致：本表主列数 %d，此行 %d 列" % (major, c)))
        # E11 公式内裸竖线（必须在 split 之前查，否则裸 | 会先把单元格拆碎）
        for k, row in enumerate(blk):
            for m in re.finditer(r"\$([^$]+)\$", row):
                expr = m.group(1)
                if re.search(r"(?<!\\)\|", expr):
                    issues.append(Issue("ERROR", "E11", ln + k,
                                        "表格公式内出现裸竖线：$%s$ —— 应写 \\lvert ... \\rvert"
                                        % expr.strip()[:30]))
                    break
        # 识别总览表 / 判定链
        joined = "".join(hdr)
        if overview is None and ("路径" in joined and "触发" in joined):
            overview = (ln, hdr, rows)
        if chain is None and ("判据" in joined and ("步" in joined or "成立" in joined)):
            chain = (ln, hdr, rows)

    if overview is None:
        issues.append(Issue("WARN", "W2", 0,
                            "未找到「路径总览」表（表头需同时含「路径」与「触发」）"))
    if chain is None:
        issues.append(Issue("WARN", "W3", 0,
                            "未找到「判定链」表（表头需同时含「判据」与「步/成立」）"))
    return overview


# ------------------------------------------------------------------ 主文档检查

def check_doc(content, path, issues):
    if not re.search(r"^#\s+\S", content, re.M):
        issues.append(Issue("ERROR", "E8", 0, "缺少 H1 标题"))

    # E9 $$ 配对
    n = content.count("$$")
    if n % 2:
        issues.append(Issue("ERROR", "E9", 0, "$$ 出现 %d 次（奇数），存在未闭合公式块" % n))

    # E15 \begin/\end 与嵌套 cases
    nb, ne = content.count("\\begin{"), content.count("\\end{")
    if nb != ne:
        issues.append(Issue("ERROR", "E15", 0,
                            "\\begin{} %d 个 / \\end{} %d 个 不匹配" % (nb, ne)))
    for m in re.finditer(r"\\begin\{cases\}", content):
        seg = content[m.end(): m.end() + 4000]
        depth, pos = 1, 0
        for t in re.finditer(r"\\(begin|end)\{cases\}", seg):
            depth += 1 if t.group(1) == "begin" else -1
            if depth == 0:
                pos = t.start()
                break
        if pos:
            inner = seg[:pos]
            if "\\begin{cases}" in inner:
                issues.append(Issue("ERROR", "E15", line_of(content, m.start()),
                                    "存在嵌套 cases —— KaTeX 支持不稳，改用表格或单层 cases"))
                break

    # E6 / E7 svg 结构
    for m in re.finditer(r"<!DOCTYPE|<html\b|<body\b", content, re.I):
        issues.append(Issue("ERROR", "E6", line_of(content, m.start()),
                            "md 内出现 %s —— 宿主只接受裸 <svg> 片段" % m.group(0)))
    n_open = len(re.findall(r"<svg\b", content, re.I))
    n_close = len(re.findall(r"</svg\s*>", content, re.I))
    if n_open != n_close:
        issues.append(Issue("ERROR", "E7", 0,
                            "<svg> %d 个 与 </svg> %d 个不匹配" % (n_open, n_close)))
    blocks = list(SVG_BLOCK_RE.finditer(content))
    if not blocks:
        issues.append(Issue("WARN", "W2", 0, "文档内没有 <svg> 决策图"))
    for b in blocks:
        check_svg(content, b.group(0), b.start(), issues)
        if not SHAPE_RE.search(re.sub(r"<!--.*?-->", "", b.group(0), flags=re.S)):
            issues.append(Issue("ERROR", "E7", line_of(content, b.start()),
                                "<svg> 块内没有任何图形元素（空壳）"))

    # E14 章节编号连续
    nums = [int(x) for x in re.findall(r"^##\s+(\d+)[.、]", content, re.M)]
    if nums:
        expect = list(range(1, len(nums) + 1))
        if nums != expect:
            issues.append(Issue("ERROR", "E14", 0,
                                "## N. 编号不连续：实际 %s，应为 1..%d" % (nums, len(nums))))

    # E16 子类型标题格式
    for m in re.finditer(r"^###\s+(.+)$", content, re.M):
        title = m.group(1).strip()
        if re.match(r"^[A-Z]\d+\b", title):
            continue
        if re.search(r"\b[A-Z]\d+\b", title) or re.match(r"^\d+(\.\d+)*\s*[A-Z]\d+", title):
            issues.append(Issue("ERROR", "E16", line_of(content, m.start()),
                                "子类型标题格式不合规：「%s」应为 \"### A1 名称\"（不带章节前缀）"
                                % title[:30]))

    # E12 / E13 路径覆盖
    overview = check_tables(content, issues)
    if overview:
        _, hdr, rows = overview
        idx_path = next((i for i, h in enumerate(hdr) if "路径" in h), 0)
        idx_case = next((i for i, h in enumerate(hdr) if "算例" in h or "案例" in h), None)
        letters_in_table, subs_in_table = [], []
        for row in rows:
            cells = split_cells(row)
            if idx_path < len(cells):
                for L in re.findall(r"\b([A-Z])\b", cells[idx_path]):
                    if L not in letters_in_table:
                        letters_in_table.append(L)
            if idx_case is not None and idx_case < len(cells):
                for s in re.findall(r"\b([A-Z]\d+)\b", cells[idx_case]):
                    if s not in subs_in_table:
                        subs_in_table.append(s)

        body_paths = re.findall(r"^##\s+\d+[.、]\s*路径\s*([A-Z])\b", content, re.M)
        body_subs = re.findall(r"^###\s+([A-Z]\d+)\b", content, re.M)

        for L in letters_in_table:
            if L not in body_paths:
                issues.append(Issue("ERROR", "E12", 0,
                                    "总览表有路径 %s，但正文缺「## N. 路径 %s · …」章节" % (L, L)))
        for s in subs_in_table:
            if s not in body_subs:
                issues.append(Issue("ERROR", "E13", 0,
                                    "总览表列出算例 %s，但正文缺「### %s …」小节" % (s, s)))

        # W6 案例覆盖
        n_case = len(re.findall(r"\*\*(?:算例|案例)\*\*", content))
        if body_subs and n_case < len(set(body_subs)):
            issues.append(Issue("WARN", "W6", 0,
                                "案例 %d 个 < 子类型 %d 个，存在未配案例的类型"
                                % (n_case, len(set(body_subs)))))

    # W4 案例缺 boxed
    secs = re.split(r"^###\s+", content, flags=re.M)[1:]
    for sec in secs:
        head = sec.split("\n", 1)[0]
        if "**算例**" in sec or "**案例**" in sec:
            if "\\boxed" not in sec:
                issues.append(Issue("WARN", "W4", 0,
                                    "小节「%s」有案例但缺 \\boxed 结果" % head.strip()[:26]))

    # W7 占位符
    for m in re.finditer(r"\bTODO\b|\bFIXME\b|\bxxx\b|\?\?\?", content):
        issues.append(Issue("WARN", "W7", line_of(content, m.start()),
                            "残留占位符 %r" % m.group(0)))

    # W8 目录约定
    norm = path.replace("\\", "/")
    if "/method path/" not in norm and "/method_path/" not in norm and "-method_path/" not in norm:
        issues.append(Issue("WARN", "W8", 0,
                            "文件不在 \".../method path/\" 目录下（当前：%s）"
                            % os.path.dirname(norm)))


# ------------------------------------------------------------------ 主流程

def validate_file(path, quiet=False):
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            content = f.read()
    except OSError as e:
        print("  ! 无法读取：%s" % e)
        return 1, []

    issues = []
    check_doc(content, path, issues)
    errors = [i for i in issues if i.level == "ERROR"]
    warns = [i for i in issues if i.level == "WARN"]

    if not quiet:
        print("\n=== %s ===" % path)
        print("  $$ %d 个 | H2 %d 节 | H3 %d 节 | svg %d 块 | 案例 %d 个"
              % (content.count("$$"),
                 len(re.findall(r"^##\s+\S", content, re.M)),
                 len(re.findall(r"^###\s+\S", content, re.M)),
                 len(SVG_BLOCK_RE.findall(content)),
                 len(re.findall(r"\*\*(?:算例|案例)\*\*", content))))
    if not issues:
        if not quiet:
            print("  OK - 未发现问题")
    else:
        for i in issues:
            print("  " + str(i))
    if not quiet:
        print("  小结：%d 个错误，%d 个警告" % (len(errors), len(warns)))
    return (1 if errors else 0), issues


def main(argv):
    args = argv[1:]
    quiet = any(a in ("-q", "--quiet") for a in args)
    as_json = "--json" in args
    targets = []

    if "--dir" in args:
        idx = args.index("--dir")
        if idx + 1 >= len(args):
            print("用法：--dir <目录>")
            return 2
        root = args[idx + 1]
        if not os.path.isdir(root):
            print("不是目录：%s" % root)
            return 2
        for dp, _dn, fns in os.walk(root):
            for fn in sorted(fns):
                if fn.lower().endswith(".md") and not fn.startswith("_verify-log"):
                    targets.append(os.path.join(dp, fn))
    else:
        targets = [a for a in args if not a.startswith("-")]

    if not targets:
        print(__doc__)
        return 2

    rc = 0
    all_issues = []
    for t in targets:
        if not os.path.isfile(t):
            print("\n=== %s ===\n  ! 文件不存在" % t)
            rc = 2
            continue
        r, iss = validate_file(t, quiet)
        all_issues.extend((t, i) for i in iss)
        if r and rc == 0:
            rc = 1

    if as_json:
        print(json.dumps([{"file": f, **i.as_dict()} for f, i in all_issues],
                         ensure_ascii=False, indent=1))
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
