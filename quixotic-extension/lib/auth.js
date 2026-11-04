// Sign-in with the employee's own Quixotic AI account (backend/api/v1/auth.py). The browser keeps the httpOnly
// session cookie; the extension keeps only the CSRF token. The password is sent once and never stored.
export const QUIXOTIC_URL='https://maqsad.quixoticcreatives.com';   // must match manifest host_permissions

const detail=async r=>{try{return (await r.json())?.detail;}catch{return undefined;}};

export async function signIn({identifier,password},fetchFn=fetch){
  const id=String(identifier||'').trim();
  if(!id) throw new Error('Enter your Quixotic AI username or email.');
  if(!password) throw new Error('Enter your password.');
  const r=await fetchFn(`${QUIXOTIC_URL}/v1/auth/login`,{method:'POST',credentials:'include',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({identifier:id,password})});
  if(r.status===401) throw new Error('Wrong username or password.');
  if(r.status===403||r.status===429) throw new Error((await detail(r))||`Sign-in refused (HTTP ${r.status}).`);
  if(!r.ok) throw new Error(`Sign-in failed (HTTP ${r.status}).`);
  const data=await r.json();
  // PRD gap: two-step sign-in (admin roles, FR-AUTH-06) is not built into the extension yet.
  if(data.mfa&&data.mfa!=='none') throw new Error('This account needs two-step sign-in. Use a regular employee account, or sign in on the website.');
  if(!data.csrf_token) throw new Error('Sign-in failed: no session returned.');
  return {csrf:data.csrf_token};
}

export async function signOut({csrf},fetchFn=fetch){
  const r=await fetchFn(`${QUIXOTIC_URL}/v1/auth/logout`,{method:'POST',credentials:'include',headers:{'X-CSRF-Token':csrf}});
  if(!r.ok&&r.status!==401) throw new Error(`Sign-out failed (HTTP ${r.status}).`);
}
