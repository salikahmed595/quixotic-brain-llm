// Quixotic AI client: POST /v1/ask as the signed-in employee (their own permissions; backend/api/v1/ask.py).
export async function askQuixotic({apiUrl,headers,question},fetchFn=fetch){
  const response=await fetchFn(`${String(apiUrl).replace(/\/+$/,'')}/v1/ask`,{method:'POST',credentials:'include',
    headers:{'Content-Type':'application/json',...headers},body:JSON.stringify({question})});
  if(response.status===401) throw new Error('Please sign in to Quixotic AI again.');
  if(!response.ok) throw new Error(`Quixotic AI HTTP ${response.status}`);
  const data=await response.json();
  if(typeof data?.answer!=='string'||!data.answer.trim()) throw new Error('Quixotic AI returned no answer');
  return {answer:data.answer,confidence:data.confidence};
}
