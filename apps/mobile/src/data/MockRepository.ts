import {
  Conditions,
  Consent,
  CreateMeeting,
  Meeting,
  ParseResult,
  Preview,
  Session,
  emptyConditions,
  meetingSchema,
} from '../domain/model';
import {
  canFinalize,
  requireRevision,
  validateConditions,
} from '../domain/rules';
import { normalizeIntervals, validDate } from '../domain/time';
import { Repository, Scenario, Storage } from './RepositoryPort';
import { fixture } from './fixtures';
import { mockSolve } from './mockSolver';

const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value));
const KEY = 'conditionalok.mock.v1';
export class MockRepository implements Repository {
  readonly mode = 'mock' as const;
  private meetings: Record<string, Meeting> = { demo: fixture('feasible') };
  private session: { id: string; actorId: string } | null = null;
  private failNext = false;
  constructor(private storage?: Storage, private latency = 300) {}
  private async wait() {
    if (this.latency) {
      await new Promise<void>(resolve => setTimeout(resolve, this.latency));
    }
    if (this.failNext) {
      this.failNext = false;
      throw new Error('연결이 끊겼어요. 다시 시도해 주세요. (Mock 오류)');
    }
  }
  private meeting(id: string) {
    const m = this.meetings[id];
    if (!m) {
      throw new Error('모임을 찾을 수 없습니다.');
    }
    return m;
  }
  private member(m: Meeting, actor: string) {
    const p = m.participants.find(v => v.id === actor);
    if (!p) {
      throw new Error('참가자만 사용할 수 있습니다.');
    }
    return p;
  }
  private async save() {
    await this.storage?.setItem(
      KEY,
      JSON.stringify({ meetings: this.meetings, session: this.session }),
    );
  }
  async restore(): Promise<Session | null> {
    const saved = await this.storage?.getItem(KEY);
    if (saved) {
      const data = JSON.parse(saved);
      Object.values(data.meetings).forEach(m => meetingSchema.parse(m));
      this.meetings = data.meetings;
      this.session = data.session;
    }
    if (!this.session) {
      return null;
    }
    const m = this.meeting(this.session.id);
    this.member(m, this.session.actorId);
    return { meeting: copy(m), actorId: this.session.actorId };
  }
  async create(input: CreateMeeting): Promise<Session> {
    await this.wait();
    if (
      !input.title.trim() ||
      !input.name.trim() ||
      !input.dates.length ||
      input.dates.length > 7 ||
      ![input.duration, input.windowStart, input.windowEnd].every(Number.isFinite) ||
      input.dates.some(d => !validDate(d)) ||
      !input.roles.length ||
      input.roles.length > 6 ||
      input.roles.some(r => !r.trim()) ||
      input.duration < 30 ||
      input.duration % 30 ||
      input.windowStart < 0 ||
      input.windowEnd > 1440 ||
      input.windowStart % 30 ||
      input.windowEnd % 30 ||
      input.windowStart + input.duration > input.windowEnd
    ) {
      throw new Error('이름·날짜·역할·30분 단위 시간 범위를 확인해 주세요.');
    }
    const id = `m${Date.now()}`;
    const actorId = `${id}-host`;
    const m: Meeting = {
      ...fixture('empty'),
      id,
      code: `OK${Date.now().toString(36).toUpperCase()}`,
      title: input.title.trim(),
      hostId: actorId,
      dates: [...new Set(input.dates)],
      roles: [...new Set(input.roles)],
      duration: input.duration,
      windowStart: input.windowStart,
      windowEnd: input.windowEnd,
      participants: [
        {
          id: actorId,
          name: input.name.trim(),
          conditions: emptyConditions(),
          consent: 'pending',
          consentRound: 1,
          reviewNote: '',
        },
      ],
    };
    this.meetings[id] = m;
    this.session = { id, actorId };
    await this.save();
    return { meeting: copy(m), actorId };
  }
  async join(code: string, name: string): Promise<Session> {
    await this.wait();
    const m = Object.values(this.meetings).find(
      v => v.code === code.trim().toUpperCase(),
    );
    if (!m) {
      throw new Error('초대 코드를 확인해 주세요.');
    }
    if (!name.trim()) {
      throw new Error('참가자 이름을 입력해 주세요.');
    }
    if (m.status === 'finalized') {
      throw new Error('이미 확정된 모임입니다.');
    }
    const actorId = `p${Date.now()}`;
    m.participants.push({
      id: actorId,
      name: name.trim(),
      conditions: emptyConditions(),
      consent: 'pending',
      consentRound: m.round,
      reviewNote: '',
    });
    this.newRound(m, `${name.trim()}님 참가`);
    this.session = { id: m.id, actorId };
    await this.save();
    return { meeting: copy(m), actorId };
  }
  async get(id: string) {
    await this.wait();
    return copy(this.meeting(id));
  }
  private newRound(m: Meeting, reason: string) {
    if (m.plan.status !== 'idle' || m.status === 'reviewing') {
      m.previousPlan = copy(m.plan);
      m.round++;
    }
    m.revision++;
    m.status = 'collecting';
    m.plan = { round: m.round, status: 'idle', assignments: [], notices: [] };
    m.participants.forEach(p => {
      p.consent = 'pending';
      p.consentRound = m.round;
      p.reviewNote = '';
    });
    m.history.push(`${reason} · ${m.round}차 조율, 전원 동의 대기`);
  }
  async preview(
    id: string,
    actor: string,
    c: Conditions,
    revision: number,
  ): Promise<Preview> {
    await this.wait();
    const m = this.meeting(id);
    requireRevision(m, revision);
    const p = this.member(m, actor);
    validateConditions(m, actor, c);
    const next = copy(m);
    next.participants.find(v => v.id === actor)!.conditions = {
      ...c,
      availability: normalizeIntervals(c.availability),
    };
    this.newRound(next, `${p.name}님 조건 변경`);
    return {
      revision,
      before: copy(m.plan),
      after: mockSolve(next),
      changes: [
        `가능 시간 ${p.conditions.availability.length}개 → ${
          normalizeIntervals(c.availability).length
        }개 구간`,
        `역할: ${c.roles.join(', ') || '미선택'}`,
        `적용 시 ${next.round}차 조율 · ${m.participants.length}명 재동의 필요`,
      ],
    };
  }
  async updateConditions(
    id: string,
    actor: string,
    c: Conditions,
    revision: number,
  ) {
    await this.wait();
    const m = this.meeting(id);
    requireRevision(m, revision);
    const p = this.member(m, actor);
    validateConditions(m, actor, c);
    const normalized = {
      ...c,
      availability: normalizeIntervals(c.availability),
    };
    if (JSON.stringify(p.conditions) === JSON.stringify(normalized)) {
      return copy(m);
    }
    p.conditions = copy(normalized);
    this.newRound(m, `${p.name}님 조건 변경`);
    await this.save();
    return copy(m);
  }
  async calculate(id: string, actor: string, revision: number) {
    await this.wait();
    const m = this.meeting(id);
    requireRevision(m, revision);
    this.member(m, actor);
    if (m.plan.status !== 'idle') {
      return copy(m);
    }
    m.plan = mockSolve(m);
    m.status = 'reviewing';
    m.revision++;
    m.history.push(`${m.round}차 계산 완료`);
    await this.save();
    return copy(m);
  }
  async consent(
    id: string,
    actor: string,
    consent: Consent,
    note: string,
    round: number,
    revision: number,
  ) {
    await this.wait();
    const m = this.meeting(id);
    requireRevision(m, revision);
    if (
      round !== m.round ||
      m.plan.round !== round ||
      m.plan.status !== 'feasible'
    ) {
      throw new Error('현재 회차의 배정 가능한 담당표에만 응답할 수 있습니다.');
    }
    if (consent === 'review' && !note.trim()) {
      throw new Error('검토 요청 사유를 입력해 주세요.');
    }
    const p = this.member(m, actor);
    p.consent = consent;
    p.consentRound = round;
    p.reviewNote = consent === 'review' ? note.trim() : '';
    m.revision++;
    await this.save();
    return copy(m);
  }
  async finalize(id: string, actor: string, revision: number) {
    await this.wait();
    const m = this.meeting(id);
    requireRevision(m, revision);
    if (!canFinalize(m, actor)) {
      throw new Error('해당 회차 전원 동의 후 방장만 확정할 수 있습니다.');
    }
    m.status = 'finalized';
    m.revision++;
    m.plan.assignments.forEach(a => {
      a.status = 'confirmed';
    });
    m.history.push(`${m.round}차 최종 확정 · 완료`);
    await this.save();
    return copy(m);
  }
  async parseConditions(text: string): Promise<ParseResult> {
    await this.wait();
    if (!text.trim()) {
      throw new Error('조건을 입력해 주세요.');
    }
    return {
      source: 'mock',
      draft: {
        note: text,
        ...(/오전|일찍/.test(text)
          ? { preference: 'early' as const }
          : /오후|늦게/.test(text)
          ? { preference: 'late' as const }
          : {}),
      },
      questions: [
        '데모 해석입니다. 시간·역할·동반조건은 아래 구조화 입력에서 직접 확인해 주세요.',
      ],
    };
  }
  async scenario(scenario: Scenario): Promise<Session> {
    await this.wait();
    const m = fixture(scenario);
    this.meetings.demo = m;
    this.session = { id: 'demo', actorId: 'p1' };
    await this.save();
    return { meeting: copy(m), actorId: 'p1' };
  }
  async switchActor(id: string, actorId: string) {
    this.member(this.meeting(id), actorId);
    this.session = { id, actorId };
    await this.save();
  }
  simulateError() {
    this.failNext = true;
  }
}
