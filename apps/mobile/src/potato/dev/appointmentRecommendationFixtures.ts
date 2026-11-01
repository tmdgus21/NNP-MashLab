import type { AppointmentCreationDraft } from '../types/appointmentCreation';
import type {
  AppointmentRecommendationAgentSnapshot,
  AppointmentRecommendationCandidate,
  AppointmentRecommendationAgentStatus,
} from '../types/appointmentRecommendation';

const revision = 'dev-revision-1';
const candidateTime = {
  date: '2026-11-08',
  startMinute: 14 * 60,
  endMinute: 15 * 60 + 30,
  timeZone: 'Asia/Seoul',
  verified: true,
  sourceRevision: revision,
  explanation: {
    agentSummary: '조건을 만족하는 후보 예시입니다.',
    optimizerSummary: '개발 프리뷰용으로 검증 상태를 표시한 예시입니다.',
  },
} as const;

function candidate(
  candidateId: string,
  recommendationType: AppointmentRecommendationCandidate['recommendationType'],
  attendeeIds: string[],
  unavailableIds: string[],
): AppointmentRecommendationCandidate {
  return {
    candidateId,
    ...candidateTime,
    recommendationType,
    attendeeIds,
    unavailableIds,
  };
}

export const completeRecommendationPreviewDraft: AppointmentCreationDraft = {
  title: '개발 프리뷰 저녁 모임',
  category: '식사',
  duration: '90분',
  location: '서울 샘플 장소',
  organizerId: 'organizer-preview',
  timeZone: 'Asia/Seoul',
  clientAppointmentId: 'dev-preview-appointment',
  invitedFriendIds: ['friend-preview-1', 'friend-preview-2'],
  invitedFriendNameById: {
    'friend-preview-1': '지훈',
    'friend-preview-2': '민수',
  },
  participants: [
    {
      id: 'organizer-preview',
      role: 'organizer',
      invitationStatus: 'not_applicable',
      participationStatus: 'accepted',
    },
    {
      id: 'friend-preview-1',
      role: 'invitee',
      invitationStatus: 'sent',
      participationStatus: 'accepted',
    },
    {
      id: 'friend-preview-2',
      role: 'invitee',
      invitationStatus: 'sent',
      participationStatus: 'accepted',
    },
  ],
  availabilitySubmissions: [
    {
      participantId: 'organizer-preview',
      status: 'submitted',
      timeSlots: [
        {
          id: 'organizer-preview-slot',
          date: '2026-11-08',
          startTimeMinutes: 13 * 60,
          endTimeMinutes: 18 * 60,
        },
      ],
      timeZone: 'Asia/Seoul',
    },
    {
      participantId: 'friend-preview-1',
      status: 'submitted',
      timeSlots: [
        {
          id: 'friend-preview-1-slot',
          date: '2026-11-08',
          startTimeMinutes: 13 * 60,
          endTimeMinutes: 18 * 60,
        },
      ],
      timeZone: 'Asia/Seoul',
    },
    {
      participantId: 'friend-preview-2',
      status: 'submitted',
      timeSlots: [
        {
          id: 'friend-preview-2-slot',
          date: '2026-11-08',
          startTimeMinutes: 9 * 60,
          endTimeMinutes: 12 * 60,
        },
      ],
      timeZone: 'Asia/Seoul',
    },
  ],
  timeSlots: [
    {
      id: 'organizer-preview-slot',
      date: '2026-11-08',
      startTimeMinutes: 13 * 60,
      endTimeMinutes: 18 * 60,
    },
  ],
};

export const incompleteRecommendationPreviewDraft: AppointmentCreationDraft = {
  ...completeRecommendationPreviewDraft,
  participants: [
    ...completeRecommendationPreviewDraft.participants!.slice(0, 2),
    {
      id: 'friend-preview-2',
      role: 'invitee',
      invitationStatus: 'sent',
      participationStatus: 'pending',
    },
  ],
  availabilitySubmissions: [
    completeRecommendationPreviewDraft.availabilitySubmissions![0],
    completeRecommendationPreviewDraft.availabilitySubmissions![1],
    { participantId: 'friend-preview-2', status: 'not_submitted' },
  ],
};

const allAvailableCandidates = [
  candidate(
    'preview-all-1',
    'ALL_AVAILABLE',
    ['organizer-preview', 'friend-preview-1', 'friend-preview-2'],
    [],
  ),
  candidate(
    'preview-all-2',
    'ALL_AVAILABLE',
    ['organizer-preview', 'friend-preview-1', 'friend-preview-2'],
    [],
  ),
  candidate(
    'preview-all-3',
    'ALL_AVAILABLE',
    ['organizer-preview', 'friend-preview-1', 'friend-preview-2'],
    [],
  ),
  candidate(
    'preview-all-4',
    'ALL_AVAILABLE',
    ['organizer-preview', 'friend-preview-1', 'friend-preview-2'],
    [],
  ),
];

