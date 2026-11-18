# 物理实验报告 → PDF（Word COM 无头导出）
#
# 用法（PowerShell）:
#   & "<SKILL_DIR>\scripts\export_pdf.ps1" -Src "<PROJ>\<实验>报告.docx" -Pdf "<PROJ>\_preview.pdf"
#
# ⚠️ 本文件必须保存为 UTF-8 with BOM（encoding='utf-8-sig'）。
#    否则 PowerShell 5.1 会按 GBK 解码中文路径，报"找不到您的文件 …\闇嶅皵鏁堝簲…"。
#
# 说明：
#   - 以只读方式打开（第三个参数 $true），不会改动源 docx。
#   - 17 = wdExportFormatPDF。
#   - 退出前务必 Quit + ReleaseComObject，否则残留 WINWORD.EXE 会锁住文件。

param(
    [Parameter(Mandatory = $true)][string]$Src,
    [string]$Pdf = ''
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($Pdf)) {
    $Pdf = [System.IO.Path]::ChangeExtension($Src, '.pdf')
}

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($Src, $false, $true)
    $doc.ExportAsFixedFormat($Pdf, 17)
    Write-Output ("PAGES=" + $doc.ComputeStatistics(2))
    $doc.Close($false)
}
finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
Write-Output "OK $Pdf"
