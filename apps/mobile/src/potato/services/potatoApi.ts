import { z } from 'zod';

/**
 * Real client for the Potato Meet server (v2.1). Authentication is the account
 * bearer token from /v1/auth/*; everything else lives under /v2. There are no
 * fallbacks or canned responses here: a failure is surfaced as PotatoApiError.
 */

export class PotatoApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(status: number, code: string | null, message: string) {
    super(message);
    this.name = 'PotatoApiError';
    this.status = status;
    this.code = code;
  }
}

const USER_MESSAGES: Record<string, string> = {
  AVAILABILITY_EMPTY:
    '가능한 시간이 없다면 시간을 제출하지 말고, 방장에게 알리거나 모임에서 나가 주세요. 응답하지 않아도 불참으로 처리되지는 않아요.',
  ROOM_CODE_NOT_FOUND: '초대 코드를 다시 확인해 주세요.',
  NICKNAME_TAKEN: '이 모임에서 이미 사용 중인 이름이에요.',
  ROOM_FULL: '모임 인원이 가득 찼어요.',
  MEMBERSHIP_INACTIVE: '이 모임에서 나간 기록이 있어 다시 참가할 수 없어요.',
  ROUND_ALREADY_FINALIZED: '이미 확정된 모임이라 더 이상 바꿀 수 없어요.',
  SUBMISSION_VERSION_CONFLICT:
    '다른 기기에서 시간이 바뀌었어요. 새로고침한 뒤 다시 시도해 주세요.',
  STALE_AGENT_RUN: '참여자나 시간이 바뀌어 이전 계산이 무효가 됐어요. 다시 계산해 주세요.',
  INVALID_MEETING_SNAPSHOT:
    '계산할 수 없는 상태예요. 참여자 2명 이상이 모였는지, 최소 참석 인원이 맞는지 확인해 주세요.',
  INPUT_REVISION_CONFLICT: '모임 정보가 바뀌었어요. 새로고침한 뒤 다시 시도해 주세요.',
  HOST_CANNOT_LEAVE: '방장은 모임을 나갈 수 없어요.',
  LEAVE_NOT_SUPPORTED_FOR_INVITED: '초대받은 참여자는 아직 모임을 나갈 수 없어요.',
  NOT_AN_ATTENDEE: '이 후보에 참석자로 포함된 사람만 응답할 수 있어요.',
  CONSENT_LOCKED: '방장이 이미 결정해서 동의를 바꿀 수 없어요.',
  APPROVAL_NOT_PENDING: '모든 참석자가 동의해야 승인할 수 있어요.',
  DECISION_VERSION_CONFLICT: '상태가 바뀌었어요. 새로고침한 뒤 다시 시도해 주세요.',
  RSVP_DEADLINE_REQUIRED: '응답 마감 기능이 없어 초대자를 제외할 수 없어요.',
};

function messageFor(status: number, code: string | null, detail: unknown): string {
  if (code && USER_MESSAGES[code]) {
    return USER_MESSAGES[code];
  }
  if (typeof detail === 'string' && detail) {
    return detail;
  }
  if (status === 401) {
    return '로그인이 필요해요.';
  }
  if (status === 403) {
    return '이 작업을 할 권한이 없어요.';
  }
  if (status === 404) {
    return '찾을 수 없어요.';
  }
  if (status === 422 && Array.isArray(detail)) {
    return '입력값을 확인해 주세요.';
  }
  return `요청을 처리하지 못했어요 (${status}${code ? `, ${code}` : ''}).`;
}

const loose = z.looseObject;

export const authSchema = loose({
  accountId: z.string(),
  email: z.string(),
  token: z.string(),
});
const meSchema = loose({ accountId: z.string(), email: z.string() });

export const roomViewSchema = loose({
  roomId: z.string(),
  code: z.string(),
  title: z.string(),
  activity: z.string(),
  location: z.string(),
  durationMinutes: z.number(),
  dates: z.array(z.string()),
  minimumAttendeeCount: z.number(),
  hostMemberId: z.string().nullable(),
  status: z.string(),
  coordinationRound: z.number(),
  agentInputRevision: z.number(),
  eligibleParticipantCount: z.number(),
  me: loose({ memberId: z.string(), accountId: z.string(), role: z.string() }).nullable(),
});
export type RoomView = z.infer<typeof roomViewSchema>;

const roomListSchema = loose({
  rooms: z.array(
    loose({
      roomId: z.string(),
      code: z.string(),
      title: z.string(),
      activity: z.string(),
      location: z.string(),
      durationMinutes: z.number(),
      dates: z.array(z.string()),
      role: z.string(),
      myNickname: z.string(),
      eligibleParticipantCount: z.number(),
      finalized: z.boolean(),
      finalStartsAt: z.string().nullable(),
      finalEndsAt: z.string().nullable(),
    }),
  ),
});
export type RoomSummary = z.infer<typeof roomListSchema>['rooms'][number];

