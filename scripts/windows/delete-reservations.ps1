# Elimina TODAS las reservas (RES#...) de un usuario en DynamoDB. No toca viajes, itinerarios ni perfil.
# Uso:  .\scripts\windows\delete-reservations.ps1 [-Email carlostorrecilla15@gmail.com]
param([string]$Profile = "tripplanner", [string]$Region = "us-east-1", [string]$Stack = "tripplanner-ai",
      [string]$Email = "carlostorrecilla15@gmail.com", [string]$Table = "tripplanner-data")
$ErrorActionPreference = "Stop"; $env:AWS_PAGER = ""; $env:PYTHONUTF8 = "1"

$pool = aws cloudformation describe-stacks --stack-name $Stack --region $Region --profile $Profile `
          --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" --output text
# Se filtra en PowerShell (no con --filter) para evitar problemas de comillas en PowerShell 5.1.
$users = (aws cognito-idp list-users --user-pool-id $pool.Trim() --region $Region --profile $Profile --output json | ConvertFrom-Json).Users
$user = $users | Where-Object { ($_.Attributes | Where-Object Name -eq "email").Value -eq $Email.ToLower() } | Select-Object -First 1
if (-not $user) { throw "No encontré el usuario $Email" }
$pk = "USER#$($user.Username)"

$vals = Join-Path $env:TEMP "tp-vals.json"
[IO.File]::WriteAllText($vals, (@{ ":pk" = @{ S = $pk }; ":r" = @{ S = "RES#" } } | ConvertTo-Json -Compress))
$items = aws dynamodb query --table-name $Table --region $Region --profile $Profile `
          --key-condition-expression "PK = :pk AND begins_with(SK, :r)" `
          --expression-attribute-values "file://$vals" --output json | ConvertFrom-Json
$list = @($items.Items)
if ($list.Count -eq 0) { Write-Host "No hay reservas para $Email."; return }

Write-Host "`nReservas de $Email que se van a ELIMINAR:" -ForegroundColor Yellow
foreach ($it in $list) { Write-Host ("  {0}  {1}  {2}" -f $it.SK.S, $it.confirmationCode.S, $it.title.S) }
$ok = Read-Host "`nEsto es permanente y no se puede deshacer. Escribe SI para eliminar $($list.Count) reserva(s)"
if ($ok -cne "SI") { Write-Host "Cancelado. No se eliminó nada."; return }

$keyFile = Join-Path $env:TEMP "tp-key.json"
foreach ($it in $list) {
  [IO.File]::WriteAllText($keyFile, (@{ PK = @{ S = $pk }; SK = @{ S = $it.SK.S } } | ConvertTo-Json -Compress))
  aws dynamodb delete-item --table-name $Table --key "file://$keyFile" --region $Region --profile $Profile
  Write-Host "  eliminada $($it.SK.S)"
}
Write-Host "`nListo: $($list.Count) reserva(s) eliminada(s)." -ForegroundColor Green
