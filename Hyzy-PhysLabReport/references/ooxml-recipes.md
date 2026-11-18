# OOXML / OMML 直构配方与踩坑

> 完整可跑版本在 `scripts/build_report.py`。本文件只给**规则、签名与坑**，避免与脚本重复维护。

## 一、为什么直构

| 路径 | 问题 |
|---|---|
| `editor_sdk`（tencent-local-office-edit） | `doc_insert_math` 只产**行内**公式、无 Cambria Math、文档默认字体 SimSun、`sectPr` 为空 → 四项直接违规 |
| Word 里手排 | 无法脚本化，改一处要重排全篇 |
| **python-docx + 手写 OOXML/OMML** | ✅ 唯一能同时满足"字号阶梯 + 居中显示公式 + 六框表格 + 精确字宽"的路径 |

## 二、构件库签名

```python
R(text, pt=12, bold=False, u=False, sub=None, font='宋体')   # 文本 run
MR(t, pt=12, upright=False)                                  # 数学斜体 run（Cambria Math）
U(t, pt=12)                                                  # 数学正体（单位、数字、括号）
CP(pt)                                                       # m:ctrlPr
SUB(base, sub, pt)  SUP(base, sup, pt)  FRAC(num, den, pt)   # 上下标 / 分式
RAD(expr, pt)                                                # 根式（内置 degHide，不显示根指数）
DELIM(expr, pt, b='(', n=')')                                # 自适应括号
DISP(inner, pt)                                              # 显示公式（oMathPara + jc=center）
INL(inner)                                                   # 行内公式（m:oMath）
class Raw(str)                                               # 标记"已是 OOXML 片段"
mix(*parts, pt, bold)                                        # 中文串 + Raw(OMML) 混排
rich(text, pt, bold)                                         # '…_{2}…' → 宋体下标（仅纯文本场景）
P(doc, content, ppr, align, style_rpr)                       # 段落；只收 OOXML 片段
rpr_run(pt, bold)                                            # 段落标记的 rPr
SP(before_pt, after_pt)                                      # spacing（line=240 auto）
set_ppr(p, inner)                                            # 整段替换 pPr
append_frag(el, frag)                                        # 把片段塞进元素
style_table(t, widths)  fill(t, widths, rows, pt, keep)      # 六框图 + 逐行填充
pic(path, width_cm)  figcap(*parts)                          # 图片段 / 图题
```

**用法铁律**：`P()` 只接受以 `<` 开头的片段。纯文本必须过 `rich()`；带公式的混排必须 `mix('中文', Raw(INL(...)), '中文')`。
`mix()` 里传 `R(...)` 的返回值**必须包 `Raw()`**，否则被当成文本转义。

## 三、文档级设置（少一项就违规）

```python
nrm = doc.styles['Normal']; nrm.font.name = '宋体'; nrm.font.size = Pt(12)
rf = nrm.element.get_or_add_rPr().get_or_add_rFonts()
for a in ('w:ascii','w:hAnsi','w:eastAsia','w:cs'): rf.set(qn(a), '宋体')
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
sec.top_margin = sec.bottom_margin = Cm(2.54)
sec.left_margin = sec.right_margin = Cm(3.175)
# 删掉 python-docx 默认的 cols/docGrid，再显式写：
sectPr.append(parse_xml(f'<w:cols {NS} w:space="425" w:num="1"/>'))
sectPr.append(parse_xml(f'<w:docGrid {NS} w:type="lines" w:linePitch="312" w:charSpace="0"/>'))
```

保存后再改 `word/styles.xml` 的 `docDefaults`，把默认字体从等线/Calibri 换成宋体、`sz=24`。否则 Word 打开会残留 **SimSun / 等线**。

## 四、21 条踩坑（按发现顺序）

