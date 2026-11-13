# Guarda los logs recientes del agente en agent-logs.txt (raíz del proyecto) para diagnosticar errores.
# Uso:  .\scripts\windows\logs.ps1 [-Minutes 15]
param([string]$Profile = "tripplanner", [string]$Region = "us-east-1", [int]$Minutes = 15)
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"; $env:AWS_PAGER = ""
$root = Resolve-Path "$PSScriptRoot\..\.."
$arn = (Get-Content "$root\agent\.agent_arn" -Raw).Trim()
$id = $arn.Split("/")[-1]
aws logs tail "/aws/bedrock-agentcore/runtimes/$id-DEFAULT" --since "$($Minutes)m" --region $Region --profile $Profile |
    Out-File -Encoding utf8 "$root\agent-logs.txt"
Write-Host "Logs guardados en $root\agent-logs.txt"
