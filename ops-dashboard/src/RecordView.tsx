/** Read-only structured records: never infer a successful or finalized state. */
const names:Record<string,string>={availability:'가능 시간',unavailable:'불가 시간',roles:'가능 역할',requiredRoles:'필수 역할',roleUnavailable:'불가 역할',rolePreferences:'선호 역할',timePreferences:'시간 선호',companionRequirements:'동행 조건',companionId:'동행 참여자',preference:'선호',note:'메모',date:'날짜',start:'시작',end:'종료',interval:'시간',memberId:'참여자',participantId:'참여자',participantName:'담당자',role:'역할',name:'이름',version:'조건 버전',conditions:'확정 조건',createdAt:'기록 시각',round:'배정 회차',solverStatus:'계산 결과',plan:'배정 결과',assignments:'담당표',consents:'동의 현황',status:'상태',finalizedAt:'최종 확정 시각',cycle:'모임 회차',snapshot:'보존 기록',meeting:'모임',lifecycle:'종료 상태',reason:'사유',required:'필수 여부',mode:'구분',kind:'구분',weight:'선호 가중치',message:'안내',ambiguitiesResolved:'모호한 조건 확인',aiDraftId:'AI 초안 ID'};
const values:Record<string,string>={balanced:'균형',early:'이른 시간',late:'늦은 시간',preferred:'선호',avoid:'회피',required:'필수',pending:'동의 대기',agreed:'동의',review:'검토 요청',withdrawn:'철회',OPTIMAL:'최적성 확인',FEASIBLE:'배정 가능 · 최적성 미확인',INFEASIBLE:'배정 불가',UNKNOWN:'결과 미확정',ACTIVE:'진행 중',CLOSED_CONFIRMED:'확정 후 종료',EXPIRED:'미확정 만료',CANCELLED:'취소'};
export const clock=(n:number)=>`${String(Math.floor(n/60)).padStart(2,'0')}:${String(n%60).padStart(2,'0')}`;
export function RecordView({value,people={},field=''}:{value:unknown;people?:Record<string,string>;field?:string}){
 if(value===null||value===undefined)return <span className="muted">미기록</span>;
 if(typeof value==='boolean')return <span>{value?'확인':'아니요'}</span>;
 if(typeof value==='number')return <span>{['start','end'].includes(field)?clock(value):value}</span>;
 if(typeof value==='string')return <span>{people[value]||values[value]||value||'없음'}</span>;
 if(Array.isArray(value))return value.length?<ul className="record-list">{value.map((v,i)=><li key={i}><RecordView value={v} people={people}/></li>)}</ul>:<span className="muted">기록 없음</span>;
 return <dl className="record-fields">{Object.entries(value as Record<string,unknown>).map(([key,v])=><div key={key}><dt>{names[key]||key}</dt><dd><RecordView value={v} field={key} people={people}/></dd></div>)}</dl>;
}
