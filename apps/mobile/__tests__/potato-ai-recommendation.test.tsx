import React from 'react';
import { KeyboardAvoidingView, ScrollView, TextInput } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import Renderer, { act } from 'react-test-renderer';
import { AiRecommendationScreen } from '../src/potato/screens/AiRecommendationScreen';
import { getDisplayableRecommendationCandidates } from '../src/potato/services/appointmentRecommendation';
import {
  appointmentRecommendationPreviewCases,
  completeRecommendationPreviewDraft,
  incompleteRecommendationPreviewDraft,
} from '../src/potato/dev/appointmentRecommendationFixtures';
import type {
  AppointmentRecommendationAgentSnapshot,
  AppointmentRecommendationCandidate,
} from '../src/potato/types/appointmentRecommendation';
import { findButton, hasText } from '../test-utils/potato-test-utils';

const revision = 'dev-revision-1';
const candidate: AppointmentRecommendationCandidate = {
  candidateId: 'candidate-one',
  date: '2026-11-08',
  startMinute: 14 * 60,
  endMinute: 15 * 60 + 30,
  timeZone: 'Asia/Seoul',
  recommendationType: 'ALL_AVAILABLE',
  attendeeIds: ['organizer-preview', 'friend-preview-1', 'friend-preview-2'],
  unavailableIds: [],
  verified: true,
  sourceRevision: revision,
  explanation: {
    agentSummary: '모든 필수 조건을 만족하는 예시입니다.',
    optimizerSummary: '결정론적 검증 결과 예시입니다.',
  },
};

function snapshot(
  status: AppointmentRecommendationAgentSnapshot['status'],
  overrides: Partial<AppointmentRecommendationAgentSnapshot> = {},
): AppointmentRecommendationAgentSnapshot {
  return {
    status,
    agentRunId: 'run-one',
    sourceRevision: revision,
    requiredAttendeeIds: ['organizer-preview'],
    ...overrides,
  };
}

async function renderScreen(
  props: Partial<React.ComponentProps<typeof AiRecommendationScreen>> = {},
) {
  let tree!: Renderer.ReactTestRenderer;
  const fixture = appointmentRecommendationPreviewCases.allAvailable;
  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <AiRecommendationScreen
          draft={completeRecommendationPreviewDraft}
          preparation={{
            status: 'ready',
            request: {
              appointment: {
                title: '개발 프리뷰 저녁 모임',
                category: '식사',
                duration: '90분',
                location: '서울 샘플 장소',
              },
              durationMinutes: 90,
              timeZone: 'Asia/Seoul',
              participants: [],
              availabilitySubmissions: [],
              clientAppointmentId: 'dev-preview-appointment',
            },
          }}
          snapshot={fixture.snapshot}
          currentSourceRevision={fixture.currentSourceRevision}
          onBack={jest.fn()}
          onStartRecommendation={jest.fn()}
          onReschedule={jest.fn()}
          onCandidateSelected={jest.fn()}
          onRequestApproval={jest.fn()}
          onRetry={jest.fn()}
          onCancel={jest.fn()}
          {...props}
        />
      </SafeAreaProvider>,
    );
  });
  return tree;
}

test('all-attendee candidates take priority and no more than three are displayed', async () => {
  const partial: AppointmentRecommendationCandidate = {
    ...candidate,
    candidateId: 'partial',
    recommendationType: 'PARTIAL_ALTERNATIVE',
    attendeeIds: ['organizer-preview'],
    unavailableIds: ['friend-preview-2'],
  };
  const tree = await renderScreen({
    snapshot: snapshot('AWAITING_APPROVAL', {
      allAvailableExhausted: true,
      candidates: [
        partial,
        candidate,
        { ...candidate, candidateId: 'all-2' },
        { ...candidate, candidateId: 'all-3' },
        { ...candidate, candidateId: 'all-4' },
      ],
    }),
  });

  const candidateButtons = tree.root.findAll(
    node =>
      typeof node.props.onPress === 'function' &&
      typeof node.props.accessibilityLabel === 'string' &&
      node.props.accessibilityLabel.startsWith('추천 후보 '),
  );
  expect(candidateButtons).toHaveLength(3);
  expect(
    candidateButtons.every(button =>
      button.props.accessibilityLabel.includes('2026년 11월 8일'),
    ),
  ).toBe(true);
  expect(hasText(tree, '전원 참석')).toBe(true);
  expect(hasText(tree, '일부 참석 대안')).toBe(false);
  await act(async () => tree.unmount());
});

