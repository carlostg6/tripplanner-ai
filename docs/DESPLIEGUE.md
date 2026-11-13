# Despliegue desde cero

## Windows (PowerShell): ruta rápida

Es el camino con el que se desplegó el proyecto en la cuenta del equipo.

Requisitos:
- AWS CLI v2 con sesión iniciada (`aws login --region us-east-1 --profile tripplanner`).
- **AWS SAM CLI** (`winget install --id Amazon.SAM-CLI -e`).
- **Python 3.10+** y **Node.js 20+**.
- Acceso en Bedrock a los modelos del agente. Se verifica con `.\scripts\windows\test-models.ps1`.

```powershell
cd C:\Users\Carlo\workshop-a2a\tripplanner-ai
Set-ExecutionPolicy -Scope Process Bypass        # permite ejecutar los scripts solo en esta ventana
.\scripts\windows\1-deploy-backend.ps1           # Cognito, API, Lambdas, DynamoDB, S3, CloudFront (~10 min)
.\scripts\windows\2-deploy-agent.ps1 -CreateMemory   # agentes en AgentCore + memoria (~10 min)
.\scripts\windows\3-deploy-frontend.ps1          # build + publicación del frontend
```

Scripts de apoyo:

| Script | Uso |
|---|---|
| `test-models.ps1` | Prueba qué modelos de Claude puede invocar la cuenta. Los modelos *Legacy* o no habilitados fallan aquí. |
| `logs.ps1 [-Minutes 15]` | Guarda los logs del runtime de AgentCore en `agent-logs.txt` para diagnosticar errores del chat. |
| `diag.ps1` | Muestra los ítems de DynamoDB, los usuarios de Cognito, las últimas peticiones al API y los errores de las Lambdas, en `diag.txt`. |

`2-deploy-agent.ps1` acepta `-OrchestratorModel` y `-SpecialistModel`. Los valores por defecto son `us.anthropic.claude-sonnet-4-6` y `us.anthropic.claude-haiku-4-5-20251001-v1:0`. Además, el script adjunta al rol del runtime:
- `AgentToolsInvokePolicy`, que solo permite `lambda:InvokeFunction` sobre las Lambdas de las Tools;
- una política *inline* `TripPlannerMemoryAccess`, que solo da acceso a la memoria creada.

Los scripts toman credenciales temporales del perfil con `aws configure export-credentials`, así que funcionan con sesiones de `aws login`. Al final muestran la URL de la aplicación.

---

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
./scripts/deploy_agent.sh tripplanner-ai us-east-1
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
AGENT_RUNTIME_ARN=<Agent ARN> ./scripts/deploy_frontend.sh tripplanner-ai us-east-1
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

Estos problemas aparecieron durante el despliegue real y así se resolvieron:

| Síntoma | Causa | Solución |
|---|---|---|
| El chat dice "El asistente tuvo un problema…" y el log muestra `This Model is marked by provider as Legacy` | El modelo configurado quedó obsoleto en Bedrock. | Ejecutar `test-models.ps1` y volver a desplegar con un modelo que responda OK. |
| El log muestra `… is not available for this account` | El modelo aparece como ACTIVE, pero la cuenta no tiene acceso. | Igual que el caso anterior: elegir un modelo que funcione en la cuenta. |
| Después de volver a desplegar, el agente sigue usando la configuración vieja | Cada sesión de AgentCore sigue en su contenedor original hasta que se apaga por inactividad (~15 min). | En la app, hacer clic en **Nueva conversación**, que crea un nuevo `sessionId`. |
| `AccessDeniedException … bedrock-agentcore:ListEvents` | Al rol del runtime le faltaba el permiso de memoria. | Ahora lo agrega `2-deploy-agent.ps1`. El agente sigue funcionando con memoria local si el permiso falta. |
| Al volver a entrar, *Mis viajes* aparece vacío | Se creó una segunda cuenta: en el User Pool, "Carlos@…" y "carlos@…" eran usuarios distintos. | El frontend ahora pasa el correo a minúsculas. Para corregir una cuenta existente se usa `admin-update-user-attributes`. |
| `sam deploy` responde "Update of resource type is not permitted" | Ya existía otro stack con el mismo nombre. | Usar un nombre de stack propio: `tripplanner-ai`. |
| `aws` en PowerShell responde `'charmap' codec can't encode` | Codificación de la consola de Windows. | `$env:PYTHONUTF8="1"` (los scripts ya lo hacen). |

### Otros síntomas

| Síntoma | Solución |
|---|---|
| El chat responde 401/403 | El token no es un *access token* del mismo `client_id`, o el runtime no tiene el autorizador JWT configurado. Vuelve a ejecutar `deploy_agent.sh`. |
| El agente responde "No autenticado: falta el token" | Falta `--request-header-allowlist Authorization` en la configuración del runtime. |
| Las Tools devuelven `UNAVAILABLE` o `AccessDenied` | No se adjuntó `AgentToolsInvokePolicy` al rol del runtime, o `TOOL_FUNCTIONS` tiene nombres incorrectos. |
| `AccessDeniedException` del modelo | Habilita el modelo en la consola de Bedrock o cambia `ORCHESTRATOR_MODEL_ID` / `SPECIALIST_MODEL_ID`. |
| Error de CORS en el chat con `VITE_AGENT_MODE=direct` | Usa `cloudfront`: mismo dominio, sin CORS. |
| El clima falla | El runtime necesita salida a Internet hacia `*.open-meteo.com`. Es el modo de red público por defecto. |
