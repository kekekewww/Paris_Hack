const IDLE_MS=180000;
const STARTUP_MS=30000;
const BOOT_ID=/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const unavailable=()=>new Error('Cloud backend unavailable');

function workerOrigin(value){
  const url=new URL(value);
  const host=url.hostname;
  if(url.protocol!=='https:'||url.username||url.password||(url.port&&url.port!=='443')
    ||!host.endsWith('.workers.dev')||host.split('.').length<3)throw unavailable();
  return url.origin;
}

/** Native Durable Object Container API lifecycle, without mutation retries.
 * The Worker supplies its routed request URL and private storage token. Model
 * credentials remain on their individual requests and never enter startup env.
 */
export class BackendContainerController {
  #container;
  #token;
  #now;
  #delay;
  #timeout;
  #startup=null;
  #ready=false;

  constructor(container,{token,now=Date.now,delay=ms=>new Promise(resolve=>setTimeout(resolve,ms)),timeoutMs=STARTUP_MS}={}){
    this.#container=container;
    this.#token=token;
    this.#now=now;
    this.#delay=delay;
    this.#timeout=timeoutMs;
  }

  async resume(){
    try{
      if(this.#container?.running)await this.#container.setInactivityTimeout(IDLE_MS);
    }catch{throw unavailable();}
  }

  /** Inspection only: no allocation, port traffic or explicit idle renewal.
   * Calling this RPC still counts as Durable Object activity on the platform.
   */
  async status(){
    try{
      const container=this.#container;
      if(!container||typeof container.running!=='boolean')throw unavailable();
      if(!container.running)return {running:false,boot_id:null,image_matches:false};
      const expected=container.images?.base;
      if(typeof expected!=='string'||!expected||typeof container.inspect!=='function')throw unavailable();
      const info=await container.inspect();
      if(!info||typeof info.image!=='string')throw unavailable();
      const boot=info.labels?.boot;
      return {running:true,boot_id:typeof boot==='string'&&boot.length===36&&BOOT_ID.test(boot)?boot:null,image_matches:info.image===expected};
    }catch{throw unavailable();}
  }

  async #probe(port,remaining){
    const abort=new AbortController();
    let timer;
    try{
      return await Promise.race([
        port.fetch('http://container/api/v1/health',{signal:abort.signal}),
        new Promise((_,reject)=>{timer=setTimeout(()=>{abort.abort();reject(unavailable());},Math.min(2000,remaining));}),
      ]);
    }finally{clearTimeout(timer);}
  }

  async #start(origin){
    const container=this.#container;
    const deadline=this.#now()+this.#timeout;
    if(!container.running){
      const image=container.images?.base;
      if(typeof image!=='string'||!image)throw unavailable();
      container.start({
        image,instance:'standard-1',enableInternet:true,labels:{boot:crypto.randomUUID()},
        env:{
          RUNTIME_LLM_KEYS:'true',LLM_PROVIDER:'openai_compatible',LLM_API_KEY:'',
          LLM_MODEL:'deepseek/deepseek-v4.1-flash-1017',
          LLM_BASE_URL:'https://openrouter.ai/api/v1',LLM_TIMEOUT_SECONDS:'300',
          ALLOWED_ORIGINS:origin,SESSION_COOKIE_SECURE:'true',RATE_LIMIT_REQUESTS:'240',
          CASE_STORE_URL:origin+'/__internal/cases',CASE_STORE_TOKEN:this.#token,
        },
      });
    }
    let idleTimer;
    try{
      await Promise.race([
        container.setInactivityTimeout(IDLE_MS),
        new Promise((_,reject)=>{idleTimer=setTimeout(()=>reject(unavailable()),Math.max(1,deadline-this.#now()));}),
      ]);
    }finally{clearTimeout(idleTimer);}
    const port=container.getTcpPort(8000);
    while(this.#now()<deadline){
      try{
        const response=await this.#probe(port,deadline-this.#now());
        // Readiness uses only a fixed, side-effect-free health endpoint. Its
        // response is never logged or included in a public startup error.
        void response.body?.cancel().catch(()=>{});
        if(response.ok){this.#ready=true;return;}
      }catch{}
      const remaining=deadline-this.#now();
      if(remaining>0)await this.#delay(Math.min(500,remaining));
    }
    throw unavailable();
  }

  async #ensureReady(origin){
    if(this.#container.running&&this.#ready)return;
    if(!this.#startup){
      this.#ready=false;
      this.#startup=this.#start(origin).finally(()=>{this.#startup=null;});
    }
    await this.#startup;
  }

  async fetch(request){
    try{
      const origin=workerOrigin(request.url);
      if(!this.#container||typeof this.#token!=='string'||this.#token.length<24||this.#token.length>512
        ||!/^[!-~]+$/.test(this.#token)||typeof this.#now!=='function'||typeof this.#delay!=='function'
        ||!Number.isFinite(this.#timeout)||this.#timeout<=0||this.#timeout>STARTUP_MS)throw unavailable();
      await this.#ensureReady(origin);
      const target=new URL(request.url);target.protocol='http:';
      // Forward exactly once. A transport error could follow a committed
      // mutation or a paid model request, so the caller owns any later retry.
      return await this.#container.getTcpPort(8000).fetch(new Request(target,request));
    }catch{throw unavailable();}
  }
}