test('partial-attendance alternatives are shown only after full attendance was exhausted', async () => {
  const partial: AppointmentRecommendationCandidate = {
    ...candidate,
    candidateId: 'partial',
    recommendationType: 'PARTIAL_ALTERNATIVE',
    attendeeIds: ['organizer-preview', 'friend-preview-1'],
    unavailableIds: ['friend-preview-2'],
  };
  const tree = await renderScreen({
    snapshot: snapshot('PARTIAL_ALTERNATIVE', {
      allAvailableExhausted: false,
      candidates: [partial],
    }),
  });
  expect(
    hasText(
      tree,
      '검증 상태와 입력 버전을 확인할 수 있는 추천 후보가 없습니다.',
    ),
  ).toBe(true);
  await act(async () => tree.unmount());

  const validTree = await renderScreen({
    snapshot: snapshot('PARTIAL_ALTERNATIVE', {
      allAvailableExhausted: true,
      candidates: [partial],
    }),
  });
  expect(
    hasText(
      validTree,
      '전원 참석 가능 여부를 확인한 뒤 제공하는 일부 참석 대안입니다.',
    ),
  ).toBe(true);
  expect(hasText(validTree, '참석 가능: 나, 지훈')).toBe(true);
  expect(hasText(validTree, '참석 불가: 민수')).toBe(true);
  await act(async () => validTree.unmount());
});

test('unsubmitted invitees remain pending and are not listed as unavailable', async () => {
  const tree = await renderScreen({
    draft: incompleteRecommendationPreviewDraft,
    snapshot: appointmentRecommendationPreviewCases.waiting.snapshot,
    preparation: {
      status: 'needs_information',
      missingFields: ['participantResponses', 'participantAvailability'],
      invalidFields: [],
      knownContext: { participants: [], availabilitySubmissions: [] },
    },
  });
  expect(hasText(tree, '응답 대기')).toBe(true);
  expect(
    hasText(tree, '응답 대기 중인 참여자는 불참으로 간주하지 않습니다.'),
  ).toBe(true);
  expect(hasText(tree, '참석 불가: 민수')).toBe(false);
  await act(async () => tree.unmount());
});

test('every supported agent status has a visible screen state', async () => {
  const expectedLabels: Record<
    AppointmentRecommendationAgentSnapshot['status'],
    string
  > = {
    WAITING_FOR_INPUT: '추천 요청을 기다리고 있어요',
    ANALYZING: '참여자 응답과 조건을 분석하고 있어요',
    RUNNING_TOOLS: '일정 가능 여부를 계산하고 있어요',
    ALL_AVAILABLE: '전원이 참석할 수 있는 후보를 찾았어요',
    PARTIAL_ALTERNATIVE: '전원 참석 후보가 없어 대안을 찾았어요',
    NO_FEASIBLE_SCHEDULE: '조건에 맞는 일정을 찾지 못했어요',
    AWAITING_APPROVAL: '후보가 방장 승인을 기다리고 있어요',
    STALE: '입력 정보가 변경되어 다시 계산해야 해요',
    ERROR: '추천을 처리하지 못했어요',
  };
  for (const fixture of Object.values(appointmentRecommendationPreviewCases)) {
    const tree = await renderScreen({
      draft: fixture.draft,
      snapshot: fixture.snapshot,
      currentSourceRevision: fixture.currentSourceRevision,
      developmentFixture: true,
    });
    expect(hasText(tree, expectedLabels[fixture.status])).toBe(true);
    await act(async () => tree.unmount());
  }
});

test('unverified, stale, and incomplete candidates are withheld from selection', async () => {
  const invalidCandidates = [
    { ...candidate, candidateId: 'unverified', verified: false },
    { ...candidate, candidateId: 'wrong-revision', sourceRevision: 'older' },
    {
      ...candidate,
      candidateId: 'missing-required',
      attendeeIds: ['friend-preview-1'],
    },
    { ...candidate, candidateId: 'bad-date', date: '2026-02-31' },
    { ...candidate, candidateId: 'bad-time-zone', timeZone: 'Not/A_Timezone' },
  ];
  const result = getDisplayableRecommendationCandidates(
    snapshot('ALL_AVAILABLE', { candidates: invalidCandidates }),
    revision,
  );
  expect(result).toBeUndefined();

  const tree = await renderScreen({
    snapshot: snapshot('ALL_AVAILABLE', { candidates: invalidCandidates }),
  });
  expect(
    hasText(
      tree,
      '검증 상태와 입력 버전을 확인할 수 있는 추천 후보가 없습니다.',
    ),
  ).toBe(true);
  await act(async () => tree.unmount());
});

