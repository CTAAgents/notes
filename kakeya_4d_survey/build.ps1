# ============================================================
#  构建脚本：OpenAI 四维挂谷猜想工作综述
#  用法：pwsh ./build.ps1          （多遍 xelatex 自动收敛 + 日志体检）
#        pwsh ./build.ps1 -Clean   （体检通过后清理中间文件）
# ============================================================
param(
  [switch]$Clean
)
$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot
$name = 'OpenAI四维挂谷猜想工作综述'
$pdf = Join-Path $PSScriptRoot "$name.pdf"
$logPath = Join-Path $PSScriptRoot "$name.log"
Write-Host "=== 构建：$name ===" -ForegroundColor Cyan

# 记录构建前状态：用于识别 xelatex 静默失败（未启动/未产出）的情形
$pdfBefore = if (Test-Path -LiteralPath $pdf) { (Get-Item -LiteralPath $pdf).LastWriteTime } else { [datetime]::MinValue }

# 多遍编译：至少两遍；若交叉引用仍在漂移则续跑，直至收敛或达到上限
$maxPasses = 4
for ($pass = 1; $pass -le $maxPasses; $pass++) {
  Write-Host "--- 第 $pass 遍 xelatex ---"
  $logBefore = if (Test-Path -LiteralPath $logPath) { (Get-Item -LiteralPath $logPath).LastWriteTime } else { [datetime]::MinValue }
  & xelatex -interaction=nonstopmode -file-line-error "$name.tex" | Out-Null
  $xor = $LASTEXITCODE
  $logAfter = if (Test-Path -LiteralPath $logPath) { (Get-Item -LiteralPath $logPath).LastWriteTime } else { [datetime]::MinValue }
  if ($logAfter -le $logBefore) {
    Write-Host "xelatex 未产生新日志（exit=$xor），判定引擎未成功启动，中止。" -ForegroundColor Red
    Write-Host "排查建议：MiKTeX 引擎内部错误（如内存不足 bad allocation）多为暂时性，可稍后重试；确认引擎可用：xelatex --version。" -ForegroundColor Yellow
    exit 2
  }
  if ($pass -ge 2) {
    $cur = Get-Content -LiteralPath $logPath -Raw
    if ($cur -notmatch 'Label\(s\) may have changed') { break }
    if ($pass -eq $maxPasses) { Write-Host '提示：交叉引用在最大轮次内未收敛，请检查浮动体布局是否震荡。' -ForegroundColor Yellow }
  }
}

# PDF 新鲜度检查：若 PDF 未被本次构建更新，说明编译未产出
$pdfAfter = if (Test-Path -LiteralPath $pdf) { (Get-Item -LiteralPath $pdf).LastWriteTime } else { [datetime]::MinValue }
if ($pdfAfter -le $pdfBefore) {
  Write-Host "PDF 未被本次构建更新（可能编译中止或输出被占用），中止。" -ForegroundColor Red
  exit 3
}

$raw = Get-Content -LiteralPath $logPath -Raw
if (-not $raw) { throw '未能读取编译日志。' }

$checks = [ordered]@{
  'TeX 错误'      = '(?m)^! '
  'Overfull hbox' = 'Overfull \\hbox'
  'Overfull vbox' = 'Overfull \\vbox'
  'Underfull'     = 'Underfull'
  '未定义引用'     = 'There were undefined references'
  '未定义引用键'   = "Citation .+ undefined"
  '缺字'          = 'Missing character'
  '字体警告'      = 'Font Warning'
  '书签警告'      = 'Token not allowed in a PDF string'
  '重复标签'      = 'multiply defined'
  '标签漂移'      = 'Label\(s\) may have changed'
}
$soft = @('Underfull', '标签漂移')
$fail = $false

Write-Host "`n=== 日志体检 ===" -ForegroundColor Cyan
foreach ($k in $checks.Keys) {
  $c = ([regex]::Matches($raw, $checks[$k])).Count
  $status = if ($c -eq 0) { 'PASS' } elseif ($soft -contains $k) { 'WARN' } else { 'FAIL' }
  if ($c -ne 0 -and ($soft -notcontains $k)) { $fail = $true }
  '{0,-14} {1,4}  {2}' -f $k, $c, $status | Write-Host
}

$errs = [regex]::Matches($raw, '(?m)^! .*')
if ($errs.Count -gt 0) {
  Write-Host "`n-- 错误明细（前 10 条）--" -ForegroundColor Red
  $errs | Select-Object -First 10 | ForEach-Object { Write-Host ('   ' + $_.Value) -ForegroundColor Red }
}
$um = [regex]::Matches($raw, "Citation '([^']+)' undefined")
if ($um.Count -gt 0) {
  Write-Host "`n-- 未定义引用键（前 20 条）--" -ForegroundColor Red
  $um | Select-Object -First 20 | ForEach-Object { Write-Host ('   ' + $_.Groups[1].Value) -ForegroundColor Red }
}

if (Test-Path -LiteralPath $pdf) {
  Write-Host ("`nPDF: {0}  ({1:N0} KB)" -f $pdf, ((Get-Item -LiteralPath $pdf).Length / 1KB)) -ForegroundColor Green
}

if ($Clean -and -not $fail) {
  Remove-Item -ErrorAction SilentlyContinue "$name.aux", "$name.out", "$name.toc", "$name.log"
  Write-Host '中间文件已清理。' -ForegroundColor Green
}

if ($fail) {
  Write-Host "`n构建体检未通过。" -ForegroundColor Red
  exit 1
}
Write-Host "`n构建体检通过。" -ForegroundColor Green
exit 0