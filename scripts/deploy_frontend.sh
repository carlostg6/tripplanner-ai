#!/usr/bin/env bash
# Construye el frontend con las salidas del stack y lo publica en S3 + CloudFront.
# Uso: AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:... ./scripts/deploy_frontend.sh [stack] [region]
set -euo pipefail
STACK=${1:-tripplanner-backend}
REGION=${2:-us-east-1}
: "${AGENT_RUNTIME_ARN:?Define AGENT_RUNTIME_ARN (salida de 'agentcore status')}"
out() { aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
          --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }

cd "$(dirname "$0")/../frontend"
cat > .env.production.local <<ENV
VITE_AWS_REGION=$REGION
VITE_API_URL=$(out ApiUrl)
VITE_USER_POOL_ID=$(out UserPoolId)
VITE_USER_POOL_CLIENT_ID=$(out UserPoolClientId)
VITE_AGENT_RUNTIME_ARN=$AGENT_RUNTIME_ARN
VITE_AGENT_MODE=cloudfront
VITE_MOCK=false
ENV
npm ci
npm run build
BUCKET=$(out FrontendBucketName)
aws s3 sync dist/ "s3://$BUCKET/" --delete --cache-control "public,max-age=31536000,immutable" --exclude index.html
aws s3 cp dist/index.html "s3://$BUCKET/index.html" --cache-control "no-cache"
aws cloudfront create-invalidation --distribution-id "$(out FrontendDistributionId)" --paths "/index.html" >/dev/null
echo "✅ Frontend publicado en $(out FrontendUrl)"
