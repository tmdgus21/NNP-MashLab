import { Meeting, emptyConditions } from '../domain/model';
import { Scenario } from './RepositoryPort';
import { mockSolve } from './mockSolver';

export function fixture(scenario: Scenario): Meeting {
  const dates = ['2026-10-17', '2026-10-18'];
  const roles = ['진행', '기록', '촬영'];
  const m: Meeting = {
    id: 'demo',
    code: 'OK2026',
    title: '주말 프로젝트 모임',
    hostId: 'p1',
    timezone: 'Asia/Seoul',
    dates,
    roles,
    duration: 60,
    windowStart: 540,
    windowEnd: 1080,
    revision: 1,
    round: 1,
    status: 'collecting',
    previousPlan: null,
    history: ['1차 조율을 시작했어요'],
    plan: { round: 1, status: 'idle', assignments: [], notices: [] },
    participants: [
      ['p1', '민지', ['진행', '기록'], 600, 900],
      ['p2', '준호', ['촬영', '진행'], 660, 960],
      ['p3', '서연', ['기록', '촬영'], 600, 840],
      ['p4', '도윤', ['진행', '기록'], 720, 1020],
    ].map(([id, name, availableRoles, start, end]) => ({
      id: id as string,
      name: name as string,
      conditions: {
        ...emptyConditions(),
        roles: availableRoles as string[],
        availability: dates.map(date => ({
          date,
          start: start as number,
          end: end as number,
        })),
      },
      consent: 'pending',
      consentRound: 1,
      reviewNote: '',
    })),
  };
  if (scenario === 'empty') {
    m.participants = [m.participants[0]];
    m.participants[0].conditions = emptyConditions();
    return m;
  }
  if (scenario === 'conflict') {
    m.participants.forEach((p, i) => {
      p.conditions.availability = [
        { date: dates[0], start: 540 + i * 120, end: 600 + i * 120 },
      ];
    });
  }
  if (scenario === 'infeasible') {
    m.participants.forEach(p => {
      p.conditions.roles = p.conditions.roles.filter(r => r !== '촬영');
    });
  }
  m.plan = mockSolve(m);
  m.status = 'reviewing';
  if (scenario === 'changed') {
    m.previousPlan = m.plan;
    m.round = 2;
    m.revision = 2;
    m.participants[0].conditions.availability = dates.map(date => ({
      date,
      start: 780,
      end: 960,
    }));
    m.participants.forEach(p => {
      p.consentRound = 2;
    });
    m.plan = mockSolve(m);
    m.history.push('민지님의 조건 변경 · 2차 재동의 필요');
  }
  if (scenario === 'finalized') {
    m.participants.forEach(p => {
      p.consent = 'agreed';
    });
    m.status = 'finalized';
    m.plan.assignments.forEach(a => {
      a.status = 'confirmed';
    });
    m.history.push('방장이 1차 담당표를 최종 확정했어요');
  }
  return m;
}
