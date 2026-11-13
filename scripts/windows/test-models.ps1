# Prueba qué modelos de Claude puede invocar tu cuenta en Bedrock (una llamada mínima por modelo).
# Uso:  .\scripts\windows\test-models.ps1
param([string]$Profile = "tripplanner", [string]$Region = "us-east-1")
$ErrorActionPreference = "Continue"; $env:AWS_PAGER = ""; $env:PYTHONUTF8 = "1"
$models = @(
  "us.anthropic.claude-sonnet-5-5", "us.anthropic.claude-sonnet-5", "us.anthropic.claude-sonnet-4-6",
  "us.anthropic.claude-opus-4-5-20251101-v1:0", "us.anthropic.claude-haiku-5-5",
  "us.anthropic.claude-haiku-4-5-20251001-v1:0",
  "global.anthropic.claude-sonnet-4-6", "global.anthropic.claude-haiku-4-5-20251001-v1:0"
)
$msg = Join-Path $env:TEMP "tp-msg.json"
[IO.File]::WriteAllText($msg, '[{"role":"user","content":[{"text":"Responde solo: ok"}]}]')
$root = Resolve-Path "$PSScriptRoot\..\.."
$out = @()
foreach ($m in $models) {
  # cmd /c une stdout+stderr a nivel del sistema: así PowerShell 5.1 no convierte los errores en excepciones.
  $r = cmd /c "aws bedrock-runtime converse --model-id $m --messages file://$msg --inference-config maxTokens=10 --region $Region --profile $Profile --query output.message.content[0].text --output text 2>&1"
  $ok = ($LASTEXITCODE -eq 0)
  $line = "{0,-50} {1}" -f $m, $(if ($ok) { "OK" } else { "FALLA: " + (($r | Out-String).Trim() -split "`n")[-1] })
  Write-Host $line -ForegroundColor $(if ($ok) { "Green" } else { "DarkGray" })
  $out += $line
}
$out | Out-File -Encoding utf8 "$root\models-test.txt"
