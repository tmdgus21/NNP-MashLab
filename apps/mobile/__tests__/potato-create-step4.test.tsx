import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import Renderer, { act } from 'react-test-renderer';
import { CreateAppointmentStep4AdjustScreen } from '../src/potato/screens/CreateAppointmentStep4AdjustScreen';
import { getAppointmentRecommendationMessage } from '../src/potato/services/appointmentRecommendation';
import type { AppointmentCreationDraft } from '../src/potato/types/appointmentCreation';
import {
  findButton,
  findViewsWithProps,
  hasText,
  textContent,
} from '../test-utils/potato-test-utils';

const initialDraft: AppointmentCreationDraft = {
  title: '저녁 약속',
  category: '식사',
  duration: '2시간',
  location: '서울',
  invitedFriends: ['민수', '지훈'],
  timeSlots: [
    {
      id: 'slot-1',
      date: '2026-10-31',
      startTimeMinutes: 9 * 60 + 30,
      endTimeMinutes: 11 * 60,
    },
    {
      id: 'slot-2',
      date: '2026-11-01',
      startTimeMinutes: 14 * 60,
      endTimeMinutes: 16 * 60,
    },
  ],
};

function hasTextContaining(
  tree: Renderer.ReactTestRenderer,
  text: string,
): boolean {
  return tree.root.findAllByType(Text).some(element => {
    const children = element.props.children;
    return textContent(children).includes(text);
  });
}

test('step four displays creation data and reports missing AI request information', async () => {
  const onRequestAiRecommendation = jest.fn();
  const onBack = jest.fn();
  const onNavigateStep = jest.fn();
  let tree!: Renderer.ReactTestRenderer;

  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <CreateAppointmentStep4AdjustScreen
          nickname="가은"
          draft={initialDraft}
          onBack={onBack}
          onNavigateStep={onNavigateStep}
          onRequestAiRecommendation={onRequestAiRecommendation}
        />
      </SafeAreaProvider>,
    );
  });

  expect(hasText(tree, '2026년 10월 31일 (토)')).toBe(true);
  expect(hasText(tree, '가은')).toBe(true);
  expect(hasText(tree, '민수')).toBe(true);
  expect(hasText(tree, '지훈')).toBe(true);
  expect(hasText(tree, '친구 일정 미제출')).toBe(true);
  expect(hasText(tree, '10월 14일')).toBe(false);

  for (const step of [1, 2, 3] as const) {
    await act(async () => {
      tree.root
        .findByProps({
          accessibilityLabel: `${step}단계 ${
            step === 1 ? '정보' : step === 2 ? '초대' : '나의 시간'
          }`,
        })
        .props.onPress();
    });
  }
  expect(onNavigateStep.mock.calls.map(([step]) => step)).toEqual([1, 2, 3]);

  await act(async () => findButton(tree, '이전').props.onPress());
  expect(onBack).toHaveBeenCalledTimes(1);

  await act(async () => findButton(tree, 'AI 조율').props.onPress());
  expect(onRequestAiRecommendation).toHaveBeenCalledWith(
    expect.objectContaining({
      status: 'needs_information',
      missingFields: expect.arrayContaining([
        'organizerId',
        'timeZone',
        'invitedFriendIds',
      ]),
    }),
  );

  await act(async () => tree.unmount());
});

test('step four preserves draft after back and re-entry without editing step 1 to 3 data', async () => {
  let tree!: Renderer.ReactTestRenderer;
  const onRequestAiRecommendation = jest.fn();
  function FlowHarness() {
    const [draft] = useState(initialDraft);
    const [visible, setVisible] = useState(true);

    return visible ? (
      <CreateAppointmentStep4AdjustScreen
        draft={draft}
        onBack={() => setVisible(false)}
        onNavigateStep={jest.fn()}
        onRequestAiRecommendation={onRequestAiRecommendation}
      />
    ) : (
      <Pressable onPress={() => setVisible(true)}>
        <Text>STEP 4 재진입</Text>
      </Pressable>
    );
  }

  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <FlowHarness />
      </SafeAreaProvider>,
    );
  });

  await act(async () => findButton(tree, '이전').props.onPress());
  await act(async () => findButton(tree, 'STEP 4 재진입').props.onPress());
  expect(hasText(tree, '2026년 10월 31일 (토)')).toBe(true);
  expect(hasText(tree, '친구 일정 미제출')).toBe(true);
  await act(async () => findButton(tree, 'AI 조율').props.onPress());
  expect(onRequestAiRecommendation).toHaveBeenLastCalledWith(
    expect.objectContaining({ status: 'needs_information' }),
  );

  await act(async () => tree.unmount());
});

