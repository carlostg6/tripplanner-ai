# Paso 2: Orchestrator + Flight + Weather (con MCPs) en Amazon Bedrock AgentCore Runtime.
# Usa el Starter Toolkit de Python dentro de un entorno virtual propio (no choca con la CLI npm @aws/agentcore).
# Uso:  .\scripts\windows\2-deploy-agent.ps1 [-Profile tripplanner] [-Region us-east-1] [-CreateMemory]
param([string]$Profile = "tripplanner", [string]$Region = "us-east-1", [string]$Stack = "tripplanner-ai",
      [switch]$CreateMemory,
      [string]$OrchestratorModel = "us.anthropic.claude-sonnet-4-6",
      [string]$SpecialistModel = "us.anthropic.claude-haiku-4-5-20251001-v1:0",
      # Clave de SerpAPI para vuelos reales de Google Flights. Si se omite se toma de $env:SERPAPI_KEY;
      # vacía = vuelos simulados. Nunca se escribe en el repositorio.
      [string]$SerpApiKey = $env:SERPAPI_KEY)
. "$PSScriptRoot\_common.ps1"
Assert-Command python "Instala Python 3.12+ (python.org) y marca 'Add to PATH'."
Use-AwsProfile $Profile
$env:AGENTCORE_SUPPRESS_RECOMMENDATION = "1"

Push-Location "$PSScriptRoot\..\..\agent"
try {
    if (-not (Test-Path ".venv\Scripts\python.exe")) { python -m venv .venv }
    $py = Resolve-Path ".venv\Scripts\python.exe"
    $ac = ".venv\Scripts\agentcore.exe"
    & $py -m pip install --quiet --upgrade pip
    & $py -m pip install --quiet -r requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { throw "pip install falló" }

    $discovery = Get-StackOutput $Stack $Region "CognitoDiscoveryUrl"
    $clientId  = Get-StackOutput $Stack $Region "UserPoolClientId"
    $tools     = Get-StackOutput $Stack $Region "ToolFunctionNames"
    $policyArn = Get-StackOutput $Stack $Region "AgentToolsInvokePolicyArn"

    # Memoria de AgentCore (corto + largo plazo). Se guarda el id en .memory_id para reutilizarlo.
    $memoryId = ""
    if (Test-Path ".memory_id") { $memoryId = (Get-Content ".memory_id" -Raw).Trim() }
    if (-not $memoryId -and $CreateMemory) {
        $out = & $py scripts\create_memory.py --region $Region
        $memoryId = (($out | Select-String "MEMORY_ID =") -replace ".*MEMORY_ID =\s*", "").Trim()
        if ($memoryId) { Set-Content ".memory_id" $memoryId }
    }
    Write-Host "Vuelos: $(if ($SerpApiKey) { 'Google Flights real (SerpAPI)' } else { 'simulados (sin SERPAPI_KEY)' })"
    Write-Host "MEMORY_ID: $(if ($memoryId) { $memoryId } else { '(sin memoria AgentCore; usa -CreateMemory)' })"

    # PowerShell 5.1 elimina comillas al pasar JSON a ejecutables: se escapan a mano.
    $auth = @{ customJWTAuthorizer = @{ discoveryUrl = $discovery; allowedClients = @($clientId) } } |
            ConvertTo-Json -Compress -Depth 5
    if ($PSVersionTable.PSVersion -lt [version]"7.3") { $auth = $auth -replace '"', '\"' }

    & $ac configure --entrypoint main.py --name tripplanner_orchestrator --requirements-file requirements.txt `
        --region $Region --non-interactive --disable-memory --authorizer-config $auth --request-header-allowlist "Authorization"
    if ($LASTEXITCODE -ne 0) { throw "agentcore configure falló" }

    & $ac deploy --auto-update-on-conflict `
        --env "TOOL_FUNCTIONS=$tools" --env "MEMORY_ID=$memoryId" `
        --env "ORCHESTRATOR_MODEL_ID=$OrchestratorModel" `
        --env "SPECIALIST_MODEL_ID=$SpecialistModel" `
        --env "SERPAPI_KEY=$SerpApiKey"
    if ($LASTEXITCODE -ne 0) { throw "agentcore deploy falló" }

    $info = & $py -c @"
import yaml
c = yaml.safe_load(open('.bedrock_agentcore.yaml'))
a = c['agents'][c.get('default_agent') or next(iter(c['agents']))]
print(a['aws']['execution_role']); print((a.get('bedrock_agentcore') or {}).get('agent_arn') or '')
"@
    $roleArn, $agentArn = $info
    $roleName = $roleArn.Split("/")[-1]
    aws iam attach-role-policy --role-name $roleName --policy-arn $policyArn
    if ($LASTEXITCODE -ne 0) { throw "No se pudo adjuntar la política al rol $roleName" }
    if ($memoryId) {
        # Permiso de mínimo privilegio para usar SOLO esta memoria de AgentCore.
        $acct = aws sts get-caller-identity --query Account --output text
        $memPolicy = @{ Version = "2012-10-17"; Statement = @(@{ Sid = "TripPlannerMemoryAccess"; Effect = "Allow";
            Action = @("bedrock-agentcore:CreateEvent","bedrock-agentcore:GetEvent","bedrock-agentcore:ListEvents",
                       "bedrock-agentcore:DeleteEvent","bedrock-agentcore:ListSessions","bedrock-agentcore:RetrieveMemoryRecords",
                       "bedrock-agentcore:ListMemoryRecords","bedrock-agentcore:GetMemoryRecord","bedrock-agentcore:GetMemory");
            Resource = "arn:aws:bedrock-agentcore:${Region}:${acct}:memory/$memoryId" }) } | ConvertTo-Json -Depth 6
        $tmp = Join-Path $env:TEMP "tp-memory-policy.json"
        [IO.File]::WriteAllText($tmp, $memPolicy)
        aws iam put-role-policy --role-name $roleName --policy-name TripPlannerMemoryAccess --policy-document "file://$tmp"
    }
    Set-Content ".agent_arn" $agentArn
    Write-Host "`n✅ Agente desplegado." -ForegroundColor Green
    Write-Host "Rol: $roleName (con política $policyArn)"
    Write-Host "Agent ARN: $agentArn" -ForegroundColor Yellow
} finally { Pop-Location }
