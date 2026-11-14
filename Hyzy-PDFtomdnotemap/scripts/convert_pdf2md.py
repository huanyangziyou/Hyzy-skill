#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PDF -> Markdown 批量转换（pymupdf4llm 封装）

产物沿用素材库约定：  <src>/<stem>/<stem>.md  +  <src>/<stem>/images/

依赖 pymupdf4llm。脚本用任意 python3 跑（只吃标准库），真正解析 PDF 的解释器
由 --py 指定；省略 --py 时按下列顺序自动探测，探不到就停下来提示问用户（不猜）：
    1. 环境变量 HYZY_PDF_PY / HYZY_VENV_PY
    2. 当前解释器 sys.executable
    3. 宿主集中环境目录 $USERPROFILE/.workbuddy/binaries/python/envs/*/
    4. PATH 上的 python3 / python

用法：
    # 转换（数字版 PDF，默认）
    python convert_pdf2md.py --src "<素材目录>"

    # 扫描版 PDF（开 OCR）
    python convert_pdf2md.py --src "<素材目录>" --ocr-mode auto

    # 只转其中几本
    python convert_pdf2md.py --src "..." --only "关键词1,关键词2"

    # 复查（不转换，只统计）
    python convert_pdf2md.py --src "..." --verify-only

安全说明：仅读写本地文件；不联网；不删除任何文件。
"""
import argparse
import glob
import io
import os
import re
import shutil
import subprocess
import sys
import time

try:  # Windows 控制台编码兜底
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass

def _has_pymupdf4llm(py: str) -> bool:
    try:
        return subprocess.run([py, "-c", "import pymupdf4llm"],
                              capture_output=True).returncode == 0
    except Exception:
        return False


def resolve_py() -> str:
    """按 env-adapt 协议探测含 pymupdf4llm 的解释器；探不到返回空串（交由调用方提示问用户）。"""
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""
    cands = [os.environ.get("HYZY_PDF_PY"), os.environ.get("HYZY_VENV_PY"), sys.executable]
    if home:
        for pat in ("Scripts/python.exe", "Scripts/python", "bin/python"):
            cands += sorted(glob.glob(os.path.join(
                home, ".workbuddy", "binaries", "python", "envs", "*", *pat.split("/"))))
    cands += [shutil.which("python3"), shutil.which("python")]
    for c in filter(None, cands):
        if os.path.exists(c) and _has_pymupdf4llm(c):
            return c
    return ""


# 网盘未下完的残留文件后缀 —— 必须排除，否则会拿到半截 PDF
JUNK_SUFFIX = (".downloading", ".crdownload", ".part", ".tmp", ".!qb")


def log(lines, msg):
    stamp = time.strftime("%H:%M:%S")
    s = "[%s] %s" % (stamp, msg)
    print(s, flush=True)
    lines.append(s)


def find_pdfs(src, only, exclude):
    names = []
    for f in sorted(os.listdir(src)):
        if not f.lower().endswith(".pdf"):
            continue
        if f.lower().endswith(JUNK_SUFFIX):
            continue
        if only and not any(k.strip() and k.strip() in f for k in only):
            continue
        if exclude and any(k.strip() and k.strip() in f for k in exclude):
            continue
        names.append(f)
    return names


def md_paths(src, pdf_name):
    stem = os.path.splitext(pdf_name)[0]
    d = os.path.join(src, stem)
    return stem, os.path.join(d, stem + ".md"), os.path.join(d, "images")


def count_heads(md):
    h1 = h2 = h3 = lines = 0
    with open(md, encoding="utf-8", errors="replace") as f:
        for line in f:
            lines += 1
            s = line.lstrip()
            if s.startswith("### "):
                h3 += 1
            elif s.startswith("## "):
                h2 += 1
            elif s.startswith("# "):
                h1 += 1
    return lines, h1, h2, h3


def verify(src, pdfs):
    print("%-52s%8s%7s%8s%5s%6s   %s" % ("书名(stem)", "mdKB", "图片", "行数", "H1", "H2", "状态"))
    print("-" * 100)
    ok = True
    for fn in pdfs:
        stem, md, imgdir = md_paths(src, fn)
        if not os.path.exists(md):
            print("%-52s%8s%7s%8s%5s%6s   %s" % (stem[:50], "-", "-", "-", "-", "-", "缺失 md"))
            ok = False
            continue
        sz = os.path.getsize(md)
        nimg = len(os.listdir(imgdir)) if os.path.isdir(imgdir) else 0
        lines, h1, h2, _ = count_heads(md)
        flag = "OK" if sz > 1000 else "过小(可能转换失败)"
        if sz <= 1000:
            ok = False
        print("%-52s%8d%7d%8d%5d%6d   %s" % (stem[:50], sz // 1024, nimg, lines, h1, h2, flag))
    print("-" * 100)
    print("复查结果：%s" % ("全部 OK" if ok else "存在异常项，需处理"))
    return ok


def main():
    ap = argparse.ArgumentParser(description="PDF -> Markdown 批量转换")
    ap.add_argument("--src", required=True, help="含 PDF 的素材目录")
    ap.add_argument("--py", default=None,
                    help="含 pymupdf4llm 的 python 解释器；省略时自动探测（见 references/env-adapt.md）")
    ap.add_argument("--ocr-mode", default="never", choices=["never", "auto", "always"],
                    help="never=数字版(默认,快) / auto=自动 / always=强制OCR")
    ap.add_argument("--only", default="", help="只转文件名含这些关键词的本（逗号分隔）")
    ap.add_argument("--exclude", default="", help="排除文件名含这些关键词的本（逗号分隔）")
    ap.add_argument("--force", action="store_true", help="已存在 md 也重新转换")
    ap.add_argument("--verify-only", action="store_true", help="只复查，不转换")
    ap.add_argument("--log", default="", help="日志文件路径（默认只输出到 stdout）")
    args = ap.parse_args()

    src = os.path.abspath(args.src)
    if not os.path.isdir(src):
        print("目录不存在：%s" % src)
        return 2
    only = [x for x in args.only.split(",") if x.strip()]
    exclude = [x for x in args.exclude.split(",") if x.strip()]
    pdfs = find_pdfs(src, only, exclude)
    if not pdfs:
        print("在 %s 未找到可转换的 PDF（已排除 .downloading 等残留）" % src)
        return 1

    if args.verify_only:
        return 0 if verify(src, pdfs) else 1

    py = args.py or resolve_py()
    if not py:
        print("未找到含 pymupdf4llm 的 Python。请向用户确认该解释器路径（不要猜）后重跑：\n"
              "  HYZY_PDF_PY=<解释器路径> python convert_pdf2md.py --src \"<素材目录>\"\n"
              "若用户同意安装：<解释器> -m pip install pymupdf4llm")
        return 2
    if not os.path.exists(py):
        print("找不到解释器：%s\n请向用户确认含 pymupdf4llm 的路径后重跑（或用 HYZY_PDF_PY 指定）。" % py)
        return 2
    chk = subprocess.run([py, "-c", "import pymupdf4llm"],
                         capture_output=True, text=True)
    if chk.returncode != 0:
        print("该解释器缺少 pymupdf4llm：%s\n请向用户确认另一个含该库的解释器路径（不要猜）。" % py)
        return 2

    lines = []
    log(lines, "工作目录: %s" % src)
    log(lines, "待转换: %d 本 | ocr-mode=%s" % (len(pdfs), args.ocr_mode))
    t0 = time.time()
    done = fail = 0
    for i, fn in enumerate(pdfs, 1):
        stem, md, imgdir = md_paths(src, fn)
        rel = os.path.relpath(md, src)
        if os.path.exists(md) and not args.force:
            log(lines, "[%d/%d] 已存在，跳过: %s (%dKB)"
                % (i, len(pdfs), rel, os.path.getsize(md) // 1024))
            continue
        log(lines, "[%d/%d] >>> 开始: %s" % (i, len(pdfs), fn))
        t1 = time.time()
        r = subprocess.run(
            [py, "-m", "pymupdf4llm", fn, "--out", ".",
             "--write-images", "--ocr-mode", args.ocr_mode],
            cwd=src, capture_output=True, text=True)
        dt = time.time() - t1
        if os.path.exists(md):
            nimg = len(os.listdir(imgdir)) if os.path.isdir(imgdir) else 0
            log(lines, "    完成 耗时 %.1fmin 退出码 %d md=%dKB 图片=%d"
                % (dt / 60, r.returncode, os.path.getsize(md) // 1024, nimg))
            done += 1
        else:
            fail += 1
            log(lines, "    !! 未生成 md，退出码 %d" % r.returncode)
            if r.stderr:
                log(lines, "    STDERR: " + r.stderr[-1500:])
    log(lines, "\n完成 %d 本，失败 %d 本，总耗时 %.1f min" % (done, fail, (time.time() - t0) / 60))

    if args.log:
        with open(args.log, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    print("\n==== 复查 ====")
    verify(src, pdfs)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
