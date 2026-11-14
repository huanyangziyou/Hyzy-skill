# 环境自适应协议（HDLtoSVG&Explain）

本 skill 不绑定任何机器。命令模板里的路径都是**占位符**：占位符原样出现，就意味着「本机未配置」。

## 一、四个占位符与解析责任

| 占位 | 含义 | 本 skill 的要求 | 谁定 |
|---|---|---|---|
| `<SKILL_DIR>` | 本 skill 所在目录（含 `scripts/validate_svg.py`） | 直接推导，不问人 | 自动 |
| `<PY>` | 跑 `validate_svg.py` 的 Python 3 | `validate_svg.py` 只用标准库，任何 Python 3.8+ 均可 | 自动探测 |
| `<BROWSER>` | 用于 headless 截图核对的 Chromium 系浏览器可执行文件 | 必须是 Chromium 内核（Edge/Chrome），Firefox 不认 `--headless=new` + `--screenshot` | 探测，失败才问 |
| `<风格锚点>` | 用户自己满意的一份旧成品 md（版式/色板/口诀口吻的来源） | **只由用户给**，不探测、不猜、不翻用户工程目录找 | 用户 |

> 本 skill 的画图与写文档**不需要任何第三方库**。唯一的外部程序是渲染核对用的浏览器——而渲染核对是可选的加强步骤：拿不到浏览器就如实说「未做渲染核对」，不要假称已核对。

## 二、三步处理

1. **先探测（只读，不问人）**
   ```bash
   # <SKILL_DIR>
   cd "<本 SKILL.md 所在目录>" && pwd
   # <PY>
   python3 -c "import sys;print(sys.executable)" || python -c "import sys;print(sys.executable)" || py -3 -c "import sys;print(sys.executable)"
   # <BROWSER>：Windows 常见两个位置
   ls "/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" \
      "/c/Program Files/Google/Chrome/Application/chrome.exe" 2>/dev/null
   ```
   macOS 试 `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`；Linux 试 `google-chrome` / `chromium`（`command -v`）。

2. **唯一结果 → 直接用**，并在首次回复写明「已将 `<BROWSER>` 解析为 …」。

3. **探测不到 → 问，只问一句**，且**只在真正要用它的那一步问**：`<BROWSER>` 只在渲染核对时需要，脚本校验阶段不要提前问「要不要装浏览器」。
   ```
   为了做渲染核对（确认图没有溢出、末图没被截），我需要一个 Chromium 系浏览器路径。
   有的话给我路径；没有/不想装的话，我就跳过渲染核对，只做脚本校验并如实标注「未做渲染」。
   ```

## 三、硬门（违反即失败）

- 占位符未解析就执行命令 —— 禁止。
- 拿文档里的示例路径当默认值 —— 禁止。
- 把解析结果写回本 skill 的任何文件 —— 禁止。
- 跳过渲染核对却宣称「排版正常」 —— 禁止。脚本 0 错 0 警 ≠ 渲染正确，这两件事必须分开说。

## 四、源码与产物位置

- 源码路径、产物 md 路径、`<风格锚点>` **都由用户当次给出**，本 skill 不预设任何工程目录，也不自带默认锚点。
- 用户没给产物目录时先问一句，不要凭猜写进某个工程目录（会污染用户的代码仓库）。
