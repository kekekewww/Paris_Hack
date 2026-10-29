import test from 'node:test';
import assert from 'node:assert/strict';
import {BackendContainerController} from '../cloudflare/backend-container.js';

const origin='https://claim-demo.example.workers.dev';
const token='synthetic-internal-token-for-controller-tests';
function fixture(overrides={}){
  const calls={start:[],idle:[],probe:[],forward:[]};
  let time=0;
  const container={
    running:false,images:{base:'registry.cloudflare.com/example/demo@sha256:synthetic'},
    start(options){calls.start.push(options);this.running=true;},
    async setInactivityTimeout(value){calls.idle.push(value);},
    getTcpPort(port){assert.equal(port,8000);return {fetch:async(value,options)=>{
      if(typeof value==='string'&&value==='http://container/api/v1/health'){
        calls.probe.push({value,options});return new Response('{"status":"ok"}');
      }
      calls.forward.push({value,options});return new Response('{"accepted":true}',{status:202});
    }};},
    ...overrides,
  };
  const controller=new BackendContainerController(container,{token,now:()=>time,delay:async ms=>{time+=ms;}});
  return {container,controller,calls};
}

test('cold startup uses a pinned image, fixed model and isolated storage configuration',async()=>{
  const {controller,calls}=fixture();
  const response=await controller.fetch(new Request(origin+'/api/v1/health',{headers:{Origin:'https://untrusted.example','X-Forwarded-Host':'untrusted.example'}}));
  assert.equal(response.status,202);assert.equal(calls.start.length,1);
  const options=calls.start[0];
  assert.equal(options.image,'registry.cloudflare.com/example/demo@sha256:synthetic');
  assert.equal(options.instance,'standard-1');assert.equal(options.enableInternet,true);
  assert.equal(options.env.CASE_STORE_URL,origin+'/__internal/cases');
  assert.equal(options.env.CASE_STORE_TOKEN,token);assert.equal(options.env.ALLOWED_ORIGINS,origin);
  assert.equal(options.env.RUNTIME_LLM_KEYS,'true');assert.equal(options.env.LLM_API_KEY,'');
  assert.equal(options.env.LLM_MODEL,'deepseek/deepseek-v4.1-flash-1017');
  assert.equal(options.env.LLM_TIMEOUT_SECONDS,'300');assert.equal(options.env.SESSION_COOKIE_SECURE,'true');
  assert.equal(options.env.LLM_BASE_URL,'https://openrouter.ai/api/v1');
  assert.equal(calls.probe.length,1);assert.deepEqual(calls.idle,[180000]);
});

test('concurrent initial requests share readiness without duplicating mutations',async()=>{
  const {controller,calls}=fixture();
  await Promise.all([1,2,3].map(n=>controller.fetch(new Request(origin+'/api/v1/cases',{method:'POST',body:JSON.stringify({n})}))));
  assert.equal(calls.start.length,1);assert.equal(calls.probe.length,1);assert.equal(calls.forward.length,3);
  const bodies=await Promise.all(calls.forward.map(call=>call.value.text()));
  assert.deepEqual(bodies.sort(),['{"n":1}','{"n":2}','{"n":3}']);
  assert.ok(calls.forward.every(call=>call.value.url===origin.replace('https:','http:')+'/api/v1/cases'));
});

test('constructor recovery restores idle policy for an already running container',async()=>{
  const {controller,calls}=fixture({running:true});
  await controller.resume();assert.deepEqual(calls.idle,[180000]);assert.equal(calls.start.length,0);
});

test('image changes do not destroy an active container and apply on the next cold startup',async()=>{
  const {controller,calls,container}=fixture({destroy(){assert.fail('must not interrupt active jobs');}});
  await controller.fetch(new Request(origin+'/api/v1/health'));
  container.images.base='registry.cloudflare.com/example/demo@sha256:next';
  await controller.fetch(new Request(origin+'/api/v1/health'));assert.equal(calls.start.length,1);
  container.running=false;
  await controller.fetch(new Request(origin+'/api/v1/health'));assert.equal(calls.start.length,2);
  assert.equal(calls.start[1].image,container.images.base);
});

test('readiness tolerates connection refusal and non-success statuses within one startup',async()=>{
  let probes=0;const {controller,calls}=fixture({getTcpPort(){return {fetch:async value=>{
    if(typeof value==='string'){
      probes++;if(probes===1)throw new Error('private allocation error');
      return new Response('',{status:probes===2?503:200});
    }
    return new Response('ready');
  }};}});
  assert.equal(await (await controller.fetch(new Request(origin+'/api/v1/health'))).text(),'ready');
  assert.equal(probes,3);assert.equal(calls.start.length,1);
});

test('readiness failure is bounded, sanitized and never forwards a mutation',async()=>{
  let attempts=0;const {controller,calls}=fixture({getTcpPort(){return {fetch:async()=>{attempts++;throw new Error(token);}};}});
  await assert.rejects(controller.fetch(new Request(origin+'/api/v1/cases',{method:'POST',body:'{}'})),error=>{
    assert.equal(error.message,'Cloud backend unavailable');assert.equal(error.cause,undefined);return true;
  });
  assert.ok(attempts>=2&&attempts<=61);assert.equal(calls.forward.length,0);
});

test('a failed readiness promise is cleared so an explicit later attempt can recover',async()=>{
  let ready=false;const {controller,container,calls}=fixture({getTcpPort(){return {fetch:async value=>{
    if(typeof value==='string')return new Response('',{status:ready?200:503});
    calls.forward.push(value);return new Response('recovered');
  }};}});
  await assert.rejects(controller.fetch(new Request(origin+'/api/v1/health')));
  ready=true;container.running=false;
  assert.equal(await (await controller.fetch(new Request(origin+'/api/v1/health'))).text(),'recovered');
  assert.equal(calls.start.length,2);assert.equal(calls.forward.length,1);
});

