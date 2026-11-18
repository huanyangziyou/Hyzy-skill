# -*- coding: utf-8 -*-
"""两份 docx 的段落级 diff：AI 稿 vs 用户修订稿。

用法:
  python diff_docx.py A.docx B.docx [--max 300]

输出:
  1) 统计对比（汉字 / oMathPara / 表 / 图 / 字号 / 中西空格）
  2) 逐段 diff（- 原稿 / + 修订稿），表格整体作为一段参与比较

为什么不用 Word 比较文档：Word 的修订视图会把样式改动也算进去，
而复盘只需要"文字与公式变了什么"。段落级 difflib 足够且可脚本化。
"""
import sys, re, zipfile, difflib, argparse

def load(path):
    return zipfile.ZipFile(path).read('word/document.xml').decode('utf-8')

def stats(x):
    txt = ''.join(re.findall(r'<w:t(?: [^>]*)?>(.*?)</w:t>', x))
    return {
        '汉字': len(re.findall(r'[\u4e00-\u9fff]', txt)),
        'oMathPara': x.count('<m:oMathPara>'),
        '表': x.count('<w:tbl>'),
        '图': x.count('<pic:pic>') or x.count('<pic:pic '),
        '字号': sorted({int(s) // 2 for s in re.findall(r'<w:sz w:val="(\d+)"/>', x)}),
        '中西空格': len(re.findall(r'[\u4e00-\u9fff][ \t]+[0-9A-Za-z]|[0-9A-Za-z][ \t]+[\u4e00-\u9fff]', txt)),
        'SimSun': x.count('SimSun'),
    }

def paras(x):
    out = []
    for m in re.finditer(r'<w:tbl>.*?</w:tbl>|<w:p(?:\s[^>]*)?>.*?</w:p>', x, re.S):
        blk = m.group(0)
        if blk.startswith('<w:tbl>'):
            rows = []
            for tr in re.findall(r'<w:tr(?:\s[^>]*)?>.*?</w:tr>', blk, re.S):
                cells = []
                for tc in re.findall(r'<w:tc>.*?</w:tc>', tr, re.S):
                    t = ''.join(re.findall(r'<w:t(?: [^>]*)?>(.*?)</w:t>', tc))
                    mm = ''.join(re.findall(r'<m:t(?: [^>]*)?>(.*?)</m:t>', tc))
                    cells.append((t + mm).strip())
                rows.append(' | '.join(cells))
            out.append('\n'.join(rows))
        else:
            t = ''.join(re.findall(r'<w:t(?: [^>]*)?>(.*?)</w:t>', blk))
            mm = ''.join(re.findall(r'<m:t(?: [^>]*)?>(.*?)</m:t>', blk))
            s = (t + (('  [' + mm + ']') if mm else '')).strip()
            if s:
                out.append(s)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('a'); ap.add_argument('b')
    ap.add_argument('--max', type=int, default=300, help='单行截断长度')
    a = ap.parse_args()
    xa, xb = load(a.a), load(a.b)
    sa, sb = stats(xa), stats(xb)
    print('== 统计对比')
    for k in sa:
        flag = '' if sa[k] == sb[k] else '  <<<'
        print('  %-10s A=%-24s B=%-24s%s' % (k, sa[k], sb[k], flag))
    la, lb = paras(xa), paras(xb)
    print('\n== 段落数 A=%d  B=%d' % (len(la), len(lb)))
    print('\n== 逐段 diff（- 原稿 / + 修订稿）')
    for line in list(difflib.unified_diff(la, lb, lineterm='', n=0))[2:]:
        print(line[:a.max])

if __name__ == '__main__':
    main()