| # | 坑 | 现象 | 解 |
|---|---|---|---|
| 1 | `append_frag` 只遍历元素子节点 | 纯文本被静默丢弃（汉字 665→439，无报错） | `P()` 加断言：非 `<` 开头直接抛 |
| 2 | `w:t` 正则写成 `<w:t[^>]*>` | 误匹配 `<w:tblPrEx>` 等 | 必须 `<w:t(?: [^>]*)?>` |
| 3 | 图片段用 `lineRule="exact"` | 内联图片向上溢出页边距被裁（y0=0.73 cm） | `line="240" lineRule="auto"`；图片段真实占位 = 图高 + 0.54 cm |
| 4 | `keepNext` 无差别加 | 图+标题+公式结巨块，整块推下页，留白 8–10 cm | 图片段与显示公式**不加**；`h1/h2/h3`、提示语、图题**加** |
| 5 | 成对公式拆页 | ε(1000) 在页底、ε(800) 在次页首 | 每对第一条 `keepNext` |
| 6 | 章节大标题孤立页底 | 「三、课后习题」独占页脚 | `h1` 必须 `keepNext`（曾漏过） |
| 7 | 三张 10 行表切碎页面 | 半页空白 ×2 | 单元格 `line="240" lineRule="exact"` + `snapToGrid=0`（0.55→0.46 cm/行）；`snapToGrid` 单独设无效 |
| 8 | 表标题被转义 | 正文印出 `<w:rPr>…` 一整行 | `mix()` 里的 `R(...)` 包 `Raw()`；收尾断言 `assert '&lt;w:' not in x` |
| 9 | `Σ` 写成 `∑` | 渲染上下标反向 | 用 U+03A3 |
| 10 | 公式里残留 `& \ { } ^ _` | Word 打开报公式损坏 | 构建后扫 `m:t` 文本断言 |
| 11 | 行内公式直接写中文 | 字距被拉散 | 中文走 `rich()`，公式走 `Raw(INL(...))`，二者用 `mix()` 拼 |
| 12 | 图片宽度凭感觉 | 页面留白/图过小 | 由剩余空间反解：图高 + 0.21 + 0.54 + 0.71 ≤ 剩余 |
| 13 | 表格列宽等分 | 数字挤成两行 | `tblGrid` 逐列给值，按内容最宽者分配 |
| 14 | 表头物理量用 Unicode 下标 | `D1`、`d_i` 不像公式 | 表头用 `hdr(MR(...))` 产行内 OMML |
| 15 | 单元格 pPr 顺序错 | Word 忽略对齐 | pPr 子元素顺序：`keepNext → snapToGrid → spacing → ind → jc → rPr` |
| 16 | 预览句柄挡 rename | `os.replace` 报 WinError 5 | 原地 `open(path,'r+b').write()+truncate()` |
| 17 | `win32com` 未安装 | `ModuleNotFoundError` | Word COM 走 PowerShell，不走 Python |
| 18 | PowerShell 脚本无 BOM | 中文路径被当 GBK（"找不到您的文件 …\闇嶅皵…"） | 写文件用 `encoding='utf-8-sig'` |
| 19 | 段落计数按 `<w:p[ >]` | 漏掉无属性 `<w:p>` | 用 `<w:p(?:\s[^>]*)?>` |
| 20 | 直接数 `oMathPara` 判公式数 | Word 重存后 6→21（表头行内式被提级） | 剔表后数"独占段"（见 `verification.md`） |
| 21 | 在用户手改过的 docx 上重跑脚本 | 手改全部丢失 | 备份 + 外科式补丁（只改目标节点字节） |

## 五、构建后的断言清单（写进脚本尾部）

```python
x = zipfile.ZipFile(OUT).read('word/document.xml').decode('utf-8')
assert '&lt;w:' not in x, '有 OOXML 片段被当文本转义（Raw 遗漏）'
txt = ''.join(re.findall(r'<w:t(?: [^>]*)?>(.*?)</w:t>', x))
han = len(re.findall(r'[\u4e00-\u9fff]', txt))
print('汉字 %d | 表外显示公式 %d | 表 %d | 宋体 %d | SimSun %d'
      % (han, ndisp, x.count('<w:tbl>'), x.count('宋体'), x.count('SimSun')))
```

范围：汉字 ≤ 预算、`SimSun`=0、表/图数=专用约束、显示公式在区间、每道习题的汉字数单独打印。

## 六、外科式补丁（用户手改后只改一处）

```python
data = open(SRC, 'rb').read()
x = zipfile.ZipFile(SRC).read('word/document.xml').decode('utf-8')
i = x.index('目标片段前唯一锚点')          # 先 count()==1 断言唯一
j = x.index('目标片段后唯一锚点', i)
x = x[:i] + 新片段 + x[j:]
# 用 zipfile 复制原包，只替换 document.xml 条目（或换 word/media/imageN.png）
```

要点：**纯字符串切分，不经 lxml 序列化**，保证其余字节零改动；定位前先 `count()` 断言唯一，否则改错段落。
