# 任务类型识别与固定流程（dispatch）

来源：2026-08 系列实战（30+ 会议记录 docx、19 份纯文本会议记录、多份直播逐字稿、多份「复制体+剪贴板图」手册、知识星球 HTML 源码）。

**核心原则**：先识别任务类型，再进入该类**固定流程**；每类绑定**已预置的工具/脚本**，直接复用，**绝不临场写脚本、绝不临场 `pip install`**。

---

## 识别决策树

> ⚠️ **入口成本闸门（积分意识，分档）**：内联长文会随每轮对话被 AI 反复重读，产生输入 token 乘数。**分档**：纯长文（无图）> ~1500 字 / 带图复制体 > ~3000 字 → 先请用户存成 `.txt` 再发路径，用 Read 单次注入；带图复制体 ≤ ~3000 字 → 直接内联，完成后再提示下次存文件。`.txt` 只进上下文一次。

```
输入是什么？
├─ 文件后缀 .docx / .pdf ──────────────► 【A】文档类（docx/pdf）
├─ 文件后缀 .txt ──────────────────────► 【B】逐字稿 / 会议记录（txt）
├─ 文件后缀 .html / 粘贴的网页源码 ────► 【C】网页源码类（html）
├─ 以 http(s):// 开头的链接 ───────────► 【D】网页 URL 类
└─ 大段粘贴文本 / .txt + @image#n 截图 ─► 【E】复制体 + 剪贴板图类（优先 .txt 单次注入）
```

【B】内还要看内容信号细分：
```
.txt 内容里是否含「内容记录（AI总结）」或「系统音：」？
├─ 含 → 直播逐字稿（逐字稿 + AI 纪要双段）→ 同一脚本自动判定
└─ 不含 → 普通会议记录 / 纯文本 → 同一脚本
```
> 两类都走 `scripts/raw2md_clean.py`，它已内置双段判定，无需区分、无需另写脚本。

---

## 【A】文档类（.docx / .pdf）

固定工具：`scripts/convert_docx.py`（内部调用预装 markitdown）。

- 单文件：`python convert_docx.py input.docx -o out.md`
- 目录 1:1 镜像：`python convert_docx.py <src_dir> <dst_dir>`（保留子目录结构，每个 docx→md）
- 产出：与源同结构的 .md。
- 校验：tag-safe 正则 `<w:t[^>]*>([^<]*)</w:t>` 统计真实文本，与 markitdown 输出比对（≈100%）；0 残留嵌入标记。

## 【B】逐字稿 / 会议记录（.txt）

固定工具：`scripts/raw2md_clean.py`（含 `light`/`medium` 档，已内置双段）。

- 命令：`python raw2md_clean.py input.txt -o out.md --intensity medium`
- 行为：删系统音/转写标记 + 仅左边界删语气词/口头禅 + 合并 3+ 叠字 + 同音错字「原词（纠正）」；遇「内容记录（AI总结）」自动切分，前半按句切每段 4 句，后半 AI 纪要按「N、」转 H3。
- 编码回退 utf-8→gbk→gb18030。
- 校验：0 残留 `系统音|转写内容|【|说话人`；标题层级正确。

## 【C】网页源码类（.html / 粘贴源码）

固定工具：手工去重 + `curl`（系统自带）。详见 `html-to-md.md`。

- 步骤：定位唯一正文容器（去 milkdown/tiptap 重复副本）→ 提取结构 → 远程图 `curl -o ./images/<语义名>.png` 本地化 → 保留原文链接 → 表格化。
- 校验：无重复副本残留；图片本地文件存在；链接可达。

## 【D】网页 URL 类

固定工具：WebFetch 或 `curl` 抓取源码 → 再走【C】。

- 先取源码（WebFetch 转 markdown 或 curl 存 .html），确认无登录墙；再按 html 流程处理。

## 【E】复制体 + 剪贴板图类

固定工具：LLM 直接结构化（**禁脚本**）+ `scripts/localize_clipboard.py`（图片本地化）+ `scripts/validate_md.py`（校验）。

