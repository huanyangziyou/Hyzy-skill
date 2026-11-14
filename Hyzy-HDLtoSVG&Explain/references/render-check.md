# 渲染核对（第五步之 5）

> **何时读**：`validate_svg.py` 跑完、准备交付之前。脚本报 `0 错 0 警` **不等于**渲染正确——它只看字面标签，看不到文本压边、节点掉框外、末图被截。
> 新建文档也做，多图文档必做。

```python
# 抽出 md 里所有 SVG → 套一层白底 HTML（宽 680 + padding）→ Chromium headless 截图
import re, os, subprocess
BROWSER = "<BROWSER>"          # 按 references/env-adapt.md 解析；不要写死安装路径
svgs = re.findall(r"<svg\b.*?</svg>", open(MD, encoding="utf-8").read(), re.S)
html = "<!DOCTYPE html><meta charset=utf-8><body style='margin:0;background:#fff'>" \
       + "".join(f"<div style='width:680px;margin:0 0 24px;padding:12px'>{g}</div>" for g in svgs)
open(HP, "w", encoding="utf-8").write(html)
subprocess.run([BROWSER,
                "--headless=new", "--disable-gpu", "--hide-scrollbars",
                f"--screenshot={PNG}", "--window-size=740,2400", "file:///" + HP.replace("\\", "/")])
```

⚠️ **`--window-size` 的高度必须盖过全部图的累计高度**，否则**末图会被静默截掉**（默认 `712,1032` 只够单张图；3 图文档常需 `2400`+）。**不要靠猜坐标裁图定位**——先按行段扫描算出每张图的真实 y 区间，再逐图放大复核：

```python
import numpy as np; from PIL import Image
a = np.array(Image.open(PNG).convert("L"))
rows = (a < 245).sum(axis=1)            # 每行的非白像素数
segs, s = [], None
for i, v in enumerate(rows):
    if v > 0 and s is None: s = i
    elif v == 0 and s is not None:
        if i - s > 5: segs.append((s, i))   # 每张图一个连续内容段
        s = None
```
`segs` 的条目数 == 图数时，逐段 `Image.crop(...).resize(2×)` 读一遍即可确认完整。

**只看三点**：① 节点数对不对；② 有没有图形掉在框外变成裸文本；③ **文本有没有溢出/压边的框**（中文长句最容易顶到右边框）。

> **校验器的可见范围（盲区）**：脚本只认**字面** `<svg …>`。若图以 `![svg](data:image/svg+xml;base64,…)` 内嵌，`<svg` 不作为字面量出现 → 该图**完全不在检查范围内**（`md 结构：0 个 svg 块` 就是这个信号，哪怕文档里有 4 张图）。交付时优先内联 SVG；发现 base64 内嵌要主动说明"这几张图没被校验到"。

### 5.1 「某张图怎么没了」的排障顺序（先查文件现场，再查渲染）

1. **先打开文件看现场**：定位到该图的 H2 下方。若那里是**一句路径 / 一句无关文本 / 一串连续空行**，就是**被粘贴覆盖**了（真因里最常见），跟渲染无关。
2. 确认覆盖后**先建备份**（`<文件名>.bak-YYYYMMDD`，并记下原 md5），再动手重建。
3. **重建必须同源**：从同一文档已附的源码段（或原 `.v`）**逐级重读参数**，不从表格/摘要/记忆补值；重建后逐个核对节点配色段落与「读图口诀」是否仍对得上。
4. 修完跑一次校验；**再补一次 headless 渲染核对**——真实渲染是最接近用户视角的判据。**直接照搬上文「写入流程第 5 步」的脚本与两条纪律**（窗口高度必须盖过全部图、按行段扫描定位每张图）——此处不重复，以免出现两处口径不一致的旧写法。
5. 只有排除"覆盖"之后，才去查渲染侧原因（`</svg>` 提前闭合、marker id 未定义、宿主不支持内联 SVG 等）。
