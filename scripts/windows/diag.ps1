# Diagnóstico: qué hay en DynamoDB, usuarios de Cognito y últimas peticiones al API (canal 1).
# Uso:  .\scripts\windows\diag.ps1
param([string]$Profile = "tripplanner", [string]$Region = "us-east-1", [string]$Stack = "tripplanner-ai")
$ErrorActionPreference = "Continue"; $env:AWS_PAGER = ""; $env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
$root = Resolve-Path "$PSScriptRoot\..\.."
$f = "$root\diag.txt"
function Run($title, $cmd) {
  "`n===== $title =====" | Out-File -Append -Encoding utf8 $f
  (cmd /c "$cmd 2>&1") | Out-File -Append -Encoding utf8 $f
}
"Diagnóstico $(Get-Date -Format o)" | Out-File -Encoding utf8 $f
Run "DynamoDB items (PK, SK, tipo, origen)" "aws dynamodb scan --table-name tripplanner-data --projection-expression PK,SK,entityType,createdBy,createdAt --region $Region --profile $Profile --output json"
$pool = (cmd /c "aws cloudformation describe-stacks --stack-name $Stack --region $Region --profile $Profile --query Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue --output text").Trim()
Run "Usuarios Cognito ($pool)" "aws cognito-idp list-users --user-pool-id $pool --region $Region --profile $Profile --query Users[].[Username,UserStatus,UserCreateDate] --output text"
$lg = (cmd /c "aws cloudformation describe-stack-resource --stack-name $Stack --logical-resource-id ApiAccessLogs --region $Region --profile $Profile --query StackResourceDetail.PhysicalResourceId --output text").Trim()
Run "API Gateway: últimas peticiones ($lg)" "aws logs tail $lg --since 2h --region $Region --profile $Profile"
foreach ($fn in @("GetTrips","GetReservations","GetProfile","CreateTrip")) {
  Run "Lambda tripplanner-$fn (errores 2h)" "aws logs tail /aws/lambda/tripplanner-$fn --since 2h --filter-pattern ERROR --region $Region --profile $Profile"
}
Write-Host "Listo: $f"
