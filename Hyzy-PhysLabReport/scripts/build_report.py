# -*- coding: utf-8 -*-
"""物理实验报告 docx 构建骨架（python-docx + 手写 OOXML/OMML 直构）

怎么用：
  1. 改「数据区」：表数据、拟合结果、习题文字。
  2. 改「骨架区」：按专用约束的节次增删段落（标题层级用 h1/h2/h3）。
  3. 跑：python build_report.py [输出路径]
  4. 跑完核对末尾打印的统计（汉字 / 表外显示公式 / 表 / 图 / 宋体 / SimSun）。
  5. 导 PDF 逐页目视（scripts/export_pdf.ps1）+ 跑 check_report.py。

设计约束（改代码前先读）：
  - P() 只接受 OOXML 片段；纯文本过 rich()，混排过 mix('中文', Raw(INL(...)), '中文')。
  - mix() 里传 R(...) 的返回值必须包 Raw()，否则被当文本转义（曾整段印出 XML）。
  - 图片段禁用 lineRule="exact"（会把图顶出页边距裁掉）。
  - keepNext：标题/提示语/图题加；图片段与显示公式不加；成对公式给第一条加。
  - 表格单元格用 lineRule="exact" + snapToGrid=0，否则三张 10 行表会把页面切碎。

依赖：python-docx, Pillow
"""
import os
import re
import sys
import zipfile
import shutil
from docx import Document
from docx.shared import Pt, Cm
from docx.oxml import parse_xml
from docx.oxml.ns import qn

WNS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
MNS = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
NS = f'xmlns:w="{WNS}" xmlns:m="{MNS}"'
SONG, CMF = '宋体', 'Cambria Math'
EPS = '\u03b5'      # ε
MINUS = '\u2212'    # −

# ============================================================ 数据区
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), 'out', 'demo.docx')

TITLE_NAME = '演示实验名称'
CLS_LINE = [('班级：', ''), ('姓名：', ''), ('座位号', '')]

D_MM = ['−16.0', '−12.0', '−8.0', '−4.0', '0', '4.0', '8.0', '12.0', '16.0']
COL_A = ['−27.0', '−20.0', '−14.0', '−7.0', '0.0', '7.5', '14.0', '20.5', '27.5']
COL_B = ['−25.0', '−18.5', '−13.0', '−6.0', '0.0', '6.5', '13.0', '18.0', '25.5']
COL_C = ['−23.5', '−17.5', '−12.0', '−6.0', '0.0', '5.5', '11.5', '16.5', '23.0']

EPS_1000, EPS_800 = '0.585', '0.692'          # 拟合结果（与图内标注必须一致）
RAW_IMG = None                                 # 原始数据图路径，None = 不插图
FIG1 = None                                    # 曲线图路径，None = 不插图

Q1 = '1、演示题一（照抄原题）'
A1 = '结论先行 → 一句机理。不复述「二、数据处理」里的中间结果，只给关系与最终比值。'
Q2 = '2、演示题二（照抄原题）'
A2 = '第二题答案，单段、不分条、不加「答：」。'

# ============================================================ 构件库
def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def R(text, pt=12, bold=False, u=False, sub=None, font=SONG):
    sz = int(round(pt * 2))
    rpr = f'<w:rFonts w:hint="eastAsia" w:ascii="{font}" w:hAnsi="{font}" w:eastAsia="{font}" w:cs="{font}"/>'
    if bold:
        rpr += '<w:b/><w:bCs/>'
    rpr += f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>'
    if u:
        rpr += '<w:u w:val="single"/>'
    if sub == 'sub':
        rpr += '<w:vertAlign w:val="subscript"/>'
    elif sub == 'sup':
        rpr += '<w:vertAlign w:val="superscript"/>'
    return f'<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{esc(text)}</w:t></w:r>'


