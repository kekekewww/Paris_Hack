import {MAX_COMMAND_BYTES} from './case-store.js';

const policy="default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; worker-src 'self' blob:; connect-src 'self'; object-src 'self' blob:; frame-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'";
const errors={
  VALIDATION_ERROR:[422,'案件儲存請求格式不正確。'],
  PAYLOAD_TOO_LARGE:[413,'案件資料超出暫存服務的大小限制。'],
  CASE_NOT_FOUND:[404,'找不到此案件，請重新開始。'],
  CASE_EXISTS:[409,'案件識別碼已存在。'],
  CASE_CONFLICT:[409,'案件已更新，請重新載入後再試。'],
  CASE_LIMIT:[429,'暫存案件數量已達上限，請先清除不再使用的案件。'],
};
function protectedResponse(response, noStore=false){
  const headers=new Headers(response.headers);
  for(const [name,value] of Object.entries({'Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Permissions-Policy':'camera=(), microphone=(), geolocation=()','Content-Security-Policy':policy}))headers.set(name,value);
  if(noStore)headers.set('Cache-Control','no-store');
  return new Response(response.body,{status:response.status,statusText:response.statusText,headers});
}
function error(code,message,status){return protectedResponse(Response.json({error:{code,message}},{status}),true);}
async function authorized(header, token){
  if(typeof token!=='string'||token.length<24||typeof header!=='string'||header.length>512)return false;
  const encoder=new TextEncoder();
  const [actual,expected]=await Promise.all([header,'Bearer '+token].map(value=>crypto.subtle.digest('SHA-256',encoder.encode(value))));
  const left=new Uint8Array(actual),right=new Uint8Array(expected);
  let different=0;for(let i=0;i<left.length;i++)different|=left[i]^right[i];
  return different===0;
}
async function commandBody(request){
  const reader=request.body?.getReader();
  if(!reader)throw Object.assign(new Error(),{code:'VALIDATION_ERROR'});
  let size=0;const parts=[];
  while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>MAX_COMMAND_BYTES){await reader.cancel();throw Object.assign(new Error(),{code:'PAYLOAD_TOO_LARGE'});}parts.push(value);}
  const body=new Uint8Array(size);let at=0;for(const part of parts){body.set(part,at);at+=part.length;}
  try{return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(body));}catch{throw Object.assign(new Error(),{code:'VALIDATION_ERROR'});}
}

export async function routeRequest(request, services){
  const url=new URL(request.url);
  if(url.pathname.startsWith('/__internal')){
    if(url.pathname==='/__internal/backend'){
      if(url.search||request.method!=='GET'||!await authorized(request.headers.get('Authorization'),services.storeToken))return error('NOT_FOUND','找不到此資源。',404);
      try{
        const status=await services.backendStatus();
        if(!status||typeof status.running!=='boolean'||typeof status.image_matches!=='boolean'
          ||!(status.boot_id===null||typeof status.boot_id==='string'&&status.boot_id.length===36&&/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(status.boot_id)))throw new Error();
        return protectedResponse(Response.json({running:status.running,boot_id:status.boot_id,image_matches:status.image_matches}),true);
      }catch{return error('SERVICE_UNAVAILABLE','無法取得展示後端執行狀態。',503);}
    }
    if(url.pathname!=='/__internal/cases'||url.search||request.method!=='POST'||!await authorized(request.headers.get('Authorization'),services.storeToken))return error('NOT_FOUND','找不到此資源。',404);
    try{
      const result=await services.storeCall(await commandBody(request));
      if(result.error){const [status,message]=errors[result.error.code]||[503,'案件暫存服務目前無法使用。'];return error(errors[result.error.code]?result.error.code:'CASE_STORE_UNAVAILABLE',message,status);}
      return protectedResponse(Response.json({result:result.result}),true);
    }catch(failure){const [status,message]=errors[failure?.code]||[503,'案件暫存服務目前無法使用。'];return error(errors[failure?.code]?failure.code:'CASE_STORE_UNAVAILABLE',message,status);}
  }
  if(/^\/(?:\.env(?:[./]|$)|\.local(?:\/|$)|\.git(?:\/|$)|backend(?:\/|$)|src(?:\/|$)|node_modules(?:\/|$)|cloudflare(?:\/|$))/.test(url.pathname))return error('NOT_FOUND','找不到此資源。',404);
  if(url.pathname.startsWith('/api/')){
    const origin=request.headers.get('Origin');
    if((origin&&origin!==url.origin)||request.headers.get('Sec-Fetch-Site')==='cross-site')return error('ORIGIN_NOT_ALLOWED','此來源無法存取案件服務。',403);
    if(url.searchParams.has('key'))return error('KEY_INVALID','請從展示首頁的連結載入金鑰。',422);
    try{return protectedResponse(await services.apiFetch(request),true);}catch{return error('PROVIDER_UNAVAILABLE','展示後端正在啟動或暫時無法使用，請稍後重試。',503);}
  }
  try{return protectedResponse(await services.assetFetch(request),url.searchParams.has('key'));}catch{return error('SERVICE_UNAVAILABLE','網站暫時無法載入，請稍後重試。',503);}
}