test('changing the recommendation revision blocks candidate approval', async () => {
  const onRequestApproval = jest.fn();
  const tree = await renderScreen({
    snapshot: snapshot('ALL_AVAILABLE', { candidates: [candidate] }),
    currentSourceRevision: 'new-revision',
    onRequestApproval,
  });
  expect(
    tree.root.findAll(
      node => node.props.accessibilityLabel?.startsWith('추천 후보 ') === true,
    ),
  ).toHaveLength(0);
  expect(
    tree.root.findAllByProps({
      accessibilityLabel: '선택한 후보로 방장 승인 요청',
    }),
  ).toHaveLength(0);
  expect(onRequestApproval).not.toHaveBeenCalled();
  await act(async () => tree.unmount());
});

test('natural-language rescheduling submits run and revision context', async () => {
  const onReschedule = jest.fn();
  const tree = await renderScreen({
    snapshot: snapshot('AWAITING_APPROVAL', { candidates: [candidate] }),
    onReschedule,
  });
  const input = tree.root.findByType(TextInput);
  await act(async () => input.props.onChangeText('일요일 오후로 다시 찾아줘'));
  await act(async () => findButton(tree, '전송').props.onPress());

  expect(onReschedule).toHaveBeenCalledWith({
    agentRunId: 'run-one',
    sourceRevision: revision,
    requestText: '일요일 오후로 다시 찾아줘',
  });
  expect(hasText(tree, 'API 미연결 상태라 요청을 전송하지 않았습니다.')).toBe(
    true,
  );
  await act(async () => tree.unmount());
});

test('empty rescheduling text cannot be sent', async () => {
  const onReschedule = jest.fn();
  const tree = await renderScreen({
    snapshot: snapshot('AWAITING_APPROVAL', { candidates: [candidate] }),
    onReschedule,
  });
  const sendButton = findButton(tree, '전송');
  expect(sendButton.props.accessibilityState.disabled).toBe(true);
  await act(async () => sendButton.props.onPress());
  expect(onReschedule).not.toHaveBeenCalled();
  await act(async () => tree.unmount());
});

test('API-disconnected state is explicit and running agents cannot start duplicate requests', async () => {
  const onStartRecommendation = jest.fn();
  const onCancel = jest.fn();
  const tree = await renderScreen({
    snapshot: snapshot('RUNNING_TOOLS'),
    onStartRecommendation,
    onCancel,
    apiConnected: false,
  });
  expect(
    hasText(tree, 'AI 서버 미연결 · 추천 요청은 아직 전송되지 않습니다.'),
  ).toBe(true);
  expect(findButton(tree, 'STEP 4로 돌아가기').props.accessibilityRole).toBe(
    'button',
  );
  expect(
    tree.root.findAllByProps({ accessibilityLabel: 'AI 추천 요청' }),
  ).toHaveLength(0);
  expect(onStartRecommendation).not.toHaveBeenCalled();
  await act(async () => findButton(tree, '취소').props.onPress());
  expect(onCancel).toHaveBeenCalledWith('run-one');
  await act(async () => tree.unmount());
});

test('a connected initial request cannot be triggered twice before state updates', async () => {
  const onStartRecommendation = jest.fn();
  const tree = await renderScreen({
    snapshot: snapshot('WAITING_FOR_INPUT', { agentRunId: undefined }),
    apiConnected: true,
    onStartRecommendation,
  });
  await act(async () => findButton(tree, 'AI 추천 요청').props.onPress());
  await act(async () => findButton(tree, 'AI 추천 요청').props.onPress());
  expect(onStartRecommendation).toHaveBeenCalledTimes(1);
  await act(async () => tree.unmount());
});