test('empty or invalid draft reports missing information without fabricating a request', async () => {
  const onRequestAiRecommendation = jest.fn();
  let tree!: Renderer.ReactTestRenderer;

  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <CreateAppointmentStep4AdjustScreen
          draft={{}}
          onBack={jest.fn()}
          onNavigateStep={jest.fn()}
          onRequestAiRecommendation={onRequestAiRecommendation}
        />
      </SafeAreaProvider>,
    );
  });

  expect(hasText(tree, '등록된 시간이 없습니다.')).toBe(true);
  expect(
    hasText(tree, 'STEP 3에서 날짜와 가능한 시간을 추가해주세요.'),
  ).toBe(true);
  expect(hasText(tree, '그래프를 좌우로 밀어 확인')).toBe(false);
  expect(
    tree.root
      .findAllByType(Text)
      .some(text => textContent(text.props.children).includes('모임 이름, 활동')),
  ).toBe(false);
  await act(async () => findButton(tree, 'AI 조율').props.onPress());
  expect(onRequestAiRecommendation).toHaveBeenCalledWith(
    expect.objectContaining({ status: 'needs_information' }),
  );

  await act(async () => tree.unmount());

  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <CreateAppointmentStep4AdjustScreen
          draft={{
            ...initialDraft,
            timeSlots: [
              {
                id: 'bad',
                date: '2026-02-31',
                startTimeMinutes: 800,
                endTimeMinutes: 700,
              },
            ],
          }}
          onBack={jest.fn()}
          onNavigateStep={jest.fn()}
          onRequestAiRecommendation={onRequestAiRecommendation}
        />
      </SafeAreaProvider>,
    );
  });
  expect(hasTextContaining(tree, '날짜와 가능한 시간 정보를 확인해주세요.')).toBe(true);
  await act(async () => findButton(tree, 'AI 조율').props.onPress());
  expect(onRequestAiRecommendation).toHaveBeenCalledTimes(2);

  await act(async () => tree.unmount());
});

test('recommendation preparation messages are user-facing and hide internal field names', () => {
  const message = getAppointmentRecommendationMessage({
    status: 'needs_information',
    missingFields: ['organizerId', 'timeZone', 'participantResponses'],
    invalidFields: ['duration'],
    knownContext: {
      participants: [],
      availabilitySubmissions: [],
    },
  });

  expect(message).toContain('참여자 정보와 시간대 설정');
  expect(message).toContain('초대된 참여자의 응답');
  expect(message).toContain('소요 시간은');
  expect(message).not.toContain('organizerId');
  expect(message).not.toContain('timeZone');
});

