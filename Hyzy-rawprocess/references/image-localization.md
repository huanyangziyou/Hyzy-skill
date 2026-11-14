# 图片本地化

来源：`2026-08-25.md`（开营手册 2 图）、`2026-08-26.md`（副本2 9 图、知识星球 7 图）。

## 原则
- 剪贴板临时文件 / 远程图都**易失效**，必须本地化到 `./images/` 用相对路径引用。
- 按**内容语义**重命名（非 `图片1.png`），便于日后检索与 wiki 链接。

## 剪贴板图（复制体 + 截图场景）

WorkBuddy 会把用户粘贴的截图落到 `$HOME/.workbuddy/clipboard-images/`（Windows 即 `%USERPROFILE%\.workbuddy\clipboard-images\`；若宿主改了位置，用 `HYZY_CLIPBOARD_DIR` 覆盖），文件名形如 `clipboard-<ISO时间戳>-<hash>.<ext>`，按字典序即时间顺序（最新在末尾）。用户消息里的 `@image#1 … @image#n` 顺序与这里的文件名时间序一致——**映射一律以 `@image#n` 顺序为准，禁止仅凭目录最新 N 张猜序**（跨轮/延迟粘贴会错位）。

### 映射协议（避免图义错位）
- **多模态可用**：本地化后，对每张图**抽取 1 句视觉描述写入 alt/图注**（如 `![视觉设定板：母女/车辆/道具](./images/01-visual-board.jpg)`），留痕可回溯。
- **多模态不可用**：禁止凭文本位置猜图义。在 md 对应位置用 `<!-- @image#k 待补图注 -->` 占位，并**向用户索要每张图的说明与顺序**，拿到后再回填命名与图注。

### 一键本地化（替代手写 20 行 cp）
调用固化脚本 `scripts/localize_clipboard.py`，按 `@image#n` 顺序取最新 N 张并语义重命名：
```bash
# 变量解析规则见 SKILL.md「环境自适应」（<SKILL_DIR> / <PY> / <OUT_DIR> 三个占位符）
SKILL="${SKILL_DIR:?先解析 <SKILL_DIR>}"
PY="${PY:-python3}"
S="$SKILL/scripts"
# 取修改时间最新 9 张，按 @image#1..#9 命名（--src 可省，脚本默认即剪贴板目录）
"$PY" "$S/localize_clipboard.py" --dest "<OUT_DIR>/images" --latest 9 \
    --names "01-a.jpg,02-b.png,03-c.jpg,04-d.png,05-e.png,06-f.png,07-g.png,08-h.png,09-i.png"
# 更可靠：显式指定源文件名（避免 tail 误抓旧图）
"$PY" "$S/localize_clipboard.py" --dest "<OUT_DIR>/images" --files "clip-aaa.png,clip-bbb.jpg" --names "01-a.png,02-b.png"
# 预览不复制：加 --dry-run
```
- 命名按**内容语义**，非 `图片1.png`（示例：副本2-账号总览表.png、01-visual-board.jpg）。
- 若用户提供的是图片文件而非剪贴板，直接按语义重命名 `copy` 即可。

## 非图片附件（zip / .skill / 模板等）
复制体若附带非图片附件（如 LLM-Wiki 启动包 `.zip`、工作台 `.skill`），统一落 **`./attachments/`**（与 `images/` 同级），并在正文用相对路径引用：
```markdown
配套压缩包见 [attachments/LLM-Wiki启动包.zip](./attachments/LLM-Wiki启动包.zip)
```
- 附件不进 `images/`，避免与图片混用。
- 若附件与 md 必须在同级目录（如 `.skill` 需与 `images/` 同级），则放 **同名文件夹**（如 `xindao-personal-workbench/xindao-personal-workbench.skill`），不混入 images。

## 远程图（HTML 场景）
```bash
mkdir -p ./images
curl -L -o ./images/s1-账号总览.png "https://article-images.zsxq.com/xxxx.png"
```
- 失败（403/过期）保留原 URL + 标注，不静默丢。

## 正文引用
统一用相对路径：`![账号总览表](./images/副本2-账号总览表.png)`。
