# Paso 1: backend serverless (Cognito, API Gateway, Lambdas, DynamoDB, S3, CloudFront, IAM).
# Uso:  .\scripts\windows\1-deploy-backend.ps1 [-Profile tripplanner] [-Region us-east-1]
param([string]$Profile = "tripplanner", [string]$Region = "us-east-1", [string]$Stack = "tripplanner-backend")
. "$PSScriptRoot\_common.ps1"
Assert-Command sam "Instala AWS SAM CLI: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html"
Use-AwsProfile $Profile

Push-Location "$PSScriptRoot\..\..\backend"
try {
    # Sin `sam build`: las Lambdas solo usan boto3 (incluido en el runtime), así que SAM empaqueta
    # src/ directamente y no hace falta tener Python 3.12 exacto instalado.
    sam deploy --stack-name $Stack --region $Region --resolve-s3 --no-confirm-changeset `
        --no-fail-on-empty-changeset --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM
    if ($LASTEXITCODE -ne 0) { throw "sam deploy falló" }
    Write-Host "`n✅ Backend desplegado. Salidas:" -ForegroundColor Green
    aws cloudformation describe-stacks --stack-name $Stack --region $Region --query "Stacks[0].Outputs" --output table
} finally { Pop-Location }
