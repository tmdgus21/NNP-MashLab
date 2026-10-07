import { MockRepository } from '../src/data/MockRepository';
import { fixture } from '../src/data/fixtures';
import { mockSolve } from '../src/data/mockSolver';
import { canFinalize } from '../src/domain/rules';
import { covers } from '../src/domain/time';
import { emptyConditions, meetingSchema } from '../src/domain/model';
const repo = () => new MockRepository(undefined, 0);
test.each([
  'feasible',
  'conflict',
  'infeasible',
  'changed',
  'finalized',
  'empty',
] as const)('fixture %s follows JSON contract', name => {
  expect(() => meetingSchema.parse(fixture(name))).not.toThrow();
});
test('solver never assigns an unavailable, unqualified or duplicate participant', () => {
  const m = fixture('feasible');
  const plan = mockSolve(m);
  expect(plan.status).toBe('feasible');
  expect(plan.assignments).toHaveLength(m.roles.length);
  expect(new Set(plan.assignments.map(a => a.participantId)).size).toBe(
    m.roles.length,
  );
  plan.assignments.forEach(a => {
    const p = m.participants.find(v => v.id === a.participantId)!;
    expect(p.conditions.roles).toContain(a.role);
    expect(covers(p.conditions.availability, a.interval)).toBe(true);
  });
  expect(mockSolve(fixture('conflict')).status).toBe('infeasible');
  expect(mockSolve(fixture('infeasible')).assignments).toEqual([]);
});
test('companion availability is a hard constraint', () => {
  const m = fixture('feasible');
  m.participants = m.participants.slice(0, 3);
  m.participants[0].conditions.companionId = 'p2';
  m.participants[1].conditions.availability = [];
  expect(mockSolve(m).status).toBe('infeasible');
});
test('preview is read-only; changes invalidate consent; stale revision is rejected', async () => {
  const r = repo();
  let { meeting: m } = await r.scenario('feasible');
  m = await r.consent(m.id, 'p1', 'agreed', '', m.round, m.revision);
  const conditions = {
    ...m.participants[0].conditions,
    preference: 'late' as const,
  };
  const preview = await r.preview(m.id, 'p1', conditions, m.revision);
  expect((await r.get(m.id)).round).toBe(1);
  expect((await r.get(m.id)).participants[0].consent).toBe('agreed');
  m = await r.updateConditions(m.id, 'p1', conditions, preview.revision);
  expect(m.round).toBe(2);
  expect(m.previousPlan?.round).toBe(1);
  expect(m.plan.status).toBe('idle');
  expect(m.participants.every(p => p.consent === 'pending')).toBe(true);
  await expect(
    r.updateConditions(m.id, 'p1', conditions, preview.revision),
  ).rejects.toThrow('다른 변경');
  m = await r.calculate(m.id, 'p1', m.revision);
  await expect(
    r.consent(m.id, 'p1', 'agreed', '', 1, m.revision),
  ).rejects.toThrow('현재 회차');
});
test('full agreement, withdrawal, review, host authorization and immutable finalization', async () => {
  const r = repo();
  let { meeting: m } = await r.scenario('feasible');
  await expect(r.finalize(m.id, 'p1', m.revision)).rejects.toThrow();
  for (const p of m.participants) {
    m = await r.consent(m.id, p.id, 'agreed', '', m.round, m.revision);
  }
  expect(canFinalize(m, 'p1')).toBe(true);
  await expect(r.finalize(m.id, 'p2', m.revision)).rejects.toThrow();
  m = await r.consent(m.id, 'p2', 'pending', '', m.round, m.revision);
  expect(canFinalize(m, 'p1')).toBe(false);
  await expect(
    r.consent(m.id, 'p2', 'review', '', m.round, m.revision),
  ).rejects.toThrow('사유');
  m = await r.consent(
    m.id,
    'p2',
    'review',
    '시간 확인 필요',
    m.round,
    m.revision,
  );
  expect(m.participants[1].reviewNote).toBe('시간 확인 필요');
  m = await r.consent(m.id, 'p2', 'agreed', '', m.round, m.revision);
  m = await r.finalize(m.id, 'p1', m.revision);
  expect(m.status).toBe('finalized');
  expect(m.plan.assignments.every(a => a.status === 'confirmed')).toBe(true);
  await expect(
    r.updateConditions(m.id, 'p1', emptyConditions(), m.revision),
  ).rejects.toThrow('확정');
});
test('create, join, storage restoration and simulated network error', async () => {
  const items: Record<string, string> = {};
  const storage = {
    getItem: async (k: string) => items[k] ?? null,
    setItem: async (k: string, v: string) => {
      items[k] = v;
    },
  };
  const r = new MockRepository(storage, 0);
  const s = await r.create({
    name: '방장',
    title: '새 모임',
    dates: ['2026-10-17'],
    roles: ['진행'],
    duration: 60,
    windowStart: 540,
    windowEnd: 1080,
  });
  const joined = await r.join(s.meeting.code, '참가자');
  expect(joined.meeting.participants).toHaveLength(2);
  expect((await new MockRepository(storage, 0).restore())?.actorId).toBe(
    joined.actorId,
  );
  await expect(r.join('INVALID', '가')).rejects.toThrow('초대 코드');
  r.simulateError();
  await expect(r.get(s.meeting.id)).rejects.toThrow('연결');
  expect((await r.get(s.meeting.id)).id).toBe(s.meeting.id);
});
