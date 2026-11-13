# Paso 3: construye el frontend con las salidas del stack y lo publica en S3 + CloudFront.
# Uso:  .\scripts\windows\3-deploy-frontend.ps1 [-Profile tripplanner] [-Region us-east-1] [-AgentArn arn:...]
param([string]$Profile = "tripplanner", [string]$Region = "us-east-1", [string]$Stack = "tripplanner-backend",
      [string]$AgentArn = "")
. "$PSScriptRoot\_common.ps1"
Assert-Command npm "Instala Node.js 20+ (nodejs.org)."
Use-AwsProfile $Profile

$root = Resolve-Path "$PSScriptRoot\..\.."
if (-not $AgentArn -and (Test-Path "$root\agent\.agent_arn")) { $AgentArn = (Get-Content "$root\agent\.agent_arn" -Raw).Trim() }
if (-not $AgentArn) { throw "Falta el Agent ARN. Ejecuta primero 2-deploy-agent.ps1 o pasa -AgentArn." }

Push-Location "$root\frontend"
try {
    @"
VITE_AWS_REGION=$Region
VITE_API_URL=$(Get-StackOutput $Stack $Region 'ApiUrl')
VITE_USER_POOL_ID=$(Get-StackOutput $Stack $Region 'UserPoolId')
VITE_USER_POOL_CLIENT_ID=$(Get-StackOutput $Stack $Region 'UserPoolClientId')
VITE_AGENT_RUNTIME_ARN=$AgentArn
VITE_AGENT_MODE=cloudfront
VITE_MOCK=false
"@ | Set-Content -Encoding ascii ".env.production.local"

    npm ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci falló" }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "npm run build falló" }

    $bucket = Get-StackOutput $Stack $Region "FrontendBucketName"
    aws s3 sync dist/ "s3://$bucket/" --delete --exclude index.html --cache-control "public,max-age=31536000,immutable"
    aws s3 cp dist/index.html "s3://$bucket/index.html" --cache-control "no-cache"
    aws cloudfront create-invalidation --distribution-id (Get-StackOutput $Stack $Region "FrontendDistributionId") --paths "/index.html" | Out-Null
    Write-Host "`n✅ Frontend publicado en: $(Get-StackOutput $Stack $Region 'FrontendUrl')" -ForegroundColor Green
} finally { Pop-Location }