test('error retry, candidate selection, and approval request are separate actions', async () => {
  const onRetry = jest.fn();
  const errorTree = await renderScreen({
    snapshot: snapshot('ERROR', {
      error: {
        code: 'TOOL_FAILURE',
        userMessage: '계산을 완료하지 못했습니다.',
        retryable: true,
      },
    }),
    onRetry,
  });
  expect(hasText(errorTree, '계산을 완료하지 못했습니다.')).toBe(true);
  await act(async () => findButton(errorTree, '다시 시도').props.onPress());
  expect(onRetry).toHaveBeenCalledWith({
    agentRunId: 'run-one',
    sourceRevision: revision,
  });
  await act(async () => errorTree.unmount());

  const partial: AppointmentRecommendationCandidate = {
    ...candidate,
    candidateId: 'partial',
    recommendationType: 'PARTIAL_ALTERNATIVE',
    attendeeIds: ['organizer-preview', 'friend-preview-1'],
    unavailableIds: ['friend-preview-2'],
  };
  const onCandidateSelected = jest.fn();
  const onRequestApproval = jest.fn();
  const tree = await renderScreen({
    snapshot: snapshot('PARTIAL_ALTERNATIVE', {
      allAvailableExhausted: true,
      candidates: [partial],
    }),
    onCandidateSelected,
    onRequestApproval,
  });
  const card = tree.root.findAll(
    node =>
      typeof node.props.onPress === 'function' &&
      typeof node.props.accessibilityLabel === 'string' &&
      node.props.accessibilityLabel.startsWith('추천 후보 1,'),
  )[0];
  expect(card).toBeDefined();
  await act(async () => card.props.onPress());
  await act(async () =>
    findButton(tree, '선택한 후보로 방장 승인 요청').props.onPress(),
  );
  expect(onCandidateSelected).toHaveBeenCalledWith({
    agentRunId: 'run-one',
    sourceRevision: revision,
    candidateId: 'partial',
  });
  expect(onRequestApproval).toHaveBeenCalledWith({
    agentRunId: 'run-one',
    sourceRevision: revision,
    candidateId: 'partial',
  });
  expect(hasText(tree, '일정은 아직 확정되지 않았어요.')).toBe(false);
  await act(async () => tree.unmount());
});

test('awaiting-approval state does not expose a second approval request', async () => {
  const onRequestApproval = jest.fn();
  const tree = await renderScreen({
    snapshot: snapshot('AWAITING_APPROVAL', { candidates: [candidate] }),
    onRequestApproval,
  });
  expect(
    hasText(
      tree,
      '방장의 승인을 기다리는 중입니다. 일정은 아직 확정되지 않았어요.',
    ),
  ).toBe(true);
  expect(
    tree.root.findAllByProps({
      accessibilityLabel: '선택한 후보로 방장 승인 요청',
    }),
  ).toHaveLength(0);
  expect(onRequestApproval).not.toHaveBeenCalled();
  await act(async () => tree.unmount());
});

test('request input and send control remain in the safe-area keyboard-aware screen', async () => {
  const tree = await renderScreen();
  expect(tree.root.findAllByType(KeyboardAvoidingView)).toHaveLength(1);
  expect(tree.root.findByType(KeyboardAvoidingView).props.behavior).toBe(
    'padding',
  );
  expect(tree.root.findByType(ScrollView).props.keyboardDismissMode).toBe(
    'none',
  );
  expect(tree.root.findByType(TextInput).props.accessibilityLabel).toBe(
    '재조율 요청',
  );
  expect(
    tree.root.findByProps({ accessibilityLabel: '재조율 요청 전송' }),
  ).toBeDefined();
  await act(async () => tree.unmount());
});

test('STEP 4 appointment and availability data remain visible in the recommendation request context', async () => {
  const onStartRecommendation = jest.fn();
  const preparation = {
    status: 'ready' as const,
    request: {
      appointment: {
        title: '개발 프리뷰 저녁 모임',
        category: '식사',
        duration: '90분',
        location: '서울 샘플 장소',
      },
      durationMinutes: 90,
      timeZone: 'Asia/Seoul',
      participants: [],
      availabilitySubmissions: [],
      clientAppointmentId: 'dev-preview-appointment',
    },
  };
  const tree = await renderScreen({
    preparation,
    snapshot: snapshot('WAITING_FOR_INPUT', { agentRunId: undefined }),
    onStartRecommendation,
  });
  expect(hasText(tree, '개발 프리뷰 저녁 모임')).toBe(true);
  expect(hasText(tree, '지훈')).toBe(true);
  expect(hasText(tree, '시간 제출 완료')).toBe(true);
  await act(async () => findButton(tree, 'AI 추천 요청').props.onPress());
  expect(onStartRecommendation).toHaveBeenCalledWith(preparation.request);
  await act(async () => tree.unmount());
});
