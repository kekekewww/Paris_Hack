import {DurableObject} from 'cloudflare:workers';
import {BackendContainerController} from './backend-container.js';
import {executeCaseCommand, CaseStoreError, CASE_TTL_SECONDS} from './case-store.js';
import {routeRequest} from './gateway.js';

export class ClaimStore extends DurableObject {
  constructor(ctx, env){
    super(ctx,env);
    ctx.blockConcurrencyWhile(async()=>{
      executeCaseCommand(ctx.storage,{op:'cleanup'});
      await this.scheduleCleanup();
    });
  }
  async scheduleCleanup(){
    const row=this.ctx.storage.sql.exec('SELECT MIN(created_at) AS earliest FROM cases').toArray()[0];
    if(row?.earliest==null){await this.ctx.storage.deleteAlarm();return;}
    await this.ctx.storage.setAlarm(Math.max(Date.now()+1000,Math.ceil((row.earliest+CASE_TTL_SECONDS)*1000)));
  }
  async command(input){
    try{
      const result=executeCaseCommand(this.ctx.storage,input);
      await this.scheduleCleanup();
      return {result};
    }catch(failure){
      if(failure instanceof CaseStoreError)return {error:{code:failure.code,message:failure.message,status:failure.status}};
      return {error:{code:'CASE_STORE_UNAVAILABLE',message:'案件暫存服務目前無法使用。',status:503}};
    }
  }
  async alarm(){
    executeCaseCommand(this.ctx.storage,{op:'cleanup'});
    await this.scheduleCleanup();
  }
}

export class ClaimBackend extends DurableObject {
  constructor(ctx,env){
    super(ctx,env);
    this.backend=new BackendContainerController(ctx.container,{token:env.CASE_STORE_TOKEN});
    ctx.blockConcurrencyWhile(()=>this.backend.resume());
  }
  async fetch(request){return this.backend.fetch(request);}
  async runtimeStatus(){return this.backend.status();}
}

export default {
  async fetch(request,env){
    return routeRequest(request,{
      storeToken:env.CASE_STORE_TOKEN,
      assetFetch:value=>env.ASSETS.fetch(value),
      apiFetch:value=>env.CLAIM_BACKEND.getByName('claim-demo-v1').fetch(value),
      storeCall:command=>env.CASE_STORAGE.getByName('claim-cases-v1').command(command),
      backendStatus:()=>env.CLAIM_BACKEND.getByName('claim-demo-v1').runtimeStatus(),
    });
  },
};
