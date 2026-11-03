import type {
  AvailabilityView,
  CandidatesView,
  DecisionView,
  FinalResultView,
  LatestRunView,
  ParticipantsView,
  PotatoApi,
  RoomView,
} from './potatoApi';

export type ParticipantRow = ParticipantsView['participants'][number];

export interface RoomState {
  room: RoomView;
  participants: ParticipantRow[];
  myAvailability: AvailabilityView;
  latest: LatestRunView;
  candidates: CandidatesView | null;
  decision: DecisionView | null;
  finalResult: FinalResultView;
}

const DECIDABLE = new Set(['ALL_AVAILABLE', 'PARTIAL_ALTERNATIVE', 'AWAITING_APPROVAL']);

/** One consistent read of everything a phone shows for a room. */
export async function loadRoomState(api: PotatoApi, roomId: string): Promise<RoomState> {
  const [room, participants, myAvailability, latest, finalResult] = await Promise.all([
    api.rooms.get(roomId),
    api.rooms.participants(roomId),
    api.availability.get(roomId),
    api.runs.latest(roomId),
    api.decision.finalResult(roomId),
  ]);
  let candidates: CandidatesView | null = null;
  let decision: DecisionView | null = null;
  const run = latest.run;
  if (run && run.current && DECIDABLE.has(run.status)) {
    [candidates, decision] = await Promise.all([
      api.runs.candidates(roomId, run.runId),
      api.decision.get(roomId, run.runId),
    ]);
  }
  return { room, participants: participants.participants, myAvailability, latest, candidates, decision, finalResult };
}

export function participantLabel(person: ParticipantRow): string {
  if (person.participationStatus === 'declined') {
    return '참여 거절';
  }
  if (person.eligibility !== 'active') {
    return '방장이 제외함';
  }
  if (person.participationStatus === 'pending') {
    return '응답 대기';
  }
  return person.availability.status === 'submitted' ? '시간 제출 완료' : '시간 미제출';
}

/** Who the Agent is still waiting for. Never an absence: they are simply unresolved. */
export function missingInput(participants: ParticipantRow[]): string[] {
  return participants
    .filter(
      person =>
        person.eligibility === 'active' &&
        person.participationStatus !== 'declined' &&
        (person.participationStatus === 'pending' || person.availability.status !== 'submitted'),
    )
    .map(person => `${person.displayName ?? '초대한 사람'} (${participantLabel(person)})`);
}

export function runStatusMessage(state: RoomState): string {
  const run = state.latest.run;
  if (!run) {
    return '아직 일정을 계산하지 않았어요.';
  }
  if (!run.current || run.status === 'STALE') {
    return '참여자나 시간이 바뀌어 이전 계산이 무효가 됐어요. 다시 계산해 주세요.';
  }
  switch (run.status) {
    case 'QUEUED':
    case 'RUNNING':
      return '계산 중이에요…';
    case 'WAITING_FOR_INPUT': {
      const waiting = missingInput(state.participants);
      return waiting.length
        ? `아직 기다리는 사람이 있어요: ${waiting.join(', ')}`
        : '입력을 기다리고 있어요. 다시 계산해 주세요.';
    }
    case 'NO_FEASIBLE_SCHEDULE':
      return '모두 가능한 시간을 찾지 못했어요. 가능한 시간을 늘려 주세요.';
    case 'FAILED':
    case 'ERROR':
      return `계산에 실패했어요${run.errorCode ? ` (${run.errorCode})` : ''}. 다시 시도해 주세요.`;
    case 'CANCELLED':
      return '계산이 취소됐어요.';
    default:
      return '계산이 끝났어요. 후보를 확인해 주세요.';
  }
}
