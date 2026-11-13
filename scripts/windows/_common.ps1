# Funciones comunes para los scripts de despliegue en Windows (PowerShell 5.1+).
$ErrorActionPreference = "Stop"
$env:AWS_PAGER = ""   # sin paginador "-- Más --" en la salida de AWS CLI

function Use-AwsProfile([string]$Profile) {
    # Exporta credenciales temporales del perfil (incluye sesiones de `aws login`)
    # como variables de entorno, para que SAM, boto3 y el toolkit de AgentCore las usen.
    $lines = aws configure export-credentials --profile $Profile --format powershell
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudieron obtener credenciales del perfil '$Profile'. Ejecuta: aws login --profile $Profile"
    }
    $lines | ForEach-Object { if ($_ -match '^\$Env:') { Invoke-Expression $_ } }
    Remove-Item Env:AWS_PROFILE -ErrorAction SilentlyContinue
    $id = aws sts get-caller-identity --query Account --output text
    Write-Host "Cuenta AWS: $id" -ForegroundColor Cyan
}

function Get-StackOutput([string]$Stack, [string]$Region, [string]$Key) {
    $v = aws cloudformation describe-stacks --stack-name $Stack --region $Region `
        --query "Stacks[0].Outputs[?OutputKey=='$Key'].OutputValue" --output text
    if ($LASTEXITCODE -ne 0 -or -not $v -or $v -eq "None") { throw "No encontré la salida '$Key' del stack $Stack." }
    return $v.Trim()
}

function Assert-Command([string]$Name, [string]$Hint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) { throw "Falta '$Name'. $Hint" }
}