const participantsSchema = loose({
  roomId: z.string(),
  eligibleParticipantCount: z.number(),
  participants: z.array(
    loose({
      participantId: z.string(),
      memberId: z.string().nullable(),
      displayName: z.string().nullable(),
      role: z.enum(['organizer', 'invitee']),
      invitationStatus: z.enum(['not_applicable', 'not_sent', 'sent']),
      participationStatus: z.enum(['pending', 'accepted', 'declined']),
      eligibility: z.string(),
      joinPath: z.enum(['organizer', 'invitation', 'code']),
      availability: loose({
        status: z.enum(['not_submitted', 'submitted']),
        version: z.number(),
        updatedAt: z.string().nullable(),
      }),
    }),
  ),
});
export type ParticipantsView = z.infer<typeof participantsSchema>;

export interface AvailabilitySlotInput {
  date: string;
  startTimeMinutes: number;
  endTimeMinutes: number;
}
const availabilitySchema = loose({
  status: z.enum(['not_submitted', 'submitted']),
  version: z.number(),
  timeSlots: z.array(
    loose({ date: z.string(), startTimeMinutes: z.number(), endTimeMinutes: z.number() }),
  ),
});
export type AvailabilityView = z.infer<typeof availabilitySchema>;

const runAcceptedSchema = loose({ runId: z.string(), status: z.string() });
const runStatusSchema = loose({
  runId: z.string(),
  status: z.string(),
  errorCode: z.string().nullable(),
});
export type RunStatus = z.infer<typeof runStatusSchema>;

const candidatesSchema = loose({
  runId: z.string(),
  status: z.string(),
  candidates: z.array(
    loose({
      candidateId: z.string(),
      rank: z.number(),
      startsAt: z.string(),
      endsAt: z.string(),
      candidateType: z.string(),
      members: z.array(
        loose({
          roomMemberId: z.string(),
          participationStatus: z.string(),
          consentStatus: z.string().nullable(),
        }),
      ),
    }),
  ),
});
export type CandidatesView = z.infer<typeof candidatesSchema>;

const latestRunSchema = loose({
  roomId: z.string(),
  currentInputRevision: z.number(),
  run: loose({
    runId: z.string(),
    status: z.string(),
    errorCode: z.string().nullable(),
    sourceRevision: z.number(),
    current: z.boolean(),
    approvalStatus: z.string(),
    selectedCandidateId: z.string().nullable(),
    finalized: z.boolean(),
  }).nullable(),
});
export type LatestRunView = z.infer<typeof latestRunSchema>;

const decisionSchema = loose({
  runId: z.string(),
  status: z.string(),
  approvalStatus: z.string(),
  selectedCandidateId: z.string().nullable(),
  consentRound: z.number().nullable(),
  decisionVersion: z.number(),
  attendees: z.array(
    loose({ roomMemberId: z.string(), consentStatus: z.string().nullable() }),
  ),
  allAgreed: z.boolean(),
  finalized: z.boolean(),
  graphSync: z.string(),
});
export type DecisionView = z.infer<typeof decisionSchema>;

const finalResultSchema = loose({
  finalized: z.boolean(),
  coordinationRound: z.number(),
  runId: z.string().nullable().optional(),
  startsAt: z.string().nullable().optional(),
  endsAt: z.string().nullable().optional(),
  attendeeMemberIds: z.array(z.string()).optional(),
  inputCurrent: z.boolean().nullable().optional(),
});
export type FinalResultView = z.infer<typeof finalResultSchema>;

export interface CreateRoomInput {
  title: string;
  activity: string;
  location: string;
  durationMinutes: number;
  dates: string[];
  minimumAttendeeCount?: number;
  nickname: string;
}

export interface PotatoApiConfig {
  /** Server origin such as https://host (no /v1 or /v2 suffix). */
  baseUrl: string;
  token: () => Promise<string | null>;
  fetcher?: typeof fetch;
  timeoutMs?: number;
}

let keyCounter = 0;
/** Idempotency keys only need to be unique per user, not secret. */
export function newRequestKey(prefix: string): string {
  keyCounter += 1;
  return `${prefix}-${Date.now().toString(36)}-${Math.random()
    .toString(36)
    .slice(2, 10)}-${keyCounter}`;
}