test('a forwarding transport failure is not retried or replayed',async()=>{
  let forwarded=0;const {controller}=fixture({getTcpPort(){return {fetch:async value=>{
    if(typeof value==='string')return new Response('ok');
    forwarded++;throw new Error(token);
  }};}});
  await assert.rejects(controller.fetch(new Request(origin+'/api/v1/cases',{method:'POST',body:'{}'})),error=>error.message==='Cloud backend unavailable'&&error.cause===undefined);
  assert.equal(forwarded,1);
});

for(const url of ['http://claim-demo.example.workers.dev/api/v1/health','https://localhost/api/v1/health','https://evil.example/api/v1/health','https://workers.dev/api/v1/health','https://claim-demo.example.workers.dev.evil.example/api/v1/health'])test('untrusted backend destination fails closed '+url,async()=>{
  const {controller,calls}=fixture();
  await assert.rejects(controller.fetch(new Request(url)));assert.equal(calls.start.length,0);assert.equal(calls.forward.length,0);
});

test('missing internal secret or image cannot start a container',async()=>{
  for(const key of ['token','image']){
    const {container,calls}=fixture();if(key==='image')container.images={};
    const controller=new BackendContainerController(container,{token:key==='token'?'':token});
    await assert.rejects(controller.fetch(new Request(origin+'/api/v1/health')));
    assert.equal(calls.start.length,0);
  }
});

test('hanging readiness fetch is aborted and obeys the bounded startup deadline',async()=>{
  let signal;
  const {container}=fixture({getTcpPort(){return {fetch:async(_value,options)=>{signal=options.signal;return new Promise(()=>{});}};}});
  const controller=new BackendContainerController(container,{token,timeoutMs:20});
  const before=Date.now();
  await assert.rejects(controller.fetch(new Request(origin+'/api/v1/health')));
  assert.ok(Date.now()-before<1000);assert.equal(signal.aborted,true);
});

test('a stalled platform idle-policy call cannot bypass the startup deadline',async()=>{
  const {container,calls}=fixture({setInactivityTimeout(){return new Promise(()=>{});}});
  const controller=new BackendContainerController(container,{token,timeoutMs:20});
  const result=await Promise.race([
    controller.fetch(new Request(origin+'/api/v1/health')).then(()=> 'forwarded',()=> 'bounded'),
    new Promise(resolve=>setTimeout(()=>resolve('deadline-bypassed'),200)),
  ]);
  assert.equal(result,'bounded');assert.equal(calls.forward.length,0);
});

const bootPattern=/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const syntheticBoot='3e3a19d1-ef5b-4db4-a6ad-e5209538cd90';

test('cold startup assigns an opaque boot label that changes after a real stop',async()=>{
  const {controller,container,calls}=fixture();
  container.inspect=async()=>({image:calls.start.at(-1)?.image,labels:calls.start.at(-1)?.labels});
  await controller.fetch(new Request(origin+'/api/v1/health'));
  const first=await controller.status();assert.match(first.boot_id,bootPattern);
  assert.deepEqual(calls.start[0].labels,{boot:first.boot_id});
  container.running=false;
  assert.deepEqual(await controller.status(),{running:false,boot_id:null,image_matches:false});
  await controller.fetch(new Request(origin+'/api/v1/health'));
  const second=await controller.status();assert.match(second.boot_id,bootPattern);
  assert.notEqual(second.boot_id,first.boot_id);assert.equal(second.image_matches,true);
});

test('stopped status cannot inspect, start, destroy or reset idle policy',async()=>{
  const {controller,calls}=fixture({inspect(){assert.fail('stopped inspection');},destroy(){assert.fail('destruction');}});
  assert.deepEqual(await controller.status(),{running:false,boot_id:null,image_matches:false});
  assert.deepEqual(calls,{start:[],idle:[],probe:[],forward:[]});
});

test('running status returns only validated boot and image equality without exposing inspection contents',async()=>{
  const {controller,calls,container}=fixture({running:true,async inspect(){return {
    image:this.images.base,labels:{boot:syntheticBoot,secret:token},env:{CASE_STORE_TOKEN:token},private:token,
  };}});
  assert.deepEqual(await controller.status(),{running:true,boot_id:syntheticBoot,image_matches:true});
  assert.deepEqual(calls,{start:[],idle:[],probe:[],forward:[]});
  container.images.base+='-updated';
  container.inspect=async()=>({image:'old-image',labels:{boot:syntheticBoot}});
  assert.deepEqual(await controller.status(),{running:true,boot_id:syntheticBoot,image_matches:false});
});

for(const labels of [undefined,null,{},[],{boot:token},{boot:syntheticBoot+'\n'},{boot:42}])test('status omits missing or malformed boot labels '+JSON.stringify(labels),async()=>{
  const {controller,container}=fixture({running:true,async inspect(){return {image:this.images.base,labels};}});
  assert.deepEqual(await controller.status(),{running:true,boot_id:null,image_matches:true});
  assert.equal(container.running,true);
});

test('missing container and missing or failed inspection fail closed without private details',async()=>{
  const variants=[undefined,{running:true},{running:true,images:{base:'x'},inspect:async()=>null},
    {running:true,images:{base:'x'},inspect:async()=>{throw new Error(token);}},
    {running:'yes',inspect:async()=>({image:'x'})},
  ];
  for(const container of variants){
    const controller=new BackendContainerController(container,{token});
    await assert.rejects(controller.status(),error=>error.message==='Cloud backend unavailable'&&error.cause===undefined);
  }
});
