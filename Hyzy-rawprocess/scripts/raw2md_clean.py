#!/usr/bin/env python3
# raw2md_clean.py — 原材料去噪引擎（中度标准，可配 light/medium）
# 作者：raw2md skill | 实战来源：clean_transcript.py / clean_meeting.py（2026-08 系列任务）
#
# 用法：
#   python raw2md_clean.py input.txt -o out.md            # 自动判定双段（逐字稿 + AI 纪要）
#   python raw2md_clean.py input.txt --intensity light -o out.md
#   python raw2md_clean.py input.txt --test              # 仅打印前 3000 字预览，不落盘
#
# 关键坑（已验证）：
#   1) 语气词删除必须用「仅左边界」(BOUND + token -> 保留 group1)，
#      不能用前后都带边界的 lookbehind，否则句首语气词后紧跟正文会漏删。
#   2) 编码回退 utf-8 -> gbk -> gb18030，避免中文乱码。
#   3) 同音错字「原词（纠正）」保留原字，绝不直接替换。
import re, sys, argparse

# ---------- 配置 ----------
# 系统音 / 转写内容标记（light、medium 都会删）
SYS_MARKS = [
    r'系统音[:：]\s*', r'转写内容[:：]\s*', r'说话人[ABCDEF\d]*[:：]\s*',
    r'\[[^\]]*\]', r'【[^】]*】', r'（[^）]*背景音[^）]*）', r'（[^）]*音乐[^）]*）',
]
SYS_RE = re.compile('|'.join(SYS_MARKS))

# 语气词 + 口头禅（仅左边界删除）
FILLERS = ["然后", "其实", "就是", "对吧", "的话", "那个", "这个", "嗯", "啊", "呃", "唉", "额"]
FILLERS_SORTED = sorted(FILLERS, key=len, reverse=True)
BOUND = r'(^|[\s，。、；：！？,.!?;:\n\r（）()“”"\'’‘])'
FILLER_RE = re.compile(BOUND + '(' + '|'.join(re.escape(f) for f in FILLERS_SORTED) + ')')

# 同音错字（原词（纠正）保留原字）。按需扩充，务必高置信。
CORR = {
    "西电": "西电（西理工）",
    "扇形": "扇形（善事）",
    "造型": "造型（早读）",
}
CORR_RE = re.compile('|'.join(re.escape(k) for k in CORR))

STUTTER_RE = re.compile(r'(.)\1{2,}')          # 3+ 叠字 -> 2
SENT_SPLIT = re.compile(r'(?<=[。！？!?；;\n])')  # 按句切分


def read_text(path):
    for enc in ("utf-8", "gbk", "gb18030"):
        try:
            with open(path, encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()


def remove_system_marks(t):
    return SYS_RE.sub('', t)


def remove_fillers(t):
    prev, cur = None, t
    while prev != cur:           # 迭代以处理链式语气词
        prev = cur
        cur = FILLER_RE.sub(r'\1', cur)
    return cur


def collapse_stutter(t):
    return STUTTER_RE.sub(r'\1\1', t)


def correct(t):
    return CORR_RE.sub(lambda m: CORR[m.group(0)], t)


def clean_core(t, intensity):
    t = remove_system_marks(t)
    if intensity == 'light':
        return t.strip()
    # medium / heavy 共用基座
    t = remove_fillers(t)
    t = collapse_stutter(t)
    t = correct(t)
    t = re.sub(r'[，。、；：！？]{2,}', lambda m: m.group(0)[0], t)  # 合并链式删 filler 留下的重复标点
    t = re.sub(r'\n[，。、；：]\s*', '\n', t)   # 句首孤立标点清理
    return t.strip()


def split_sentences(t):
    return [s.strip() for s in SENT_SPLIT.split(t) if s.strip()]


def to_paragraphs(t, n=4):
    sents = split_sentences(t)
    paras, buf = [], []
    for s in sents:
        buf.append(s)
        if len(buf) >= n:
            paras.append(''.join(buf))
            buf = []
    if buf:
        paras.append(''.join(buf))
    return paras


def build_md(text, intensity):
    # 双段判定：含 "内容记录（AI总结）" 等切分标记 -> 逐字稿 + AI 纪要
    m = re.search(r'内容记录（AI总结）|内容记录\s*[（(]?AI', text)
    if m:
        head = text[:m.start()]
        tail = text[m.start():]
        transcript = clean_core(head, intensity)
        paras = to_paragraphs(transcript, 4)
        tail_clean = clean_core(tail, intensity)
        # AI 纪要按 "N、" 或 "一、" 转 H3
        tail_md = re.sub(r'(?:^|\n)\s*([0-9一二三四五六七八九十]+)[、.]\s*([^\n]+)',
                         r'\n### \1、\2', tail_clean)
        return '\n\n'.join(paras) + '\n\n---\n\n' + tail_md.strip()
    # 普通会议记录：按句切段
    cleaned = clean_core(text, intensity)
    return '\n\n'.join(to_paragraphs(cleaned, 4))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('-o', '--output')
    ap.add_argument('--intensity', default='medium', choices=['light', 'medium', 'heavy'])
    ap.add_argument('--test', action='store_true')
    args = ap.parse_args()
    text = read_text(args.input)
    md = build_md(text, args.intensity)
    if args.test or not args.output:
        print(md[:3000])
        return
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f'wrote {args.output} ({len(md)} chars)')


if __name__ == '__main__':
    main()
