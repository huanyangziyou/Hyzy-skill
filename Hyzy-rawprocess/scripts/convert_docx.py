#!/usr/bin/env python3
# convert_docx.py — docx / pdf -> markdown 转换（1:1 镜像）
# 复用「已预装在固定 venv 的 markitdown」，不临场 pip install、不临场写脚本。
#
# 用法：
#   单文件：  python convert_docx.py input.docx [-o out.md]
#   目录镜像：python convert_docx.py <src_dir> <dst_dir>
#            （保留子目录结构，每个 .docx/.pdf -> 同相对路径 .md）
#
# 依赖：一个装了 markitdown 的 Python（见 references/install.md、references/env-adapt.md）。
import sys, subprocess, pathlib, os, shutil, glob


def _has_markitdown(py: str) -> bool:
    try:
        return subprocess.run([py, "-c", "import markitdown"],
                              capture_output=True).returncode == 0
    except Exception:
        return False


def _resolve_venv_py() -> str:
    """按 env-adapt 协议解析「带 markitdown 的解释器」，解析不到就退出并给出问法（不猜）。"""
    root = pathlib.Path(__file__).resolve().parent.parent
    home = pathlib.Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or "")
    cands = [
        os.environ.get("HYZY_VENV_PY"), os.environ.get("HYZY_PY"),
        str(root / ".venv" / "Scripts" / "python.exe"),   # Windows
        str(root / ".venv" / "bin" / "python"),           # macOS / Linux
    ]
    # 宿主若有集中式环境目录（如 WorkBuddy 的 binaries/python/envs/*），一并纳入探测
    if str(home):
        cands += sorted(glob.glob(str(home / ".workbuddy" / "binaries" / "python" / "envs" / "*" / "Scripts" / "python.exe")))
        cands += sorted(glob.glob(str(home / ".workbuddy" / "binaries" / "python" / "envs" / "*" / "bin" / "python")))
    cands += [shutil.which("python3"), shutil.which("python")]
    for c in filter(None, cands):
        if pathlib.Path(c).exists() and _has_markitdown(c):
            return c
    sys.exit(
        "未找到带 markitdown 的 Python。\n"
        "请向用户确认该解释器的路径（不要猜），然后重跑：\n"
        "  HYZY_VENV_PY=<解释器路径> python convert_docx.py <src> [<dst>]\n"
        "若用户同意安装：<解释器> -m pip install 'markitdown[docx]'\n"
        "（禁止 pip install --upgrade pip，会误删 pip）"
    )


_VENV_PY = None


def venv_py() -> str:
    """惰性解析：只在真正要转换时探测，避免 --help / 参数错误时白跑一次探测。"""
    global _VENV_PY
    if _VENV_PY is None:
        _VENV_PY = _resolve_venv_py()
    return _VENV_PY


SUPPORTED = (".docx", ".pdf")


def run_markitdown(src: pathlib.Path, dst: pathlib.Path) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [venv_py(), "-m", "markitdown", str(src), "-o", str(dst)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        msg = (r.stderr or r.stdout).strip().replace("\n", " ")[:240]
        print(f"[FAIL] {src}: {msg}", file=sys.stderr)
        return False
    print(f"[OK] {src} -> {dst}")
    return True


def main():
    args = sys.argv[1:]
    if not args:
        print("usage:\n"
              "  convert_docx.py <input.docx|.pdf> [-o out.md]\n"
              "  convert_docx.py <src_dir> <dst_dir>   # 1:1 目录镜像")
        sys.exit(1)

    src = pathlib.Path(args[0])

    # ---- 单文件模式 ----
    if src.is_file():
        if src.suffix.lower() not in SUPPORTED:
            print(f"[SKIP] 不支持的后缀: {src.suffix}", file=sys.stderr)
            sys.exit(1)
        if "-o" in args:
            out = pathlib.Path(args[args.index("-o") + 1])
        else:
            out = src.with_suffix(".md")
        ok = run_markitdown(src, out)
        sys.exit(0 if ok else 1)

    # ---- 目录 1:1 镜像 ----
    if src.is_dir():
        dst_root = pathlib.Path(args[1]) if len(args) > 1 else src
        files = sorted(p for p in src.rglob("*") if p.suffix.lower() in SUPPORTED)
        if not files:
            print(f"[WARN] {src} 下未找到 {SUPPORTED}", file=sys.stderr)
            sys.exit(0)
        done = 0
        for p in files:
            rel = p.relative_to(src)
            out = dst_root / rel.with_suffix(".md")
            if run_markitdown(p, out):
                done += 1
        print(f"mirrored {done}/{len(files)} files into {dst_root}")
        sys.exit(0 if done == len(files) else 1)

    print(f"[ERR] 找不到: {src}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
