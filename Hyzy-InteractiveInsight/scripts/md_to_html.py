#!/usr/bin/env python3
"""把 v2 互动理解物 md 转成自包含单文件 HTML（离线可用、零外链）。

支持 v2 的四层折叠契约（风格基线 v2 第三节）：
  - L1 <details class="mod" id="mN">  模块卡片
  - L2 <details class="blk">           五个块
  - L3 <details class="sub">           细项（步骤 / 闪卡 / 例外 / 前提）
  - L0 常显：模块摘要行的疑问句 + 结论句 + [[徽章]]

渲染器按「括号深度」解析嵌套 details，并为每个 details 写 data-lv，
供页面上的四档展开控制条使用。同时兼容 v1 的平铺 details。

只处理本 skill 产物用到的有限语法子集，不依赖任何第三方库或 CDN：
  # / ## / ###、> 引用、- 列表、| 表格|、**粗体**、`行内码`、
  _(下标) / ^(上标)、[[徽章]]、[文字](#锚点)、内联 <svg>。

仅用标准库，无网络、无外部资源、无删除操作。
"""

import argparse
import html
import re
import sys

CSS = """
:root{--bg:#f6f7f9;--surface:#fff;--ink:#22252a;--muted:#6b7280;--line:#e5e7eb;
--accent:#2563a6;--accent2:#0f766e;--soft:#eef4fb;--code:#f3f4f6;--tag:#e8eef7}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font-family:system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;
 line-height:1.72;font-size:15px}
.wrap{max-width:900px;margin:0 auto;padding:28px 24px 80px}
.bar{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);
 padding:10px 0;margin-bottom:22px;z-index:5;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.bar span{font-size:12px;color:var(--muted);margin-right:4px}
.bar button{background:var(--surface);border:1px solid var(--line);border-radius:7px;
 padding:6px 12px;font-size:13px;color:var(--accent);cursor:pointer;font-family:inherit}
.bar button:hover{background:var(--soft)}
h1{font-size:23px;line-height:1.4;margin:0 0 8px}
h2{font-size:17px;margin:26px 0 10px;padding:8px 0;border-bottom:2px solid var(--accent);color:#1c3d5e}
h3{font-size:14px;margin:14px 0 6px;color:var(--accent);font-weight:600}
p{margin:9px 0}
blockquote{margin:12px 0;padding:9px 14px;background:var(--soft);
 border-left:3px solid var(--accent);color:#3a4d63;border-radius:0 7px 7px 0;font-size:14px}
ul{margin:9px 0;padding-left:22px}
li{margin:4px 0}
strong{font-weight:600}
sub,sup{font-size:0.72em;line-height:0}
code{background:var(--code);padding:1px 5px;border-radius:4px;font-size:13px;
 font-family:"Cambria Math","Times New Roman",serif;font-style:italic}
pre{background:var(--code);padding:12px 14px;border-radius:8px;overflow:auto;line-height:1.5}
pre code{background:none;padding:0;font-style:normal}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:13.5px;background:var(--surface)}
th,td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
th{background:var(--soft);font-weight:600;color:#1c3d5e}
.summary-line{color:var(--muted);font-size:12.5px;font-weight:400}
.tag{display:inline-block;background:var(--tag);color:#31547c;border-radius:5px;
 padding:1px 7px;font-size:11.5px;margin:0 2px;font-weight:600;white-space:nowrap}
a.jump{color:var(--accent);text-decoration:none;cursor:pointer}
a.jump:hover{text-decoration:underline}
details{border-radius:8px}
summary{cursor:pointer;list-style:none}
summary::-webkit-details-marker{display:none}
summary::before{content:"\\25B8  ";color:var(--muted)}
details[open]>summary::before{content:"\\25BE  "}
details.nav{background:var(--surface);border:1px solid var(--line);padding:0 16px;margin:9px 0}
details.nav>summary{padding:10px 0;color:var(--accent);font-weight:600;font-size:14px}
details.mod{border:1px solid var(--line);border-left:4px solid var(--accent);
 background:var(--surface);margin:14px 0;padding:0 18px;
 box-shadow:0 1px 3px rgba(20,40,70,.05)}
details.mod>summary{padding:13px 0;font-size:15px;font-weight:600;color:#16324f}
details.mod>summary .tag:first-child{background:#1c3d5e;color:#fff;margin-right:8px}
details.mod[open]>summary{border-bottom:1px solid var(--line);margin-bottom:10px}
details.blk{border:1px solid var(--line);background:#fcfdfe;margin:10px 0 10px 8px;padding:0 14px}
details.blk>summary{padding:10px 0;color:var(--accent);font-size:14px}
details.blk[open]>summary{border-bottom:1px dashed var(--line)}
details.sub{border-left:3px solid var(--accent2);background:#fbfdfc;
 margin:8px 0 8px 8px;padding:0 12px}
details.sub>summary{padding:7px 0;color:var(--accent2);font-size:13px}
details.sub[open]>summary{border-bottom:1px dashed var(--line)}
.foot{margin-top:44px;padding-top:16px;border-top:1px solid var(--line);color:var(--muted);font-size:12px}
svg{max-width:100%;height:auto;display:block;margin:12px 0}
@media(max-width:600px){.wrap{padding:20px 14px 60px}h1{font-size:20px}
 details.mod{padding:0 12px}details.blk,details.sub{margin-left:2px}}
"""