const partialCandidate = candidate(
  'preview-partial-1',
  'PARTIAL_ALTERNATIVE',
  ['organizer-preview', 'friend-preview-1'],
  ['friend-preview-2'],
);

export interface AppointmentRecommendationPreviewCase {
  label: string;
  status: AppointmentRecommendationAgentStatus;
  snapshot: AppointmentRecommendationAgentSnapshot;
  draft: AppointmentCreationDraft;
  currentSourceRevision?: string;
}

const baseRun = {
  agentRunId: 'dev-preview-run',
  sourceRevision: revision,
  requiredAttendeeIds: ['organizer-preview'],
};

export const appointmentRecommendationPreviewCases: Record<
  string,
  AppointmentRecommendationPreviewCase
> = {
  waiting: {
    label: '일부 참여자 미제출',
    status: 'WAITING_FOR_INPUT',
    draft: incompleteRecommendationPreviewDraft,
    snapshot: {
      status: 'WAITING_FOR_INPUT',
      history: [
        {
          requestId: 'preview-unsubmitted',
          requestText: '참여자 응답 상태를 확인해주세요',
          status: 'not_sent',
          responseSummary: '초대 친구의 응답과 시간 제출을 기다리는 중입니다.',
        },
      ],
    },
  },
  analyzing: {
    label: '분석 중',
    status: 'ANALYZING',
    draft: completeRecommendationPreviewDraft,
    snapshot: { ...baseRun, status: 'ANALYZING' },
    currentSourceRevision: revision,
  },
  tools: {
    label: '도구 실행 중',
    status: 'RUNNING_TOOLS',
    draft: completeRecommendationPreviewDraft,
    snapshot: { ...baseRun, status: 'RUNNING_TOOLS' },
    currentSourceRevision: revision,
  },
  allAvailable: {
    label: '전원 참석 추천',
    status: 'ALL_AVAILABLE',
    draft: completeRecommendationPreviewDraft,
    snapshot: {
      ...baseRun,
      status: 'ALL_AVAILABLE',
      candidates: allAvailableCandidates,
    },
    currentSourceRevision: revision,
  },
  partial: {
    label: '최대 참석 대안',
    status: 'PARTIAL_ALTERNATIVE',
    draft: completeRecommendationPreviewDraft,
    snapshot: {
      ...baseRun,
      status: 'PARTIAL_ALTERNATIVE',
      allAvailableExhausted: true,
      candidates: [partialCandidate],
    },
    currentSourceRevision: revision,
  },
  noSchedule: {
    label: '추천 없음',
    status: 'NO_FEASIBLE_SCHEDULE',
    draft: completeRecommendationPreviewDraft,
    snapshot: { ...baseRun, status: 'NO_FEASIBLE_SCHEDULE' },
    currentSourceRevision: revision,
  },
  error: {
    label: '도구 오류',
    status: 'ERROR',
    draft: completeRecommendationPreviewDraft,
    snapshot: {
      ...baseRun,
      status: 'ERROR',
      error: {
        code: 'PREVIEW_TOOL_ERROR',
        userMessage: '일정 계산을 완료하지 못했습니다. 다시 시도해주세요.',
        retryable: true,
      },
    },
    currentSourceRevision: revision,
  },
  stale: {
    label: '재계산 필요',
    status: 'STALE',
    draft: completeRecommendationPreviewDraft,
    snapshot: {
      ...baseRun,
      status: 'STALE',
      candidates: [
        {
          ...candidate(
            'preview-stale',
            'ALL_AVAILABLE',
            ['organizer-preview', 'friend-preview-1', 'friend-preview-2'],
            [],
          ),
          sourceRevision: 'dev-old-revision',
        },
      ],
    },
    currentSourceRevision: revision,
  },
  approval: {
    label: '승인 대기',
    status: 'AWAITING_APPROVAL',
    draft: completeRecommendationPreviewDraft,
    snapshot: {
      ...baseRun,
      status: 'AWAITING_APPROVAL',
      candidates: [allAvailableCandidates[0]],
      history: [
        {
          requestId: 'preview-reschedule',
          requestText: '토요일 오후로 찾아줘',
          status: 'completed',
          responseSummary:
            '검증된 후보를 준비했습니다. 최종 확정 전 방장 승인이 필요합니다.',
        },
      ],
    },
    currentSourceRevision: revision,
  },
};

export const initialAppointmentRecommendationPreviewCase =
  appointmentRecommendationPreviewCases.waiting;
