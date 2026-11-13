#!/usr/bin/env bash
# Despliega el Orchestrator (con Flight y Weather Agents + MCPs) en AgentCore Runtime.
# Requisitos: pip install -r requirements-dev.txt ; stack SAM ya desplegado.
# Uso: ./scripts/deploy_agent.sh <stack-name> [region]
set -euo pipefail
STACK=${1:-tripplanner-ai}
REGION=${2:-us-east-1}
export AGENTCORE_SUPPRESS_RECOMMENDATION=1
out() { aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
          --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }

DISCOVERY=$(out CognitoDiscoveryUrl)
CLIENT_ID=$(out UserPoolClientId)
TOOLS=$(out ToolFunctionNames)
POLICY_ARN=$(out AgentToolsInvokePolicyArn)
MEMORY_ID=${MEMORY_ID:-}

# 1) Configurar: entrypoint, autorización JWT con Cognito y reenvío del header Authorization
agentcore configure --entrypoint main.py --name tripplanner_orchestrator \
  --requirements-file requirements.txt --region "$REGION" --non-interactive \
  --authorizer-config "{\"customJWTAuthorizer\":{\"discoveryUrl\":\"$DISCOVERY\",\"allowedClients\":[\"$CLIENT_ID\"]}}" \
  --request-header-allowlist "Authorization"

# 2) Desplegar con variables de entorno
agentcore deploy --auto-update-on-conflict \
  --env "AWS_REGION=$REGION" --env "TOOL_FUNCTIONS=$TOOLS" --env "MEMORY_ID=$MEMORY_ID"

# 3) Dar permiso al rol de ejecución para invocar SOLO las Lambdas de las Tools
ROLE_ARN=$(python3 - <<'PY'
import yaml
c = yaml.safe_load(open(".bedrock_agentcore.yaml"))
a = c["agents"][c.get("default_agent") or next(iter(c["agents"]))]
print(a["aws"]["execution_role"])
PY
)
ROLE_NAME=${ROLE_ARN##*/}
aws iam attach-role-policy --role-name "$ROLE_NAME" --policy-arn "$POLICY_ARN"
echo "✅ Política $POLICY_ARN adjuntada a $ROLE_NAME"
agentcore status | grep -i "arn:aws:bedrock-agentcore" || true
echo "Copia el Agent ARN en frontend/.env (VITE_AGENT_RUNTIME_ARN)."
