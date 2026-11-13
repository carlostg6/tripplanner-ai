/**
 * Autenticación con Amazon Cognito (SRP). El navegador solo maneja tokens del
 * usuario: no hay credenciales ni secretos de AWS en el frontend.
 */
import {
  AuthenticationDetails,
  CognitoUser,
  CognitoUserAttribute,
  CognitoUserPool,
} from "amazon-cognito-identity-js";
import { config } from "../config";

let pool;
function getPool() {
  if (!pool) pool = new CognitoUserPool({ UserPoolId: config.userPoolId, ClientId: config.userPoolClientId });
  return pool;
}

const MOCK_KEY = "tp_mock_user";

/** El correo es el usuario: se normaliza (minúsculas, sin espacios) para que
 *  "Carlos@x.com" y "carlos@x.com" sean siempre la misma cuenta. */
const norm = (email) => (email || "").trim().toLowerCase();

export function signUp(rawEmail, password, name) {
  const email = norm(rawEmail);
  if (config.mock) return Promise.resolve();
  const attrs = [new CognitoUserAttribute({ Name: "email", Value: email })];
  if (name) attrs.push(new CognitoUserAttribute({ Name: "name", Value: name }));
  return new Promise((resolve, reject) =>
    getPool().signUp(email, password, attrs, null, (err, res) => (err ? reject(err) : resolve(res))),
  );
}

export function confirmSignUp(rawEmail, code) {
  const email = norm(rawEmail);
  if (config.mock) return Promise.resolve();
  const user = new CognitoUser({ Username: email, Pool: getPool() });
  return new Promise((resolve, reject) =>
    user.confirmRegistration(code, true, (err, res) => (err ? reject(err) : resolve(res))),
  );
}

export function signIn(rawEmail, password) {
  const email = norm(rawEmail);
  if (config.mock) {
    const u = { sub: "mock-user", email, name: email.split("@")[0] };
    localStorage.setItem(MOCK_KEY, JSON.stringify(u));
    return Promise.resolve(u);
  }
  const user = new CognitoUser({ Username: email, Pool: getPool() });
  const details = new AuthenticationDetails({ Username: email, Password: password });
  return new Promise((resolve, reject) =>
    user.authenticateUser(details, {
      onSuccess: (session) => resolve(userFromSession(session)),
      onFailure: reject,
    }),
  );
}

export function signOut() {
  if (config.mock) return localStorage.removeItem(MOCK_KEY);
  getPool().getCurrentUser()?.signOut();
}

function userFromSession(session) {
  const p = session.getIdToken().decodePayload();
  return { sub: p.sub, email: p.email, name: p.name || (p.email || "").split("@")[0] };
}

/** Sesión vigente (refresca tokens automáticamente). */
export function currentSession() {
  if (config.mock) {
    const u = localStorage.getItem(MOCK_KEY);
    return Promise.resolve(u ? { user: JSON.parse(u), accessToken: "mock" } : null);
  }
  const user = getPool().getCurrentUser();
  if (!user) return Promise.resolve(null);
  return new Promise((resolve) =>
    user.getSession((err, session) => {
      if (err || !session?.isValid()) return resolve(null);
      resolve({ user: userFromSession(session), accessToken: session.getAccessToken().getJwtToken() });
    }),
  );
}

/** Access token de Cognito: lo validan API Gateway (JWT authorizer) y AgentCore (customJWTAuthorizer). */
export async function getAccessToken() {
  const s = await currentSession();
  if (!s) throw new Error("Tu sesión expiró. Ingresa de nuevo.");
  return s.accessToken;
}