def MR(t, pt=12, upright=False):
    sz = int(round(pt * 2))
    rpr = (f'<w:rPr><w:rFonts w:hint="default" w:ascii="{CMF}" w:hAnsi="{CMF}" w:cs="{CMF}"/>'
           f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/></w:rPr>')
    mrpr = '<m:rPr><m:sty m:val="p"/></m:rPr>' if upright else ''
    return f'<m:r>{mrpr}{rpr}<m:t xml:space="preserve">{esc(t)}</m:t></m:r>'


def U(t, pt=12):
    return MR(t, pt=pt, upright=True)


def CP(pt=12):
    sz = int(round(pt * 2))
    return (f'<m:ctrlPr><w:rPr><w:rFonts w:hint="default" w:ascii="{CMF}" w:hAnsi="{CMF}"/>'
            f'<w:sz w:val="{sz}"/></w:rPr></m:ctrlPr>')


def SUB(b, s, pt=12):
    return f'<m:sSub><m:sSubPr>{CP(pt)}</m:sSubPr><m:e>{b}</m:e><m:sub>{s}</m:sub></m:sSub>'


def SUP(b, s, pt=12):
    return f'<m:sSup><m:sSupPr>{CP(pt)}</m:sSupPr><m:e>{b}</m:e><m:sup>{s}</m:sup></m:sSup>'


def FRAC(n, d, pt=12):
    return f'<m:f><m:fPr>{CP(pt)}</m:fPr><m:num>{n}</m:num><m:den>{d}</m:den></m:f>'


def RAD(e, pt=12):
    return f'<m:rad><m:radPr><m:degHide m:val="1"/>{CP(pt)}</m:radPr><m:deg/><m:e>{e}</m:e></m:rad>'


def DELIM(e, pt=12, b='(', n=')'):
    return f'<m:d><m:dPr><m:begChr m:val="{b}"/><m:endChr m:val="{n}"/>{CP(pt)}</m:dPr><m:e>{e}</m:e></m:d>'


def DISP(inner, pt=12):
    return (f'<m:oMathPara><m:oMathParaPr><m:jc m:val="center"/></m:oMathParaPr>'
            f'<m:oMath>{inner}</m:oMath></m:oMathPara>')


def INL(inner):
    return f'<m:oMath>{inner}</m:oMath>'


_TOK = re.compile(r'([_^])\{([^}]*)\}')


def rich(text, pt=12, bold=False):
    """纯文本 → run；'_ {x}' / '^{x}' 转宋体上下标（仅用于不含公式的纯文本）"""
    segs, pos = [], 0
    for m in _TOK.finditer(text):
        head = text[pos:m.start()]
        if head:
            segs.append((head, None))
        segs.append((m.group(2), 'sub' if m.group(1) == '_' else 'sup'))
        pos = m.end()
    if text[pos:]:
        segs.append((text[pos:], None))
    return ''.join(R(t, pt=pt, bold=bold, sub=k) for t, k in segs if t)


class Raw(str):
    """标记：已是 OOXML 片段"""


def mix(*parts, pt=12, bold=False):
    out = []
    for p in parts:
        out.append(str(p) if isinstance(p, Raw) else rich(p, pt=pt, bold=bold))
    return ''.join(out)


def set_ppr(p, inner):
    pPr = p._p.get_or_add_pPr()
    for c in list(pPr):
        pPr.remove(c)
    p._p.replace(pPr, parse_xml(f'<w:pPr {NS}>{inner}</w:pPr>'))


def append_frag(el, frag):
    tmp = parse_xml(f'<w:wrap {NS}>{frag}</w:wrap>')
    for c in list(tmp):
        tmp.remove(c)
        el.append(c)


def P(doc, content='', ppr='', align=None, style_rpr=None):
    p = doc.add_paragraph()
    inner = ppr
    if align:
        inner += f'<w:jc w:val="{align}"/>'
    if style_rpr:
        inner += style_rpr
    set_ppr(p, inner)
    if content:
        if isinstance(content, str) and not content.lstrip().startswith('<'):
            raise ValueError('P() 只接受 OOXML 片段，纯文本请先过 rich()/mix()：%r' % content[:30])
        append_frag(p._p, content)
    return p


def rpr_run(pt=12, bold=False, font=SONG):
    sz = int(round(pt * 2))
    b = '<w:b/><w:bCs/>' if bold else ''
    return (f'<w:rPr><w:rFonts w:hint="eastAsia" w:ascii="{font}" w:hAnsi="{font}" '
            f'w:eastAsia="{font}" w:cs="{font}"/>{b}<w:sz w:val="{sz}"/>'
            f'<w:szCs w:val="{sz}"/></w:rPr>')


def SP(before=0, after=0):
    return (f'<w:spacing w:before="{int(before * 20)}" w:after="{int(after * 20)}" '
            f'w:line="240" w:lineRule="auto"/>')


# ============================================================ 文档初始化
doc = Document()
nrm = doc.styles['Normal']
nrm.font.name = SONG
nrm.font.size = Pt(12)
rf = nrm.element.get_or_add_rPr().get_or_add_rFonts()
for a in ('w:ascii', 'w:hAnsi', 'w:eastAsia', 'w:cs'):
    rf.set(qn(a), SONG)
nrm.paragraph_format.space_before = Pt(0)
nrm.paragraph_format.space_after = Pt(0)
nrm.paragraph_format.line_spacing = 1.0

sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
sec.top_margin = sec.bottom_margin = Cm(2.54)
sec.left_margin = sec.right_margin = Cm(3.175)
sec.header_distance, sec.footer_distance = Cm(1.5), Cm(1.75)
sectPr = sec._sectPr
for tag in ('w:cols', 'w:docGrid'):
    for e in sectPr.findall(qn(tag)):
        sectPr.remove(e)
sectPr.append(parse_xml(f'<w:cols {NS} w:space="425" w:num="1"/>'))
sectPr.append(parse_xml(f'<w:docGrid {NS} w:type="lines" w:linePitch="312" w:charSpace="0"/>'))


# ============================================================ 段落构件
def h1(txt):
    P(doc, R(txt, 18, True), ppr='<w:keepNext/>' + SP(12), style_rpr=rpr_run(18, True))


def h2(txt):
    P(doc, R(txt, 15, True), ppr='<w:keepNext/>' + SP(6), style_rpr=rpr_run(15, True))


def h3(parts):
    c = mix(*parts, pt=14, bold=True) if isinstance(parts, tuple) else rich(parts, 14, True)
    P(doc, c, ppr='<w:keepNext/>' + SP(6), style_rpr=rpr_run(14, True))


def tip(parts, pt=12):
    c = mix(*parts, pt=pt) if isinstance(parts, tuple) else rich(parts, pt=pt)
    P(doc, c, ppr='<w:keepNext/>' + SP(3), style_rpr=rpr_run())


def disp(f, keep=False):
    p = doc.add_paragraph()
    set_ppr(p, ('<w:keepNext/>' if keep else '') + SP(3, 3) + rpr_run())
    append_frag(p._p, DISP(f))
    return p


def pic(path, width_cm):
    if not path or not os.path.exists(path):
        print('  [跳过图片] %s' % path)
        return
    p = doc.add_paragraph()
    set_ppr(p, SP(3) + '<w:jc w:val="center"/>' + rpr_run())      # 禁用 exact 行距
    p.add_run().add_picture(path, width=Cm(width_cm))


def figcap(*parts):
    P(doc, mix(*parts, pt=12), ppr='<w:keepNext/>' + SP(6), style_rpr=rpr_run())


# ============================================================ 表
cell_mar = ('<w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="72" w:type="dxa"/>'
            '<w:bottom w:w="0" w:type="dxa"/><w:right w:w="72" w:type="dxa"/></w:tblCellMar>')
BORDERS = ('<w:tblBorders>' + ''.join(
    f'<w:{d} w:val="single" w:color="000000" w:sz="6" w:space="0"/>'
    for d in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV')) + '</w:tblBorders>')


def style_table(t, widths):
    tbl = t._tbl
    tblPr = tbl.tblPr
    for e in list(tblPr):
        if e.tag != qn('w:tblStyle'):
            tblPr.remove(e)
    tblPr.append(parse_xml(f'<w:tblW {NS} w:w="{sum(widths)}" w:type="dxa"/>'))
    tblPr.append(parse_xml(f'<w:jc {NS} w:val="center"/>'))
    tblPr.append(parse_xml(BORDERS.replace('<w:tblBorders>', f'<w:tblBorders {NS}>')))
    tblPr.append(parse_xml(f'<w:tblLayout {NS} w:type="fixed"/>'))
    tblPr.append(parse_xml(cell_mar.replace('<w:tblCellMar>', f'<w:tblCellMar {NS}>')))
    grid = tbl.find(qn('w:tblGrid'))
    if grid is not None:
        tbl.remove(grid)
    grid = parse_xml(f'<w:tblGrid {NS}>' + ''.join(f'<w:gridCol w:w="{w}"/>' for w in widths) + '</w:tblGrid>')
    tblPr.addnext(grid)
    for tr in tbl.findall(qn('w:tr')):
        for e in tr.findall(qn('w:trPr')):
            tr.remove(e)


def fill(t, widths, rows, pt=12, keep=True):
    last = len(rows) - 1
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            if val is None:
                continue
            cell = t.cell(ri, ci)
            tcPr = cell._tc.get_or_add_tcPr()
            for e in list(tcPr):
                if e.tag in (qn('w:tcW'), qn('w:vAlign')):
                    tcPr.remove(e)
            tcPr.insert(0, parse_xml(f'<w:tcW {NS} w:w="{widths[ci]}" w:type="dxa"/>'))
            tcPr.append(parse_xml(f'<w:vAlign {NS} w:val="center"/>'))
            for p in list(cell.paragraphs):
                p._p.getparent().remove(p._p)
            kn = '<w:keepNext/>' if (keep and ri < last) else ''
            np_ = parse_xml(f'<w:p {NS}><w:pPr>{kn}<w:snapToGrid w:val="0"/>'
                            f'<w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="exact"/>'
                            f'<w:jc w:val="center"/>{rpr_run(pt)}</w:pPr></w:p>')
            cell._tc.append(np_)
            if isinstance(val, Raw):
                append_frag(np_, str(val))
            elif isinstance(val, str) and val:
                append_frag(np_, rich(val, pt=pt))


def hdr(math, tail=''):
    return Raw(INL(math) + (R(tail, 12) if tail else ''))


# ============================================================ 骨架区
P(doc, R('物理实验报告', 22, True), align='center', style_rpr=rpr_run(22, True))

name_ppr = SP(15.6) + '<w:ind w:firstLine="1788" w:firstLineChars="742"/>'
P(doc, (R('实验名称：', 12, True) + R('\u3000', 12, True, u=True) +
        R(TITLE_NAME, 12, True, u=True) + R('\u3000', 12, True, u=True)),
  ppr=name_ppr, style_rpr=rpr_run(12, True))

cls_ppr = '<w:spacing w:before="0" w:after="0" w:line="360" w:lineRule="auto"/>'
cls_frag = ''.join(R(k, 12, True) + R('\u3000', 12, True, u=True) +
                   R(v, 12, True, u=True) + R('\u3000', 12, True, u=True) for k, v in CLS_LINE)
P(doc, cls_frag, ppr=cls_ppr, style_rpr=rpr_run(12, True))

# ---- 一、实验数据记录（只放原始数据图）
h1('一、实验数据记录')
pic(RAW_IMG, 13.4)

# ---- 二、数据处理
h1('二、数据处理')
h2('1、测量表格数据')

P(doc, mix('表1：演示测量数据（', Raw(INL(SUB(MR('U', 14), MR('dx', 14), 14))), Raw(R('/(V)）', 14, True))),
  ppr='<w:keepNext/>' + SP(6), style_rpr=rpr_run(14, True))
W = [1400, 1800, 1800, 1800]
t1 = doc.add_table(rows=10, cols=4)
style_table(t1, W)
rows = [[hdr(MR('D') + U('/(mm)')),
         hdr(SUB(MR('U'), MR('2')) + U(' = 1000 V')),
         hdr(SUB(MR('U'), MR('2')) + U(' = 900 V')),
         hdr(SUB(MR('U'), MR('2')) + U(' = 800 V'))]]
for i in range(9):
    rows.append([D_MM[i], COL_A[i], COL_B[i], COL_C[i]])
fill(t1, W, rows)
P(doc, '', style_rpr=rpr_run())

h2('2、测量数据计算')
h3('(1)演示小节')
figcap('图1：', Raw(INL(MR('D') + U('−') + SUB(MR('U'), MR('dx')))), '曲线')
pic(FIG1, 10.8)
tip('由拟合直线：')
disp(SUB(MR(EPS), MR('x')) + U('= ' + EPS_1000 + ' mm/V   (') +
     SUB(MR('U'), MR('2')) + U('= 1000 V)'), keep=True)
disp(SUB(MR(EPS), MR('x')) + U('= ' + EPS_800 + ' mm/V   (') +
     SUB(MR('U'), MR('2')) + U('= 800 V)'))

# ---- 三、课后习题
h1('三、课后习题')
ans_ppr = SP(3) + '<w:ind w:left="0" w:right="0" w:firstLine="420" w:firstLineChars="0"/>'
for q, ans in ((Q1, A1), (Q2, A2)):
    P(doc, rich(q, 12, True), ppr=SP(12), style_rpr=rpr_run(12, True))
    P(doc, rich(ans, 12), ppr=ans_ppr, style_rpr=rpr_run())

# ============================================================ 保存 + 修补 styles
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
doc.save(OUT)
tmp = OUT + '.tmp'
with zipfile.ZipFile(OUT, 'r') as zin, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename == 'word/styles.xml':
            s = data.decode('utf-8')
            s = re.sub(r'<w:docDefaults>.*?</w:docDefaults>',
                       '<w:docDefaults><w:rPrDefault><w:rPr>'
                       '<w:rFonts w:ascii="宋体" w:hAnsi="宋体" w:eastAsia="宋体" w:cs="宋体"/>'
                       '<w:sz w:val="24"/><w:szCs w:val="24"/>'
                       '</w:rPr></w:rPrDefault><w:pPrDefault/></w:docDefaults>', s, flags=re.S)
            data = s.encode('utf-8')
        zout.writestr(item, data)
shutil.move(tmp, OUT)

# ============================================================ 断言 + 统计
x = zipfile.ZipFile(OUT).read('word/document.xml').decode('utf-8')
assert '&lt;w:' not in x, '有 OOXML 片段被当文本转义（mix() 里的 R() 漏了 Raw()）'
mtx = ''.join(re.findall(r'<m:t(?: [^>]*)?>(.*?)</m:t>', x))
assert '\u2211' not in mtx, '公式内出现 ∑（应用 Σ U+03A3）'
assert not re.search(r'[&\\{}^_]', mtx), '公式内残留 & \\ { } ^ _'
txt = ''.join(re.findall(r'<w:t(?: [^>]*)?>(.*?)</w:t>', x))
body = re.sub(r'<w:tbl>.*?</w:tbl>', '', x, flags=re.S)
paras = re.findall(r'<w:p(?:\s[^>]*)?>.*?</w:p>', body, re.S)
ndisp = len([q for q in paras if '<m:oMathPara>' in q and not re.sub(
    r'\s', '', ''.join(re.findall(r'<w:t(?: [^>]*)?>(.*?)</w:t>', q)))])
print('已保存：%s  %.1f KB' % (OUT, os.path.getsize(OUT) / 1024))
print('汉字 %d | 表外显示公式 %d | 表 %d | 图 %d | 宋体 %d | SimSun %d'
      % (len(re.findall(r'[\u4e00-\u9fff]', txt)), ndisp, x.count('<w:tbl>'),
         x.count('<pic:pic>') or x.count('<pic:pic '), x.count('宋体'), x.count('SimSun')))
