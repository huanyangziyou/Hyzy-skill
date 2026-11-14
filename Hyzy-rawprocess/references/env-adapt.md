# 环境自适应协议（rawprocess）

本 skill 不绑定任何机器。所有路径都是**占位符**：占位符原样出现，就意味着「本机未配置」，而不是「路径字面值」。

## 一、四个占位符与解析责任

| 占位 | 含义 | 本 skill 的要求 | 谁定 |
|---|---|---|---|
| `<SKILL_DIR>` | 本 skill 所在目录 | 直接推导，不问人 | 自动 |
| `<PY>` | 跑校验/清洗脚本的 Python 3 | **只需标准库**（五个脚本 import 全是 stdlib，任何 Python 3.8+ 均可） | 自动探测 |
| `<VENV>` | 装了 `markitdown` 的 Python | **仅 docx/pdf 转换需要**；其余场景用不上 | 探测，缺失才问 |
| `<OUT_DIR>` | 产物与 `images/` 的落盘目录 | 每次任务由用户指定 | **必须问** |

> 关键区分：`<PY>` 与 `<VENV>` 不是一个东西。`convert_docx.py` 内部调用的是带 markitdown 的解释器；`validate_md.py` / `validate_tree.py` / `raw2md_clean.py` / `localize_clipboard.py` 只吃标准库，随便一个 python3 就能跑。混用会导致「校验也要求装 markitdown」这种没必要的门槛。

## 二、三步处理，不得跳步

1. **先探测（只读，不问人）**
   ```bash
   # <SKILL_DIR>
   cd "<本 SKILL.md 所在目录>" && pwd
   # <PY>：逐个试，取第一个可用的
   python3 -c "import sys;print(sys.executable)" || python -c "import sys;print(sys.executable)" || py -3 -c "import sys;print(sys.executable)"
   # <VENV>：确认某个解释器带 markitdown
   "<候选解释器>" -c "import markitdown;print('ok')"
   ```
   `<VENV>` 候选顺序（与 `convert_docx.py` 的 `_resolve_venv_py()` **逐项一致**）：`HYZY_VENV_PY` → `HYZY_PY` → `<SKILL_DIR>/.venv/Scripts/python.exe` → `<SKILL_DIR>/.venv/bin/python` → `$USERPROFILE/.workbuddy/binaries/python/envs/*/Scripts/python.exe` → `.../envs/*/bin/python` → `PATH` 上的 `python3`/`python`。每个候选都要 `import markitdown` 通过才算命中；Windows 下可执行文件在 `Scripts/`，不是 `bin/`。

2. **唯一结果 → 直接用**，并在第一次回复里写明「已将 `<X>` 解析为 …」。让用户能一眼看出你解析对没对。

3. **探测不到 / 多个候选 / 属于用户偏好 → 问，且只问一个**
   - `<OUT_DIR>`：**用户没给过才问**，不猜（猜错会把产物写进未授权目录）。**本轮已给过就直接沿用**，只在首次回复复述「按你给的 `<OUT_DIR>` 落到 …」，不重复追问——重复确认已给的信息不是严谨，是干扰。
   - `<VENV>`：**只在真正要跑 docx/pdf 转换那一步才探测/询问**，别一上来就问。缺失时问：「这份 docx 需要装 `markitdown` 的 Python。你已有 venv 吗？给我路径；没有的话我可以装到 `<SKILL_DIR>/.venv`，要装吗？」——把「要不要装」和「装哪」合成一句。

## 三、硬门（违反即失败）

- 占位符未解析就执行命令 —— 会把模板路径当真实路径，可能写错目录。
- 拿 `/tmp`、当前目录、或文档里的示例路径当默认值 —— 禁止。
- 把解析结果写回本 skill 的任何文件 —— 禁止。占位符必须原样保留，否则换机器又要人工改一遍，自适应就失效了。
- 重复追问用户**已经明确给出**的信息 —— 禁止。一次问清，之后直接干活；反复确认不是严谨。
- 在**还用不到**某占位符时提前问它（如还没到 Stage 1 就问 venv）—— 禁止。
- 拿不准却不问 —— 禁止。这个 skill 的默认策略是「宁可停一句，不要猜一次」。

## 四、问法模板

```
我需要 <OUT_DIR>（成品 md 与 images/ 的落盘目录）。
建议用 <某具体路径>，你也可以直接给一个目录；说「用建议值」我就按建议的来。
```

一次问完，不拆多轮；用户答「随便 / 你定」时用建议值，并在交付时注明实际用了哪个路径。
