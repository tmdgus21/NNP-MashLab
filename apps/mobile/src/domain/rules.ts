import { Conditions, Meeting, conditionsSchema } from './model';
import { validDate } from './time';

export function validateConditions(
  m: Meeting,
  actor: string,
  input: Conditions,
): Conditions {
  const c = conditionsSchema.parse(input);
  if (c.roles.some(r => !m.roles.includes(r))) {
    throw new Error('모임에 없는 역할입니다.');
  }
  if (
    c.availability.some(i => !validDate(i.date) || !m.dates.includes(i.date))
  ) {
    throw new Error('모임 후보 날짜만 선택해 주세요.');
  }
  if (
    c.companionId &&
    (c.companionId === actor ||
      !m.participants.some(p => p.id === c.companionId))
  ) {
    throw new Error('동반 참가자를 확인해 주세요.');
  }
  return c;
}
export function canFinalize(m: Meeting, actorId: string) {
  return (
    actorId === m.hostId &&
    m.status !== 'finalized' &&
    m.plan.status === 'feasible' &&
    m.plan.round === m.round &&
    m.plan.assignments.length === m.roles.length &&
    m.participants.length > 0 &&
    m.participants.every(
      p => p.consent === 'agreed' && p.consentRound === m.round,
    )
  );
}
export function requireRevision(m: Meeting, revision: number) {
  if (m.revision !== revision) {
    throw new Error('다른 변경이 있습니다. 새로고침 후 다시 확인해 주세요.');
  }
  if (m.status === 'finalized') {
    throw new Error('확정된 모임은 수정할 수 없습니다.');
  }
}
