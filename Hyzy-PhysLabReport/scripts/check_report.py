# -*- coding: utf-8 -*-
"""物理实验报告自检（通用 16 项 + 可配专用项）

用法:
  python check_report.py 报告.docx
  python check_report.py 报告.docx --han 700 --tables 4 --figs 4 --questions 3 \
      --forbid "V₂" --expect 0.585,0.692,0.895,1.105

退出码: 0 = 全部通过, 1 = 有不合格项。
依赖: 仅标准库。

设计说明（踩过的坑，勿改）:
  1) 显示公式不数 oMathPara —— Word 重存会把表头行内式提级（6→21）。
     正确口径 = 剔表后、段内无正文、只含 oMathPara 的段落。
  2) 下划线填空 run 数会被 Word 合并（14→5），阈值取 ≥4。
  3) 统计"汉字"只数 w:t（正文），不数 m:t（公式内文字）。
"""
import sys, re, os, zipfile, argparse, json, hashlib

SZ_OK = (12, 14, 15, 16, 18, 22)


def check(path, a):
    z = zipfile.ZipFile(path)
    x = z.read('word/document.xml').decode('utf-8')
    c = lambda pat: len(re.findall(pat, x))
    txt = ''.join(re.findall(r'<w:t(?: [^>]*)?>(.*?)</w:t>', x))
    mtx = ''.join(re.findall(r'<m:t(?: [^>]*)?>(.*?)</m:t>', x))
    kk = txt + mtx
    han = len(re.findall(r'[\u4e00-\u9fff]', txt))
    body = re.sub(r'<w:tbl>.*?</w:tbl>', '', x, flags=re.S)
    npara = len(re.findall(r'<w:p(?:[\s>])', body))
    ntbl = c(r'<w:tbl>')
    nimg = c(r'<pic:pic>') or c(r'<pic:pic ')
    used = sorted({int(s) // 2 for s in re.findall(r'<w:sz w:val="(\d+)"/>', x)})
    errs, warns = [], []

    def must(ok, msg):
        if not ok:
            errs.append(msg)

    def soft(ok, msg):
        if not ok:
            warns.append(msg)

    # ---- 结构 ----
    must(c(r'&amp;') == 0, '含 HTML 实体 %d 处' % c(r'&amp;'))
    must('&lt;w:' not in x, '有 OOXML 片段被当正文转义（mix() 里的 R() 漏了 Raw()）')
    must(c('Cambria Math') > 0, '未使用 Cambria Math')
    must(npara <= 65, '正文段 %d 超上限 65' % npara)
    must(c('宋体') > 0, '未出现宋体')
    must(c('SimSun') == 0, '出现 SimSun %d 处（应全为宋体）' % c('SimSun'))
    must(c('tblBorders') >= ntbl, 'tblBorders %d < 表格 %d' % (c('tblBorders'), ntbl))
    must(c('<w:vAlign w:val="center"/>') > 0, '单元格未垂直居中')
    soft(c('<w:u w:val="single"/>') >= 4,
         '下划线填空 %d 处（<4；Word 重存会合并 run）' % c('<w:u w:val="single"/>'))
    must(c('<w:pgSz') > 0 and c('<w:pgMar') > 0, 'sectPr 未显式设置页面')
    bad = [s for s in used if s not in SZ_OK]
    must(not bad, '出现非标准字号 %s pt' % bad)
    must('∑' not in mtx, '公式内出现 ∑（应用 Σ U+03A3）')
    must(not re.search(r'[&\\{}^_]', mtx), '公式内残留 & \\ { } ^ _ 字符')
    must('注：' not in txt and '注:' not in txt, '出现「注：」段')
    must('误差来源分析' not in txt, '出现「误差来源分析」节')
    must('实验原理' not in txt, '出现「实验原理」节')

    # ---- 显示公式：剔表后数独占段 ----
    paras = re.findall(r'<w:p(?:\s[^>]*)?>.*?</w:p>', body, re.S)
    ndisp = len([q for q in paras if '<m:oMathPara>' in q and not re.sub(
        r'\s', '', ''.join(re.findall(r'<w:t(?: [^>]*)?>(.*?)</w:t>', q)))])
    must(a.disp_min <= ndisp <= a.disp_max, '显示公式 %d 个（应 %d–%d）' % (ndisp, a.disp_min, a.disp_max))

    # ---- 专用可配项 ----
    if a.han is not None:
        must(han <= a.han, '汉字 %d 超上限 %d' % (han, a.han))
    if a.tables is not None:
        must(ntbl == a.tables, '表格 %d 张（应 %d）' % (ntbl, a.tables))
    if a.figs is not None:
        must(nimg == a.figs, '图片 %d 张（应 %d）' % (nimg, a.figs))
    nq = 0
    if '三、课后习题' in x:
        tail = x.split('三、课后习题')[-1]
        nq = len(re.findall(r'<w:t(?: [^>]*)?>([1-6]、[^<]{4,})</w:t>', tail))
    if a.questions is not None:
        must(nq == a.questions, '课后习题 %d 题（应 %d）' % (nq, a.questions))
    for bad_sym in (a.forbid or []):
        must(bad_sym not in kk, '残留禁用符号/写法：%s' % bad_sym)
    for v in (a.expect or []):
        must(v in kk, '关键数值 %s 缺失' % v)

    # ---- 中西文空格（§11.3）----
    # 默认 WARN：数值+单位（0.585 mm/V）与全角填空空间无法用正则完全区分，
    # 需要强制拦截时加 --strict-space。
    sp = re.findall(r'[\u4e00-\u9fff][ \t]+[0-9A-Za-z]|[0-9A-Za-z][ \t]+[\u4e00-\u9fff]', txt)
    msg = '汉字与字母/数字之间有空格 %d 处：%s' % (len(sp), sp[:5])
    (must if a.strict_space else soft)(not sp, msg)

    # ---- 数据契约（优化 v1：不传 --contract 时行为与旧版完全一致）----
    if a.contract:
        try:
            exp = a.contract
            with open(os.path.join(exp, '计算上下文.json'), encoding='utf-8') as f:
                ctx = json.load(f)
            with open(os.path.join(exp, 'sections.json'), encoding='utf-8') as f:
                sec = json.load(f)
            snap = hashlib.sha256(open(os.path.join(exp, 'data.json'), 'rb').read()).hexdigest()
            stale = sec.get('__sourceData') != snap
            if stale:
                errs.append('数据快照已失效：data.json 改动后未重新生成 sections.json')
            pat = re.compile(r'%%DATA:([^:]+):(.+?)%%')

            def _texts(n):
                if isinstance(n, str):
                    yield n
                elif isinstance(n, list):
                    for v in n:
                        yield from _texts(v)
                elif isinstance(n, dict):
                    for k, v in n.items():
                        if k in ('__sourceData', 'note', 'allowedConstants', 'description', 'experiment'):
                            continue
                        if k in ('text', 'answer', 'question', 'label', 'caption', 't',
                                 'text_after', 'blocks', 'parts') or isinstance(v, (list, dict)):
                            yield from _texts(v)

            expected = set()
            for t in _texts(sec):
                for key, fmt in pat.findall(t):
                    if key not in ctx:
                        errs.append('计算上下文缺少字段 %s' % key)
                    else:
                        expected.add(fmt % ctx[key])
            missing = [v for v in sorted(expected) if v not in kk]
            if missing:
                errs.append('占位符注入缺失 %d 个：%s' % (len(missing), missing[:8]))
            print('   [数据契约] 快照 %s | 期望注入 %d 个 | 缺失 %d 个'
                  % ('stale' if stale else 'valid', len(expected), len(missing)))
        except Exception as e:
            errs.append('数据契约检查异常：%s' % e)

    print('== %s  %d KB' % (os.path.basename(path), round(os.path.getsize(path) / 1024)))
    print('   汉字 %d / 正文段 %d / 表 %d / 图 %d / 显示公式 %d / 习题 %d / 字号 %s'
          % (han, npara, ntbl, nimg, ndisp, nq, used))
    if warns:
        for w in warns:
            print('   [WARN]', w)
    if errs:
        print('   [FAIL]')
        for e in errs:
            print('      -', e)
    else:
        print('   [PASS]')
    return not errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+')
    ap.add_argument('--han', type=int, default=None, help='汉字上限（专用约束）')
    ap.add_argument('--tables', type=int, default=None)
    ap.add_argument('--figs', type=int, default=None)
    ap.add_argument('--questions', type=int, default=None)
    ap.add_argument('--disp-min', dest='disp_min', type=int, default=5)
    ap.add_argument('--disp-max', dest='disp_max', type=int, default=14)
    ap.add_argument('--strict-space', dest='strict_space', action='store_true',
                    help='把中西文空格当致命项（默认仅 WARN）')
    ap.add_argument('--contract', default=None,
                    help='实验目录：校验数据快照 + 占位符注入完整性（优化 v1，默认不启用）')
    ap.add_argument('--forbid', type=lambda s: [t for t in s.split(',') if t], default=[])
    ap.add_argument('--expect', type=lambda s: [t for t in s.split(',') if t], default=[])
    a = ap.parse_args()
    ok = all([check(p, a) for p in a.files])
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