> **入口分档 + 轮次编排（成本核心）**：
> - **入口**：纯长文（无图）> ~1500 字 / 带图复制体 > ~3000 字 → 先请用户存成 `.txt` 再发路径，用 Read 单次注入（见决策树前的成本闸门）；带图复制体 ≤ ~3000 字 → 直接内联，完成后再提示下次存文件。`.txt` 只进上下文一次，避免长文每轮重灌的积分乘数。
> - **轮次（目标 ≤ 3 轮）**：把互不依赖的调用并入同一条消息——① Skill 加载 +（查目录与 `localize_clipboard.py` 合并的 Bash）+ Write 成品；② `validate_md.py` 一次；③ 记日志 + 呈现。禁止查目录 / 本地化 / Write / 校验各占一轮的线性串行。详见 SKILL.md「积分 / 成本意识」。

- 结构化：LLM 读语义一次性 Write 成品（H2/H3 + 表格 + 图片相对引用）。**绝不写正则解析脚本**（脆弱、易重跑）。
- 图片：用 `scripts/localize_clipboard.py` 按 `@image#n` 顺序取最新 N 张并语义重命名到 `./images/`（替代手写 20 行 cp）。映射协议见 `image-localization.md`。
- **附件（zip/.skill 等）**：统一落 `./attachments/`（与 `images/` 同级），正文用相对路径引用；见 `image-localization.md` 的「非图片附件」段。
- 校验：调用 `scripts/validate_md.py <产物>.md`，不临时重写 Python。
- 可选增强：清单/多工具类在 H1 下插速查表。
- 缺图：用统一约定 `> [!note] 原文此处有配图但未随文本提供`，不伪造、不变体。

---

## 工具清单（全部预置，复用不临场）

| 工具 | 位置 | 用途 | 临场? |
|------|------|------|-------|
| markitdown 0.1.7 | 固定 venv（envs/md） | docx/pdf 转换 | ❌ 已预装 |
| `scripts/convert_docx.py` | skill 内 | docx 1:1 镜像 | ❌ 已固化 |
| `scripts/raw2md_clean.py` | skill 内 | txt 去噪（含双段） | ❌ 已固化 |
| `curl` | 系统自带 | 远程图下载 | ❌ 自带 |
| `scripts/localize_clipboard.py` | skill 内 | 剪贴板图批量本地化（替代手写 cp） | ❌ 已固化 |
| `scripts/validate_md.py` | skill 内 | 单文件合并校验 | ❌ 已固化 |
| `scripts/validate_tree.py` | skill 内 | 整树 relink 校验 | ❌ 已固化 |
| LLM 直接结构化 | Agent 自身 | 复制体/长文结构化 | ❌ 内建 |

> 历史上曾临场写 `/tmp/convert_docx.py`、`/tmp/clean_transcript.py`、`/tmp/clean_meeting.py`、`/tmp/hyzy_processor.py`——这些均已固化为上述 skill 内工具或判定为禁用的低效路径，**今后不得再现**。

---

## 复制 / 移动整树（relink 模式）

把已入库目录整体复制或移动到新位置时，相对路径可能断裂。复制/移动完成后，**必须跑一次整树校验**，禁止凭「目录结构看起来一样」就判定通过：

```bash
# 变量解析规则见 SKILL.md「环境自适应」，此处不重复定义（避免两处写法漂移）
SKILL="${SKILL_DIR:?先解析 <SKILL_DIR>（见 references/env-adapt.md）}"
PY="${PY:-python3}"
"$PY" "$SKILL/scripts/validate_tree.py" "<OUT_DIR>/目标根目录"
```

- 扫描目标目录下所有 `.md`，校验每个 md 的图片引用是否都能解析到真实文件。
- 发现缺失即回头修正路径或重跑 `localize_clipboard.py`，直到 0 缺失。
- 历史上 about the system 合并、副本6 移动曾手动遍历 21/4 处引用才全通过，且副本2/开营手册出现过断链——脚本化后可一次扫完，避免遗漏。
