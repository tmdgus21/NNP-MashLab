export type User={id?:string;email:string;role:'SUPER_ADMIN'|'OPERATOR'|'VIEWER';csrf:string;expiresAt:string};
export type Room={id:string;title:string;code:string;host:string;participants:number;scheduledDate:string;round:number;cycle:number;progress:string;lifecycle:string;management:string;revision:number;closesAt:string};
export type Person={id:string;name:string;submitted:boolean;consent:string;consentRound:number;conditions:{availability:{date:string;start:number;end:number}[];roles:string[];[key:string]:unknown}};
export type Audit={id:string;actor:string;action:string;target:string;reason:string;createdAt:string;data:unknown};
export type Detail=Room & {meeting:{participants:Person[];history:string[]};submissions:unknown[];proposals:unknown[];cycles:unknown[];actions:Audit[]};
export type Account={id:string;email:string;role:User['role'];approved:boolean;frozen:boolean;failures:number;revision:number};
export async function api<T>(path:string,body?:unknown,csrf?:string,key?:string):Promise<T>{
 const abort=new AbortController(); const timer=setTimeout(()=>abort.abort(),20000);
 try {const response=await fetch('/admin-api'+path,{method:body===undefined?'GET':'POST',credentials:'same-origin',cache:'no-store',signal:abort.signal,headers:{'Content-Type':'application/json',...(csrf?{'X-CSRF-Token':csrf}:{}),...(key?{'Idempotency-Key':key}:{})},...(body===undefined?{}:{body:JSON.stringify(body)})});
 const data=await response.json().catch(()=>{throw new Error('서버에 연결할 수 없습니다. 연결 상태를 확인하고 다시 시도해 주세요.')}); if(!response.ok){if(response.status===401 && !path.startsWith('/auth/'))window.dispatchEvent(new Event('admin-session-expired')); throw new Error(typeof data.detail==='string'?data.detail:`요청 실패 (${response.status})`);} return data;
 }catch(error){if(error instanceof DOMException && error.name==='AbortError')throw new Error('응답 시간이 초과됐습니다. 저장 여부를 조회한 뒤 재시도해 주세요.');if(error instanceof TypeError)throw new Error('네트워크 연결을 확인해 주세요.');throw error;}finally{clearTimeout(timer);}
}
export const labels:Record<string,string>={ACTIVE:'진행 중',CLOSED_CONFIRMED:'확정 후 종료',EXPIRED:'미확정 만료',CANCELLED:'취소',ENABLED:'활성',DISABLED:'비활성',collecting:'조건 수집',reviewing:'동의 진행',finalized:'최종 확정',deleted:'삭제됨',SUPER_ADMIN:'최고 관리자',OPERATOR:'모임 관리자',VIEWER:'조회 전용',pending:'대기',agreed:'동의',review:'검토 요청'};