test('date selection switches the graph and keeps exact minute-based segments', async () => {
  const draft: AppointmentCreationDraft = {
    ...initialDraft,
    invitedFriends: [],
    invitedFriendIds: [],
    organizerId: 'organizer-1',
    timeZone: 'Asia/Seoul',
    selectedCalendarDate: '2026-11-01',
    timeSlots: [
      {
        id: 'half-hour',
        date: '2026-10-31',
        startTimeMinutes: 9 * 60 + 30,
        endTimeMinutes: 10 * 60,
      },
      {
        id: 'full-day',
        date: '2026-11-01',
        startTimeMinutes: 0,
        endTimeMinutes: 24 * 60,
      },
    ],
  };
  const onRequestAiRecommendation = jest.fn();
  let tree!: Renderer.ReactTestRenderer;

  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <CreateAppointmentStep4AdjustScreen
          draft={draft}
          onBack={jest.fn()}
          onNavigateStep={jest.fn()}
          onRequestAiRecommendation={onRequestAiRecommendation}
        />
      </SafeAreaProvider>,
    );
  });

  const segment = (label: string) =>
    findViewsWithProps(tree, {
      testID: 'time-segment',
      accessibilityLabel: label,
    })[0];
  const fullDaySegment = segment('00:00부터 24:00까지 가능');
  expect(fullDaySegment).toBeDefined();
  expect(
    tree.root.findByProps({
      accessibilityLabel: '2026년 11월 1일 날짜 선택',
    }).props.accessibilityState.selected,
  ).toBe(true);
  expect(StyleSheet.flatten(fullDaySegment!.props.style)).toMatchObject({
    left: 0,
    width: 600,
  });
  expect(hasText(tree, '00:00 ~ 24:00')).toBe(true);

  await act(async () => {
    tree.root
      .findByProps({ accessibilityLabel: '2026년 10월 31일 날짜 선택' })
      .props.onPress();
  });
  const firstDaySegment = segment('09:30부터 10:00까지 가능');
  expect(firstDaySegment).toBeDefined();
  expect(StyleSheet.flatten(firstDaySegment!.props.style)).toMatchObject({
    left: 237.5,
    width: 12.5,
  });
  expect(hasText(tree, '09:30 ~ 10:00')).toBe(true);

  await act(async () => {
    tree.root
      .findByProps({ accessibilityLabel: '2026년 11월 1일 날짜 선택' })
      .props.onPress();
  });
  expect(segment('09:30부터 10:00까지 가능')).toBeUndefined();
  expect(hasText(tree, '00:00 ~ 24:00')).toBe(true);
  expect(
    tree.root.findByProps({
      accessibilityLabel: '2026년 11월 1일 날짜 선택',
    }).props.accessibilityState.selected,
  ).toBe(true);

  await act(async () => findButton(tree, 'AI 조율').props.onPress());
  expect(onRequestAiRecommendation).toHaveBeenCalledWith(
    expect.objectContaining({
      status: 'ready',
      request: expect.objectContaining({
        timeZone: 'Asia/Seoul',
        availabilitySubmissions: [
          expect.objectContaining({
            participantId: 'organizer-1',
            status: 'submitted',
            timeSlots: draft.timeSlots,
          }),
        ],
      }),
    }),
  );
  await act(async () => tree.unmount());
});

test('selected date without slots shows an empty state and friends remain unsubmitted', async () => {
  let tree!: Renderer.ReactTestRenderer;
  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <CreateAppointmentStep4AdjustScreen
          draft={{
            ...initialDraft,
            selectedCalendarDate: '2026-10-30',
          }}
          onBack={jest.fn()}
          onNavigateStep={jest.fn()}
          onRequestAiRecommendation={jest.fn()}
        />
      </SafeAreaProvider>,
    );
  });

  expect(hasText(tree, '이 날짜에 등록된 시간이 없습니다.')).toBe(true);
  expect(
    hasText(tree, 'STEP 3에서 이 날짜의 가능한 시간을 추가해주세요.'),
  ).toBe(true);
  expect(hasText(tree, '그래프를 좌우로 밀어 확인')).toBe(false);
  expect(hasText(tree, '10/30 (금)')).toBe(true);
  expect(hasText(tree, '10/31 (토)')).toBe(true);
  expect(
    hasText(tree, '초대 친구는 아직 가능한 시간을 제출하지 않았습니다.'),
  ).toBe(true);

  await act(async () => tree.unmount());
});

test('invited friends are shown as unsubmitted, never as available', async () => {
  let tree!: Renderer.ReactTestRenderer;
  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <CreateAppointmentStep4AdjustScreen
          draft={initialDraft}
          onBack={jest.fn()}
          onNavigateStep={jest.fn()}
          onRequestAiRecommendation={jest.fn()}
        />
      </SafeAreaProvider>,
    );
  });

  expect(hasText(tree, '친구 일정 미제출')).toBe(true);
  expect(hasText(tree, 'ID 확인 필요')).toBe(true);
  expect(
    findViewsWithProps(tree, {
      accessibilityLabel: '친구 가능 시간 미제출',
    }).length,
  ).toBe(2);
  expect(
    findViewsWithProps(tree, { testID: 'time-segment' }).length,
  ).toBe(1);

  await act(async () => tree.unmount());
});