JS = """
function setLevel(n){
  document.querySelectorAll('details').forEach(function(d){
    var lv=parseInt(d.getAttribute('data-lv')||'0',10);
    if(n===99){d.open=true;}
    else if(n===-1){d.open=false;}
    else if(lv>0){d.open=(lv<=n);}
  });
}
document.addEventListener('click',function(e){
  var a=e.target.closest ? e.target.closest('a.jump') : null;
  if(!a)return;
  var d=document.getElementById(a.getAttribute('data-target'));
  if(d)d.open=true;
});
"""


def _wrap_balanced(text, marker, tag):
    """把 marker(...) 转成 <tag>...</tag>，支持括号嵌套。"""
    out = []
    i = 0
    while i < len(text):
        pos = text.find(marker + "(", i)
        if pos < 0:
            out.append(text[i:])
            break
        out.append(text[i:pos])
        j = pos + len(marker) + 1
        depth = 1
        while j < len(text) and depth:
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
            j += 1
        if depth == 0:
            out.append("<" + tag + ">" + text[pos + len(marker) + 1:j - 1] + "</" + tag + ">")
            i = j
        else:
            out.append(marker)
            i = pos + len(marker)
    return "".join(out)


def _bare_subscripts_in_code(match):
    """只转行内码内部的单字符裸下标 a_n -> a<sub>n</sub>，避免误伤 file_name。"""
    code = match.group(1)
    code = re.sub(r"(?<=[A-Za-z0-9ΦΨΔΩλμσηθωδγβαεζκνξπρτυχφ]{1})_([A-Za-z0-9])(?![A-Za-z0-9(])", r"<sub>\1</sub>", code)
    return "<code>" + code + "</code>"


def inline(text):
    out = html.escape(text, quote=False)
    out = re.sub(r"`([^`]+)`", _bare_subscripts_in_code, out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"\[\[([^\]]+)\]\]", r'<span class="tag">\1</span>', out)
    out = re.sub(r"\[([^\]]+)\]\(#([^)]+)\)",
                 r'<a class="jump" href="#\2" data-target="\2">\1</a>', out)
    out = _wrap_balanced(out, "_", "sub")
    out = _wrap_balanced(out, "^", "sup")
    return out


def _details_open_attrs(line):
    """返回 <details ...> 的属性字符串；不是 details 开标签返回 None。"""
    m = re.match(r"^<details(\s[^>]*)?>", line.strip())
    if not m:
        return None
    return (m.group(1) or "").strip()


def svg_notation(block):
    """SVG 内的上下标记法转成 tspan（HTML <sub> 在 SVG 文本里不生效）。"""
    block = re.sub(r"_\(([^()]*)\)",
                   r'<tspan baseline-shift="sub" font-size="0.72em">\1</tspan>', block)
    block = re.sub(r"\^\(([^()]*)\)",
                   r'<tspan baseline-shift="super" font-size="0.72em">\1</tspan>', block)
    return block


def is_table_sep(line):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c) for c in cells)