export function createPotatoApi(config: PotatoApiConfig) {
  const base = config.baseUrl.replace(/\/$/, '');
  const fetcher = config.fetcher ?? fetch;

  async function call<T>(
    method: string,
    path: string,
    schema: z.ZodType<T>,
    options: { body?: unknown; key?: string; auth?: boolean } = {},
  ): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), config.timeoutMs ?? 20000);
    try {
      const token = options.auth === false ? null : await config.token();
      let response: Response;
      try {
        response = await fetcher(`${base}${path}`, {
          method,
          signal: controller.signal,
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(options.key ? { 'Idempotency-Key': options.key } : {}),
          },
          ...(options.body === undefined ? {} : { body: JSON.stringify(options.body) }),
        });
      } catch {
        throw new PotatoApiError(
          0,
          'NETWORK',
          '서버에 연결하지 못했어요. 네트워크를 확인한 뒤 다시 시도해 주세요.',
        );
      }
      const text = await response.text();
      let parsed: unknown = null;
      try {
        parsed = text ? JSON.parse(text) : null;
      } catch {
        parsed = null;
      }
      if (!response.ok) {
        const detail = (parsed as { detail?: unknown } | null)?.detail;
        const code =
          detail && typeof detail === 'object' && !Array.isArray(detail)
            ? ((detail as { code?: unknown }).code as string | undefined) ?? null
            : null;
        throw new PotatoApiError(response.status, code, messageFor(response.status, code, detail));
      }
      const result = schema.safeParse(parsed);
      if (!result.success) {
        throw new PotatoApiError(
          response.status,
          'BAD_RESPONSE',
          '서버 응답 형식이 예상과 달라요. 앱을 최신 버전으로 업데이트해 주세요.',
        );
      }
      return result.data;
    } finally {
      clearTimeout(timer);
    }
  }

  const room = (id: string) => `/v2/rooms/${encodeURIComponent(id)}`;
  const run = (roomId: string, runId: string) =>
    `${room(roomId)}/agent-runs/${encodeURIComponent(runId)}`;

  return {
    auth: {
      register: (email: string, password: string) =>
        call('POST', '/v1/auth/register', authSchema, { body: { email, password }, auth: false }),
      login: (email: string, password: string) =>
        call('POST', '/v1/auth/login', authSchema, { body: { email, password }, auth: false }),
      me: () => call('GET', '/v1/auth/me', meSchema),
      logout: () => call('POST', '/v1/auth/logout', z.unknown()),
    },
    rooms: {
      create: (input: CreateRoomInput, key: string) =>
        call('POST', '/v2/rooms', roomViewSchema, { body: input, key }),
      list: () => call('GET', '/v2/rooms', roomListSchema),
      get: (id: string) => call('GET', room(id), roomViewSchema),
      join: (code: string, nickname: string) =>
        call('POST', '/v2/rooms/join', roomViewSchema, { body: { code: code.trim().toUpperCase(), nickname } }),
      participants: (id: string) => call('GET', `${room(id)}/participants`, participantsSchema),
      leave: (id: string) => call('POST', `${room(id)}/leave`, z.unknown()),
    },
    availability: {
      get: (roomId: string) => call('GET', `${room(roomId)}/availability/me`, availabilitySchema),
      put: (roomId: string, timeSlots: AvailabilitySlotInput[], expectedVersion?: number) =>
        call('PUT', `${room(roomId)}/availability/me`, availabilitySchema, {
          body: { timeZone: 'Asia/Seoul', timeSlots, ...(expectedVersion === undefined ? {} : { expectedVersion }) },
        }),
    },
    runs: {
      start: (roomId: string, expectedInputRevision: number, key: string) =>
        call('POST', `${room(roomId)}/agent-runs`, runAcceptedSchema, {
          body: { expectedInputRevision },
          key,
        }),
      latest: (roomId: string) => call('GET', `${room(roomId)}/latest-run`, latestRunSchema),
      get: (roomId: string, runId: string) => call('GET', run(roomId, runId), runStatusSchema),
      candidates: (roomId: string, runId: string) =>
        call('GET', `${run(roomId, runId)}/candidates`, candidatesSchema),
    },
    decision: {
      get: (roomId: string, runId: string) => call('GET', `${run(roomId, runId)}/decision`, decisionSchema),
      select: (roomId: string, runId: string, candidateId: string, expectedVersion?: number) =>
        call('POST', `${run(roomId, runId)}/select`, decisionSchema, {
          body: { candidateId, ...(expectedVersion === undefined ? {} : { expectedVersion }) },
        }),
      consent: (roomId: string, runId: string, decision: 'AGREE' | 'DISAGREE' | 'WITHDRAW') =>
        call('POST', `${run(roomId, runId)}/consent`, decisionSchema, { body: { decision } }),
      approve: (roomId: string, runId: string, decision: 'APPROVE' | 'REJECT') =>
        call('POST', `${run(roomId, runId)}/approval`, decisionSchema, { body: { decision } }),
      finalize: (roomId: string, runId: string) =>
        call('POST', `${run(roomId, runId)}/finalize`, decisionSchema, { body: {} }),
      finalResult: (roomId: string) =>
        call('GET', `${room(roomId)}/agent-final-result`, finalResultSchema),
    },
  };
}

export type PotatoApi = ReturnType<typeof createPotatoApi>;
