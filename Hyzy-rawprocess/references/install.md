# 环境与安装

来源：`2026-08-20.md` 环境坑记录。

## Python / venv（隔离环境）
- **本 skill 不自带解释器，也不假定任何固定路径**。`<PY>` 与 `<VENV>` 是两个不同角色，解析规则见 `references/env-adapt.md`：
  - `<PY>`：跑 `validate_md.py` / `validate_tree.py` / `raw2md_clean.py` / `localize_clipboard.py`，**只需标准库**，任意 Python 3.8+ 即可。
  - `<VENV>`：跑 `convert_docx.py` 的 docx/pdf 转换，需要 `markitdown`（docx 需 `[docx]` 附加依赖）。
- **先探测再装**：`"<候选解释器>" -c "import markitdown;print('ok')"` 通过就直接用；全部候选失败才考虑安装，且装前先问用户。
- Windows 下可执行文件在 `Scripts/`，macOS/Linux 在 `bin/`——写模板时按 OS 分支，不要硬套 `Scripts`。
- **markitdown 装好后不必每次重装**（实证可用版本 0.1.7，`[docx]` 支持）。复用命令：
  ```bash
  # 单文件
  "<VENV>/python" -m markitdown input.docx -o out.md
  # 或目录 1:1 镜像（内部调用同一解释器的 markitdown）
  "<VENV>/python" "<SKILL_DIR>/scripts/convert_docx.py" src_dir dst_dir
  ```
  Windows 把 `<VENV>/python` 换成 `<VENV>/Scripts/python.exe`。
- **绝不 `pip install --upgrade pip`** —— 沙箱 safe-delete 会拦截并误删 pip，导致环境报废。
- **仅在确实缺失时**才安装：先 `"<VENV>/python" -m markitdown --help` 验证，失败再用下面命令（直接装包，不升级 pip），**执行前先问用户是否允许装**：
  ```bash
  "<VENV>/python" -m pip install 'markitdown[docx]'
  ```

## 依赖可用性检查（缺失先提示，不静默失败）
- `markitdown`：处理 .docx/.pdf 时需要，**已预装在固定 venv**；调用前先验证 `python -m markitdown --help`，缺失才提示安装。
- `curl`：下载远程图时需要（Windows 10+ 自带）。缺失 → 提示。
- `python3`：运行 `scripts/raw2md_clean.py` / `scripts/convert_docx.py`。

## 索引刷新
写完后在本仓库根目录运行：
```bash
python tools/refresh_index.py
```
（位于 `~/.workbuddy/skills/tools/refresh_index.py`，刷新 `INDEX.md` 让 skill 被发现。）
