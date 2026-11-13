# Despliegue desde cero

## Requisitos

- Cuenta de AWS con acceso a modelos de **Amazon Bedrock**. Habilita Claude Sonnet y Claude Haiku en la región, o cambia los IDs de modelo en `agent/.env.example`.
- AWS CLI v2 configurado (`aws configure`), con permisos para CloudFormation, IAM, Lambda, API Gateway, DynamoDB, Cognito, S3, CloudFront, ECR, CodeBuild y Bedrock AgentCore.
- AWS SAM CLI ≥ 1.100, Python 3.12+, Node.js 20+ y Git.
- Región recomendada: `us-east-1`.

---

## Paso 1 · Backend serverless (SAM)

```bash
cd backend
pip install -r requirements-dev.txt
pytest -q                  # 7 pruebas con DynamoDB simulado
sam build
sam deploy --guided        # la primera vez; luego basta con `sam deploy`
```

Este paso crea Cognito, API Gateway, las 14 Lambdas, la tabla DynamoDB, el bucket S3, CloudFront y la política `AgentToolsInvokePolicy`.

Al terminar, anota estas salidas: `ApiUrl`, `UserPoolId`, `UserPoolClientId`, `CognitoDiscoveryUrl`, `ToolFunctionNames`, `FrontendUrl` y `AgentToolsInvokePolicyArn`.

> CloudFront tarda entre 5 y 15 minutos en quedar disponible la primera vez.

## Paso 2 · Memoria de AgentCore (opcional, recomendado)

```bash
cd agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/create_memory.py --region us-east-1
export MEMORY_ID=<id impreso>
```

## Paso 3 · Agentes en AgentCore Runtime

```bash
cd agent
pytest -q                                   # 4 pruebas sin Bedrock
./scripts/deploy_agent.sh tripplanner-backend us-east-1
```

El script `deploy_agent.sh` hace lo siguiente:

1. Ejecuta `agentcore configure` con:
   - `customJWTAuthorizer`, que usa el discovery URL de Cognito y el `client_id` de la app;
   - `--request-header-allowlist Authorization`, para que el agente reciba el token del usuario.
2. Ejecuta `agentcore deploy` con las variables `TOOL_FUNCTIONS` y `MEMORY_ID`. El build se hace en CodeBuild y no necesita Docker local.
3. Adjunta `AgentToolsInvokePolicy` al rol de ejecución del runtime.

Al final aparece el **Agent ARN** con la forma `arn:aws:bedrock-agentcore:us-east-1:<cuenta>:runtime/tripplanner_orchestrator-XXXX`.

> El *Starter Toolkit* de Python (`agentcore configure/deploy`) sigue funcionando, pero AWS recomienda la nueva CLI `@aws/agentcore` (npm). Si en el taller usaste esa CLI, configura los mismos tres elementos: el autorizador JWT de Cognito, el header `Authorization` permitido y las variables de entorno.

### Prueba rápida del agente

```bash
TOKEN=$(aws cognito-idp initiate-auth --auth-flow USER_PASSWORD_AUTH ...)   # o copia el token desde el navegador
agentcore invoke '{"prompt":"Hola"}' --bearer-token "$TOKEN"
```

## Paso 4 · Frontend

```bash
AGENT_RUNTIME_ARN=<Agent ARN> ./scripts/deploy_frontend.sh tripplanner-backend us-east-1
```

El script genera `.env.production.local` con las salidas del stack, construye el frontend con Vite, lo sube a S3 e invalida la caché de CloudFront.

Abre la `FrontendUrl` (`https://dxxxx.cloudfront.net`), regístrate con tu correo, confirma el código y sigue [DEMO.md](DEMO.md).

---

## Desarrollo local

| Qué | Cómo |
|---|---|
| Solo la UI, sin AWS | `cd frontend && cp .env.example .env && VITE_MOCK=true npm run dev`. Los datos y el agente se simulan en el navegador; usar solo para diseño. |
| Agente local + backend en AWS | `cd agent && ALLOW_INSECURE_LOCAL_USER=true LOCAL_CORS_ORIGIN=http://localhost:5173 TOOL_FUNCTIONS=... python main.py`, y en el frontend `VITE_AGENT_MODE=local`. |
| Lambdas locales | `cd backend && sam local invoke CreateTripFunction -e events/create_trip.json` |

## Limpieza

```bash
cd agent && agentcore destroy
aws s3 rm s3://<FrontendBucketName> --recursive
cd backend && sam delete
```

La tabla DynamoDB tiene `DeletionPolicy: Retain`, así que hay que borrarla a mano si ya no se necesita.

## Problemas comunes

| Síntoma | Solución |
|---|---|
| El chat responde 401/403 | El token no es un *access token* del mismo `client_id`, o el runtime no tiene el autorizador JWT configurado. Vuelve a ejecutar `deploy_agent.sh`. |
| El agente responde "No autenticado: falta el token" | Falta `--request-header-allowlist Authorization` en la configuración del runtime. |
| Las Tools devuelven `UNAVAILABLE` o `AccessDenied` | No se adjuntó `AgentToolsInvokePolicy` al rol del runtime, o `TOOL_FUNCTIONS` tiene nombres incorrectos. |
| `AccessDeniedException` del modelo | Habilita el modelo en la consola de Bedrock o cambia `ORCHESTRATOR_MODEL_ID` / `SPECIALIST_MODEL_ID`. |
| Error de CORS en el chat con `VITE_AGENT_MODE=direct` | Usa `cloudfront`: mismo dominio, sin CORS. |
| El clima falla | El runtime necesita salida a Internet hacia `*.open-meteo.com`. Es el modo de red público por defecto. |
