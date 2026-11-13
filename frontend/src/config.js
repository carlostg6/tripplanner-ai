const env = import.meta.env;

export const config = {
  region: env.VITE_AWS_REGION || "us-east-1",
  apiUrl: (env.VITE_API_URL || "").replace(/\/$/, ""),
  userPoolId: env.VITE_USER_POOL_ID || "",
  userPoolClientId: env.VITE_USER_POOL_CLIENT_ID || "",
  agentRuntimeArn: env.VITE_AGENT_RUNTIME_ARN || "",
  agentMode: env.VITE_AGENT_MODE || "cloudfront",
  mock: String(env.VITE_MOCK) === "true",
};

/** URL del endpoint HTTP streaming de AgentCore (canal 2, sin API Gateway). */
export function agentInvocationUrl() {
  if (config.agentMode === "local") return "http://localhost:8080/invocations";
  const path = `/runtimes/${encodeURIComponent(config.agentRuntimeArn)}/invocations?qualifier=DEFAULT`;
  if (config.agentMode === "direct") return `https://bedrock-agentcore.${config.region}.amazonaws.com${path}`;
  return `${window.location.origin}${path}`; // cloudfront: mismo dominio → sin CORS
}