def render(lines, level=0):
    """渲染 md 行；level 为当前 details 嵌套层数，用于写 data-lv。"""
    parts = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        attrs = _details_open_attrs(stripped)
        if attrs is not None:
            depth = 1
            summary = ""
            inner = []
            j = i + 1
            while j < len(lines) and depth > 0:
                cur = lines[j]
                s = cur.strip()
                is_open = _details_open_attrs(s) is not None
                is_close = "</details>" in s
                if is_open:
                    depth += 1
                if is_close:
                    depth -= 1
                if depth == 0:
                    break
                if s.startswith("<summary>") and depth == 1 and not summary:
                    summary = re.sub(r"</?summary>", "", s)
                else:
                    inner.append(cur)
                j += 1
            lv = 0 if re.search(r'class=["\']nav["\']', attrs) else level + 1
            parts.append(
                "<details" + (" " + attrs if attrs else "") + ' data-lv="' + str(lv) + '">'
                + "<summary>" + inline(summary) + "</summary>"
                + render(inner, level + 1) + "</details>"
            )
            i = j + 1 if j < len(lines) else j
            continue

        if stripped.startswith("<svg") or "<svg" in line:
            block = [line]
            while "</svg>" not in line and i + 1 < len(lines):
                i += 1
                line = lines[i]
                block.append(line)
            parts.append(svg_notation("\n".join(block)))
            i += 1
            continue

        if stripped.startswith("```"):
            i += 1
            code = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            parts.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
            continue

        if stripped.startswith("|") and i + 1 < len(lines) and is_table_sep(lines[i + 1]):
            header = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            t = ["<table><thead><tr>"]
            t += ["<th>" + inline(c) + "</th>" for c in header]
            t.append("</tr></thead><tbody>")
            for r in rows:
                t.append("<tr>")
                t += ["<td>" + inline(c) + "</td>" for c in r]
                t.append("</tr>")
            t.append("</tbody></table>")
            parts.append("".join(t))
            continue

        if stripped.startswith("# "):
            parts.append("<h1>" + inline(stripped[2:]) + "</h1>")
        elif stripped.startswith("## "):
            parts.append("<h2>" + inline(stripped[3:]) + "</h2>")
        elif stripped.startswith("### "):
            parts.append("<h3>" + inline(stripped[4:]) + "</h3>")
        elif stripped.startswith("> "):
            parts.append("<blockquote>" + inline(stripped[2:]) + "</blockquote>")
        elif stripped.startswith("- "):
            items = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                items.append("<li>" + inline(lines[i].strip()[2:]) + "</li>")
                i += 1
            parts.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif stripped in ("---", "***"):
            pass
        elif stripped:
            parts.append("<p>" + inline(stripped) + "</p>")
        i += 1
    return "\n".join(parts)


def convert(text, title):
    title_m = re.search(r"^#\s+(.+)", text, re.M)
    page_title = title or (title_m.group(1).strip() if title_m else "理解物")
    body = render(text.splitlines())
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(page_title)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<div class="bar"><span>折叠层级</span>
<button onclick="setLevel(1)">仅主干</button>
<button onclick="setLevel(2)">展开到块</button>
<button onclick="setLevel(99)">全部展开</button>
<button onclick="setLevel(-1)">全部收起</button>
</div>
{body}
<div class="foot">本地生成，断网可读，无任何外部请求。点击模块标题展开卡片，再点块与细项逐层深入；导航里的大纲链接会直接打开对应模块。</div>
</div>
<script>{JS}</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description="把理解物 md 转成自包含 HTML（纯本地，无外发）")
    ap.add_argument("files", nargs="+", help="要转换的 .md 文件")
    ap.add_argument("--title", default="", help="页面标题（省略则取 md 的一级标题）")
    ap.add_argument("--out-dir", default="", help="输出目录（省略则与原文件同目录）")
    args = ap.parse_args()

    import os
    for path in args.files:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        out_html = convert(text, args.title)
        if args.out_dir:
            base = os.path.basename(path).replace(".md", ".html")
            dest = os.path.join(args.out_dir, base)
        else:
            dest = path[:-3] + ".html" if path.endswith(".md") else path + ".html"
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(out_html)
        print(f"OK  {path} -> {dest}  ({len(out_html)} chars)", file=sys.stderr)


if __name__ == "__main__":
    main()
