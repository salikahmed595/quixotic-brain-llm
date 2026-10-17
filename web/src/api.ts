/* Backend client. No mock data: everything is read from, or written to, the FastAPI backend (/v1/...).
   Sign-in is a server-side session in an HttpOnly cookie (PRD §5 FR-AUTH-06); the page never sees the session token.
   Every write sends the session's CSRF token (readable `qb_csrf` cookie) in the X-CSRF-Token header. */

const API = ((window as unknown as { QB_API?: string }).QB_API || new URLSearchParams(location.search).get('api') || '').replace(/\/$/, '');

export const storage = {
  get(k: string): string | null { try { return localStorage.getItem(k); } catch { return null; } },
  set(k: string, v: string | null) { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch { /* private mode */ } },
};
export const session = {
  get(k: string): string | null { try { return sessionStorage.getItem(k); } catch { return null; } },
  set(k: string, v: string | null) { try { if (v == null) sessionStorage.removeItem(k); else sessionStorage.setItem(k, v); } catch { /* private mode */ } },
};

const csrf = () => document.cookie.split('; ').find(c => c.startsWith('qb_csrf='))?.slice(8) ?? '';

let onExpired: () => void = () => {};
let onMfa: () => void = () => {};
export const onSessionExpired = (fn: () => void) => { onExpired = fn; };
export const onMfaRequired = (fn: () => void) => { onMfa = fn; };

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

type Opts = { method?: string; body?: unknown; form?: FormData };
const PUBLIC = ['/v1/auth/login', '/v1/auth/session', '/v1/auth/register', '/v1/auth/verify-email', '/v1/auth/password-reset'];

export async function api<T = any>(path: string, { method = 'GET', body, form }: Opts = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (method !== 'GET') headers['X-CSRF-Token'] = decodeURIComponent(csrf());
  let payload: BodyInit | undefined;
  if (form) payload = form;
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body); }
  let res: Response;
  try { res = await fetch(API + path, { method, headers, body: payload, credentials: 'include' }); }
  catch { throw new ApiError('Cannot reach the server. Check your connection and try again.', 0); }
  if (res.status === 204) return null as T;
  let data: any = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (res.status === 401 && !PUBLIC.some(p => path.startsWith(p))) {
    if (data?.detail === 'mfa_required') { onMfa(); throw new ApiError('Please finish two-step sign-in.', 401); }
    onExpired();
    throw new ApiError('Your session has ended. Please sign in again.', 401);
  }
  if (!res.ok) {
    let msg = data && data.detail;
    if (Array.isArray(msg)) msg = msg.map((x: { msg: string }) => x.msg).join('; ');
    throw new ApiError(msg || `Something went wrong (${res.status}).`, res.status);
  }
  return data as T;
}
