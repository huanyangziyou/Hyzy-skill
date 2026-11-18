# -*- coding: utf-8 -*-
"""曲线图模板（matplotlib，300 dpi）：D–X 型拟合图 + ε 标注。

用法:
  改 DATA 区 → python plot_curves.py [输出目录]
  （输出目录默认 = 本文件同级的 ../out，实际用时传实验目录的 数据插图/）

为什么这样写（三条硬知识，勿改）:
  1) 图内标注不要中英混排：u'ε$_x$ = %.3f' 会被中文字体拉散字距；
     纯 ASCII 内容改用整行 mathtext：r'$\\varepsilon_x = 0.585\\ \\mathrm{mm/V}\\quad (U_2 = 1000\\ \\mathrm{V})$'
  2) 图例压成 2 列（ncol=2）+ 短标签，可把 figsize 高度从 4.75 压到 3.7 in，
     一页才容得下两张图（页面排版反解：图高+0.21+0.54+0.71 ≤ 剩余空间）。
  3) 刻度用显式列表，不用 range(int(lo), hi, 6) 这类拍脑袋步长；
     拟合线不许出框 → ylim 比数据范围再宽一档。

依赖: numpy, matplotlib（宋体走系统 simsun.ttc，不依赖 rcParams 全局设置）
"""
import os
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

# ==================== DATA 区（改成你的实验数据） ====================
OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', 'out')

X9 = np.array([-16, -12, -8, -4, 0, 4, 8, 12, 16], float)      # 自变量刻度（如 D/mm）
X7 = np.array([-12, -9, -6, -3, 0, 3, 6, 9, 12], float)

# 表: {条件: 读数数组}，只画教师要求的那几条线
CURVES = [
    dict(fname='D-Udx曲线.png',
         x=X9,
         cond={1000: np.array([-27.0, -20.0, -14.0, -7.0, 0.0, 7.5, 14.0, 20.5, 27.5]),
               800:  np.array([-23.5, -17.5, -12.0, -6.0, 0.0, 5.5, 11.5, 16.5, 23.0])},
         xlab=r'$U_{dx}\ /\ \mathrm{V}$', ylab=r'$D\ /\ \mathrm{mm}$',
         sym='x', unit='mm/V', nd=3,
         xlim=(-32, 32), xticks=list(range(-30, 31, 10)),
         ylim=(-20, 20), yticks=list(range(-18, 19, 6)),
         note_y=(0.30, 0.12)),
]

C1 = '#1F5CA8'   # 1000 V
C2 = '#BF4D40'   # 800 V


def setup_font():
    path = r'C:\Windows\Fonts\simsun.ttc'
    if os.path.exists(path):
        plt.rcParams['font.family'] = fm.FontProperties(fname=path).get_name()
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['mathtext.fontset'] = 'cm'


def draw(c):
    lo, hi = 1000, 800
    xs = c['x']
    y1, y2 = c['cond'][lo], c['cond'][hi]
    p1 = np.polyfit(c['cond'][lo], xs, 1)      # x = eps * 读数 + b  →  斜率即灵敏度
    p2 = np.polyfit(c['cond'][hi], xs, 1)
    fmt = (r'$\varepsilon_' + c['sym'] + r' = %.' + str(c['nd'])
           + r'f\ \mathrm{%s}\quad (U_2 = %d\ \mathrm{V})$')

    fig, ax = plt.subplots(figsize=(6.4, 3.7))
    xf = np.linspace(min(y1.min(), y2.min()), max(y1.max(), y2.max()), 60)
    ax.plot(c['cond'][lo], xs, 'o', color=C1, ms=5.0, mew=0, label='%d V 数据点' % lo)
    ax.plot(xf, np.polyval(p1, xf), '-', color=C1, lw=1.5, label='%d V 拟合线' % lo)
    ax.plot(c['cond'][hi], xs, 's', color=C2, ms=5.0, mew=0, label='%d V 数据点' % hi)
    ax.plot(xf, np.polyval(p2, xf), '-', color=C2, lw=1.5, label='%d V 拟合线' % hi)

    ax.set_xlabel(c['xlab'], fontsize=13)
    ax.set_ylabel(c['ylab'], fontsize=13)
    ax.set_xlim(c['xlim']); ax.set_ylim(c['ylim'])
    ax.set_xticks(c['xticks']); ax.set_yticks(c['yticks'])
    ax.tick_params(labelsize=10.5, direction='in', top=True, right=True)
    ax.grid(True, ls=':', lw=0.6, color='0.65', alpha=0.8)
    ax.legend(loc='upper left', ncol=2, framealpha=0.95, handlelength=1.5,
              columnspacing=1.1, borderpad=0.35, labelspacing=0.32,
              prop={'family': plt.rcParams['font.family'], 'size': 9.0})
    ax.text(0.985, c['note_y'][0], fmt % (p1[0], c['unit'], lo),
            transform=ax.transAxes, ha='right', va='top', fontsize=12.5, color=C1)
    ax.text(0.985, c['note_y'][1], fmt % (p2[0], c['unit'], hi),
            transform=ax.transAxes, ha='right', va='top', fontsize=12.5, color=C2)

    fig.tight_layout(pad=0.6)
    out = os.path.join(OUT_DIR, c['fname'])
    os.makedirs(OUT_DIR, exist_ok=True)
    fig.savefig(out, dpi=300, facecolor='white')
    plt.close(fig)
    print('  %-18s %6.1f KB   eps=%.5f / %.5f' % (c['fname'], os.path.getsize(out) / 1024, p1[0], p2[0]))
    return p1[0], p2[0]


if __name__ == '__main__':
    setup_font()
    print('输出目录：', os.path.abspath(OUT_DIR))
    for cc in CURVES:
        draw(cc)
