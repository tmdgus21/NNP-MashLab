import { Assignment, Meeting, Plan } from '../domain/model';
import { covers } from '../domain/time';

/** Small exhaustive fixture solver; production optimization belongs to the server. */
export function mockSolve(m: Meeting): Plan {
  let best: { assignments: Assignment[]; score: number } | undefined;
  for (const date of m.dates) {
    for (
      let start = m.windowStart;
      start + m.duration <= m.windowEnd;
      start += 30
    ) {
      const interval = { date, start, end: start + m.duration };
      const assign = (index: number, rows: Assignment[], score: number) => {
        if (index === m.roles.length) {
          if (!best || score > best.score) {
            best = { assignments: rows, score };
          }
          return;
        }
        const role = m.roles[index];
        for (const p of m.participants) {
          const c = p.conditions;
          if (
            !c.roles.includes(role) ||
            !covers(c.availability, interval) ||
            rows.some(a => a.participantId === p.id)
          ) {
            continue;
          }
          if (
            c.companionId &&
            !covers(
              m.participants.find(person => person.id === c.companionId)
                ?.conditions.availability ?? [],
              interval,
            )
          ) {
            continue;
          }
          const preference =
            c.preference === 'early'
              ? 1440 - start
              : c.preference === 'late'
              ? start
              : 720;
          assign(
            index + 1,
            [
              ...rows,
              {
                id: `${m.round}-${index}`,
                role,
                participantId: p.id,
                interval,
                status: 'proposed',
              },
            ],
            score + preference,
          );
        }
      };
      assign(0, [], 0);
    }
  }
  const assignments = best?.assignments ?? [];
  return {
    round: m.round,
    status: best ? 'feasible' : 'infeasible',
    assignments,
    notices: best
      ? [
          {
            id: 'ready',
            kind: 'info',
            title: '모든 역할을 배정했어요',
            detail:
              '역할 자격·가능시간·동시 중복배정·동반 가능시간을 확인했습니다.',
          },
          ...(m.participants.some(p => p.conditions.note.trim())
            ? [
                {
                  id: 'note',
                  kind: 'warning' as const,
                  title: '자연어 조건을 확인해 주세요',
                  detail:
                    '입력한 메모는 자동 제약이 아닙니다. 구조화된 역할·시간·선호·동반조건을 확인한 뒤 동의하세요.',
                },
              ]
            : []),
        ]
      : [
          {
            id: 'conflict',
            kind: 'error',
            title: '현재 조건으로는 배정할 수 없어요',
            detail:
              '같은 시간에 모든 역할을 맡을 인원이 부족합니다. 역할, 가능시간 또는 동반조건을 변경해 주세요.',
          },
        ],
  };
}
