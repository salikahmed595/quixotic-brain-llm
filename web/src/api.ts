/* Backend client. No mock data: everything is read from, or written to, the FastAPI backend (/v1/...).
   Sign-in still uses the bearer token the current backend issues; M1 replaces it with HttpOnly session cookies
   (PRD §5 FR-AUTH-06, docs/P0_PLAN.md). */

const API = ((window as unknown as { QB_API?: string }).QB_API || new URLSearchParams(location.search).get('api') || '').replace(/\/$/, '');
const TOKEN_KEY = 'qb_token';

export const storage = {
  get(k: string): string | null { try { return localStorage.getItem(k); } catch { return null; } },
  set(k: string, v: string | null) { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch { /* private mode */ } },
};
export const session = {
  get(k: string): string | null { try { return sessionStorage.getItem(k); } catch { return null; } },
  set(k: string, v: string | null) { try { if (v == null) sessionStorage.removeItem(k); else sessionStorage.setItem(k, v); } catch { /* private mode */ } },
};

let token: string | null = storage.get(TOKEN_KEY);
let onExpired: () => void = () => {};
export const setToken = (t: string | null) => { token = t; storage.set(TOKEN_KEY, t); };
export const hasToken = () => !!token;
export const onSessionExpired = (fn: () => void) => { onExpired = fn; };

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

type Opts = { method?: string; body?: unknown; form?: FormData };

export async function api<T = any>(path: string, { method = 'GET', body, form }: Opts = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = 'Bearer ' + token;
  let payload: BodyInit | undefined;
  if (form) payload = form;
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body); }
  let res: Response;
  try { res = await fetch(API + path, { method, headers, body: payload }); }
  catch { throw new ApiError('Cannot reach the server. Check your connection and try again.', 0); }
  if (res.status === 401 && token && path !== '/v1/auth/login') {
    setToken(null); onExpired();
    throw new ApiError('Your session has ended. Please sign in again.', 401);
  }
  if (res.status === 204) return null as T;
  let data: any = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    let msg = data && data.detail;
    if (Array.isArray(msg)) msg = msg.map((x: { msg: string }) => x.msg).join('; ');
    throw new ApiError(msg || `Something went wrong (${res.status}).`, res.status);
  }
  return data as T;
}