test('submitted invitee availability is displayed separately from the creator slots', async () => {
  const draft: AppointmentCreationDraft = {
    ...initialDraft,
    invitedFriends: ['민수'],
    invitedFriendIds: ['friend-1'],
    invitedFriendNameById: { 'friend-1': '민수' },
    participants: [
      {
        id: 'organizer-1',
        role: 'organizer',
        invitationStatus: 'not_applicable',
        participationStatus: 'accepted',
      },
      {
        id: 'friend-1',
        role: 'invitee',
        invitationStatus: 'sent',
        participationStatus: 'accepted',
      },
    ],
    availabilitySubmissions: [
      {
        participantId: 'friend-1',
        status: 'submitted',
        timeZone: 'Asia/Seoul',
        timeSlots: [
          {
            id: 'friend-slot',
            date: '2026-10-31',
            startTimeMinutes: 12 * 60,
            endTimeMinutes: 13 * 60,
          },
        ],
      },
    ],
    organizerId: 'organizer-1',
    timeZone: 'Asia/Seoul',
  };
  const onRequestAiRecommendation = jest.fn();
  let tree!: Renderer.ReactTestRenderer;

  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <CreateAppointmentStep4AdjustScreen
          draft={draft}
          onBack={jest.fn()}
          onNavigateStep={jest.fn()}
          onRequestAiRecommendation={onRequestAiRecommendation}
        />
      </SafeAreaProvider>,
    );
  });

  expect(hasText(tree, '시간 제출 완료')).toBe(true);
  expect(
    findViewsWithProps(tree, {
      accessibilityLabel: '친구가 제출한 가능 시간',
    }),
  ).toHaveLength(1);
  expect(
    findViewsWithProps(tree, { testID: 'time-segment' }).map(segment =>
      segment.props.accessibilityLabel,
    ),
  ).toEqual([
    '09:30부터 11:00까지 가능',
    '12:00부터 13:00까지 가능',
  ]);
  await act(async () => findButton(tree, 'AI 조율').props.onPress());
  expect(onRequestAiRecommendation).toHaveBeenCalledWith(
    expect.objectContaining({ status: 'ready' }),
  );

  await act(async () => tree.unmount());
});

test('submitted friend dates remain visible when the creator has no slot on that date', async () => {
  const draft: AppointmentCreationDraft = {
    ...initialDraft,
    invitedFriends: ['민수'],
    invitedFriendIds: ['friend-1'],
    invitedFriendNameById: { 'friend-1': '민수' },
    organizerId: 'organizer-1',
    timeZone: 'Asia/Seoul',
    timeSlots: [],
    participants: [
      {
        id: 'friend-1',
        role: 'invitee',
        invitationStatus: 'sent',
        participationStatus: 'accepted',
      },
    ],
    availabilitySubmissions: [
      {
        participantId: 'friend-1',
        status: 'submitted',
        timeZone: 'Asia/Seoul',
        timeSlots: [
          {
            id: 'friend-slot',
            date: '2026-11-02',
            startTimeMinutes: 14 * 60,
            endTimeMinutes: 15 * 60,
          },
        ],
      },
    ],
  };
  let tree!: Renderer.ReactTestRenderer;

  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <CreateAppointmentStep4AdjustScreen
          draft={draft}
          onBack={jest.fn()}
          onNavigateStep={jest.fn()}
          onRequestAiRecommendation={jest.fn()}
        />
      </SafeAreaProvider>,
    );
  });

  expect(hasText(tree, '2026년 11월 2일 (월)')).toBe(true);
  expect(hasText(tree, '민수 가능 시간')).toBe(true);
  expect(
    findViewsWithProps(tree, { testID: 'time-segment' }).map(segment =>
      segment.props.accessibilityLabel,
    ),
  ).toEqual(['14:00부터 15:00까지 가능']);

  await act(async () => tree.unmount());
});
