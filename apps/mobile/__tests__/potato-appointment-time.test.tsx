import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import Renderer, { act } from 'react-test-renderer';
import { CreateAppointmentStep3TimeScreen } from '../src/potato/screens/CreateAppointmentStep3TimeScreen';
import {
  formatDateKey,
  isValidDateKey,
  mergeAppointmentTimeSlots,
  parseTimeRange,
} from '../src/potato/services/appointmentTime';
import {
  findButton,
  hasText as containsText,
} from '../test-utils/potato-test-utils';
import type {
  AppointmentCreationDraft,
  AppointmentCreationTimeSlot,
} from '../src/potato/types/appointmentCreation';

function slot(
  id: string,
  date: string,
  startTimeMinutes: number,
  endTimeMinutes: number,
): AppointmentCreationTimeSlot {
  return { id, date, startTimeMinutes, endTimeMinutes };
}

function setTimeInput(
  tree: Renderer.ReactTestRenderer,
  label: string,
  value: string,
) {
  return act(async () => {
    tree.root.findByProps({ accessibilityLabel: label }).props.onChangeText(value);
  });
}

test('time range validates normal, equal and reverse ranges', () => {
  expect(parseTimeRange('09', '10', '10', '20')).toEqual({
    valid: true,
    value: { startTimeMinutes: 550, endTimeMinutes: 620 },
  });
  expect(parseTimeRange('09', '00', '09', '00')).toMatchObject({
    valid: false,
  });
  expect(parseTimeRange('10', '00', '09', '59')).toMatchObject({
    valid: false,
  });
  expect(parseTimeRange('23', '30', '24', '00')).toEqual({
    valid: true,
    value: { startTimeMinutes: 1410, endTimeMinutes: 1440 },
  });
  expect(parseTimeRange('24', '10', '24', '30')).toMatchObject({
    valid: false,
  });
});

test('date keys are validated without timezone date parsing', () => {
  expect(formatDateKey(2028, 2, 29)).toBe('2028-02-29');
  expect(isValidDateKey('2028-02-29')).toBe(true);
  expect(isValidDateKey('2027-02-29')).toBe(false);
  expect(isValidDateKey('2027-13-01')).toBe(false);
});

test('time slots merge overlapping and adjacent ranges only within the same date', () => {
  expect(
    mergeAppointmentTimeSlots([
      slot('late', '2026-10-31', 660, 720),
      slot('early', '2026-10-31', 540, 600),
      slot('overlap', '2026-10-31', 590, 670),
      slot('adjacent', '2026-10-31', 720, 780),
      slot('next-day', '2026-11-01', 540, 600),
      slot('next-year', '2027-10-31', 780, 840),
    ]),
  ).toEqual([
    slot('early', '2026-10-31', 540, 780),
    slot('next-day', '2026-11-01', 540, 600),
    slot('next-year', '2027-10-31', 780, 840),
  ]);
});

test('step three edits, deletes, preserves draft and restores state after back navigation', async () => {
  const initialDraft: AppointmentCreationDraft = {
    title: '저녁 약속',
    category: '식사',
    duration: '2시간',
    location: '서울',
    invitedFriends: ['민수', '지훈'],
    selectedCalendarDate: '2026-10-31',
    timeInput: {
      startHour: '09',
      startMinute: '00',
      endHour: '10',
      endMinute: '00',
    },
    timeSlots: [],
  };
  const onRequestStep4 = jest.fn();
  const onBack = jest.fn();
  let latestDraft = initialDraft;
  let tree!: Renderer.ReactTestRenderer;

  function FlowHarness() {
    const [draft, setDraft] = useState(initialDraft);
    const [showStep3, setShowStep3] = useState(true);

    if (!showStep3) {
      return (
        <Pressable
          accessibilityRole="button"
          onPress={() => setShowStep3(true)}
        >
          <Text>{`STEP 1·2 유지: ${draft.title} · ${draft.category} · ${draft.duration} · ${draft.location} · ${draft.invitedFriends?.join(', ')}`}</Text>
          <Text>STEP 3 재진입</Text>
        </Pressable>
      );
    }

    return (
      <CreateAppointmentStep3TimeScreen
        draft={draft}
        onDraftChange={next => {
          latestDraft = next;
          setDraft(next);
        }}
        onBack={() => {
          onBack();
          setShowStep3(false);
        }}
        onRequestStep4={onRequestStep4}
      />
    );
  }

  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <FlowHarness />
      </SafeAreaProvider>,
    );
  });

  await act(async () => {
    tree.root.findByProps({ accessibilityLabel: '시간 추가' }).props.onPress();
  });
  expect(latestDraft.timeSlots).toHaveLength(1);
  expect(latestDraft.timeSlots).toEqual([
    expect.objectContaining({
      date: '2026-10-31',
      startTimeMinutes: 540,
      endTimeMinutes: 600,
    }),
  ]);

  const firstSlot = latestDraft.timeSlots![0];
  await act(async () => {
    tree.root
      .findByProps({
        accessibilityLabel: '2026년 10월 31일 09:00 시간 수정',
      })
      .props.onPress();
  });
  await setTimeInput(tree, '종료 시', '11');
  await act(async () => {
    tree.root.findByProps({ accessibilityLabel: '시간 수정' }).props.onPress();
  });
  expect(latestDraft.timeSlots).toEqual([
    { ...firstSlot, endTimeMinutes: 660 },
  ]);

  await act(async () => {
    tree.root
      .findByProps({
        accessibilityLabel: '2026년 10월 31일 09:00 시간 삭제',
      })
      .props.onPress();
  });
  expect(latestDraft.timeSlots).toEqual([]);

  await setTimeInput(tree, '시작 시', '09');
  await setTimeInput(tree, '시작 분', '00');
  await setTimeInput(tree, '종료 시', '10');
  await setTimeInput(tree, '종료 분', '00');
  await act(async () => {
    tree.root.findByProps({ accessibilityLabel: '시간 추가' }).props.onPress();
  });
  await act(async () => findButton(tree, '이전').props.onPress());
  expect(
    containsText(
      tree,
      'STEP 1·2 유지: 저녁 약속 · 식사 · 2시간 · 서울 · 민수, 지훈',
    ),
  ).toBe(true);
  await act(async () => findButton(tree, 'STEP 3 재진입').props.onPress());
  expect(
    tree.root
      .findAllByType(Text)
      .some(element => element.props.children === '2026년 10월 31일'),
  ).toBe(true);
  expect(latestDraft.timeSlots).toHaveLength(1);
  expect(latestDraft.invitedFriends).toEqual(['민수', '지훈']);

  await act(async () => findButton(tree, '다음').props.onPress());
  expect(onRequestStep4).toHaveBeenCalledWith(
    expect.objectContaining({
      title: '저녁 약속',
      category: '식사',
      duration: '2시간',
      location: '서울',
      invitedFriends: ['민수', '지훈'],
      timeSlots: latestDraft.timeSlots,
    }),
  );
  expect(onBack).toHaveBeenCalledTimes(1);
  await act(async () => tree.unmount());
});

test('next proceeds with saved slots when the new time inputs are empty', async () => {
  const savedSlots = [
    slot('first-day', '2026-10-31', 540, 600),
    slot('next-day', '2026-11-01', 840, 960),
  ];
  const initialDraft: AppointmentCreationDraft = {
    title: '저녁 약속',
    category: '식사',
    duration: '2시간',
    location: '서울',
    invitedFriends: ['친구 ID'],
    selectedCalendarDate: '2026-10-31',
    timeInput: {
      startHour: '',
      startMinute: '',
      endHour: '',
      endMinute: '',
    },
    timeSlots: savedSlots,
  };
  const onRequestStep4 = jest.fn();
  let tree!: Renderer.ReactTestRenderer;

  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <CreateAppointmentStep3TimeScreen
          draft={initialDraft}
          onDraftChange={jest.fn()}
          onBack={jest.fn()}
          onRequestStep4={onRequestStep4}
        />
      </SafeAreaProvider>,
    );
  });

  await act(async () => findButton(tree, '다음').props.onPress());
  expect(onRequestStep4).toHaveBeenCalledWith(initialDraft);
  expect(onRequestStep4.mock.calls[0][0].timeSlots).toEqual(savedSlots);
  expect(onRequestStep4.mock.calls[0][0]).toMatchObject({
    title: '저녁 약속',
    invitedFriends: ['친구 ID'],
  });

  await act(async () => tree.unmount());
});

test('next without saved slots asks the user to add a time', async () => {
  const onRequestStep4 = jest.fn();
  let tree!: Renderer.ReactTestRenderer;

  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <CreateAppointmentStep3TimeScreen
          draft={{
            selectedCalendarDate: '2026-10-31',
            timeInput: {
              startHour: '',
              startMinute: '',
              endHour: '',
              endMinute: '',
            },
          }}
          onDraftChange={jest.fn()}
          onBack={jest.fn()}
          onRequestStep4={onRequestStep4}
        />
      </SafeAreaProvider>,
    );
  });

  await act(async () => findButton(tree, '다음').props.onPress());
  expect(onRequestStep4).not.toHaveBeenCalled();
  expect(
    containsText(
      tree,
      '시간 추가 버튼으로 가능한 시간을 먼저 저장해주세요.',
    ),
  ).toBe(true);

  await act(async () => tree.unmount());
});

test('next reports incomplete pending input without changing saved slots', async () => {
  const savedSlot = slot('saved', '2026-10-31', 540, 600);
  const draft: AppointmentCreationDraft = {
    selectedCalendarDate: '2026-10-31',
    timeInput: {
      startHour: '09',
      startMinute: '',
      endHour: '',
      endMinute: '',
    },
    timeSlots: [savedSlot],
  };
  const onDraftChange = jest.fn();
  const onRequestStep4 = jest.fn();
  let tree!: Renderer.ReactTestRenderer;

  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <CreateAppointmentStep3TimeScreen
          draft={draft}
          onDraftChange={onDraftChange}
          onBack={jest.fn()}
          onRequestStep4={onRequestStep4}
        />
      </SafeAreaProvider>,
    );
  });

  await act(async () => findButton(tree, '다음').props.onPress());
  expect(onRequestStep4).not.toHaveBeenCalled();
  expect(onDraftChange).not.toHaveBeenCalled();
  expect(containsText(tree, '시작과 종료 시간을 입력해주세요.')).toBe(true);
  expect(draft.timeSlots).toEqual([savedSlot]);

  await act(async () => tree.unmount());
});

test('repeated next presses never duplicate saved slots', async () => {
  const savedSlots = [
    slot('first-day', '2026-10-31', 540, 600),
    slot('next-day', '2026-11-01', 840, 960),
  ];
  const draft: AppointmentCreationDraft = {
    timeSlots: savedSlots,
    timeInput: {
      startHour: '',
      startMinute: '',
      endHour: '',
      endMinute: '',
    },
  };
  const onRequestStep4 = jest.fn();
  let tree!: Renderer.ReactTestRenderer;

  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <CreateAppointmentStep3TimeScreen
          draft={draft}
          onDraftChange={jest.fn()}
          onBack={jest.fn()}
          onRequestStep4={onRequestStep4}
        />
      </SafeAreaProvider>,
    );
  });

  const nextButton = findButton(tree, '다음');
  await act(async () => nextButton.props.onPress());
  await act(async () => nextButton.props.onPress());
  expect(onRequestStep4).toHaveBeenCalledTimes(2);
  expect(onRequestStep4.mock.calls.map(([nextDraft]) => nextDraft.timeSlots)).toEqual([
    savedSlots,
    savedSlots,
  ]);

  await act(async () => tree.unmount());
});

test('next saves an edited slot once and preserves slots on other dates', async () => {
  const initialSlots = [
    slot('edit-me', '2026-10-31', 540, 600),
    slot('keep-me', '2026-11-01', 840, 960),
  ];
  const initialDraft: AppointmentCreationDraft = {
    title: '저녁 약속',
    invitedFriends: ['친구 ID'],
    selectedCalendarDate: '2026-10-31',
    editingTimeSlotId: 'edit-me',
    timeInput: {
      startHour: '10',
      startMinute: '30',
      endHour: '11',
      endMinute: '30',
    },
    timeSlots: initialSlots,
  };
  const onDraftChange = jest.fn();
  const onRequestStep4 = jest.fn();
  let tree!: Renderer.ReactTestRenderer;

  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <CreateAppointmentStep3TimeScreen
          draft={initialDraft}
          onDraftChange={onDraftChange}
          onBack={jest.fn()}
          onRequestStep4={onRequestStep4}
        />
      </SafeAreaProvider>,
    );
  });

  await act(async () => findButton(tree, '다음').props.onPress());
  const nextDraft = onRequestStep4.mock.calls[0][0] as AppointmentCreationDraft;
  expect(nextDraft.timeSlots).toEqual([
    slot('edit-me', '2026-10-31', 630, 690),
    slot('keep-me', '2026-11-01', 840, 960),
  ]);
  expect(nextDraft).toMatchObject({
    title: '저녁 약속',
    invitedFriends: ['친구 ID'],
    editingTimeSlotId: undefined,
  });
  expect(onDraftChange).toHaveBeenCalledWith(nextDraft);

  await act(async () => tree.unmount());
});

test('step three rejects equal and reversed times before adding or requesting the next step', async () => {
  let draft: AppointmentCreationDraft = {
    selectedCalendarDate: '2026-10-31',
    timeInput: {
      startHour: '09',
      startMinute: '00',
      endHour: '09',
      endMinute: '00',
    },
  };
  const onRequestStep4 = jest.fn();
  let tree!: Renderer.ReactTestRenderer;
  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <CreateAppointmentStep3TimeScreen
          draft={draft}
          onDraftChange={next => {
            draft = next;
          }}
          onBack={jest.fn()}
          onRequestStep4={onRequestStep4}
        />
      </SafeAreaProvider>,
    );
  });
  await act(async () => {
    tree.root.findByProps({ accessibilityLabel: '시간 추가' }).props.onPress();
  });
  await act(async () => findButton(tree, '다음').props.onPress());
  expect(draft.timeSlots ?? []).toHaveLength(0);
  expect(onRequestStep4).not.toHaveBeenCalled();
  expect(
    tree.root
      .findAllByType(Text)
      .some(text => text.props.children === '종료 시간은 시작 시간보다 늦어야 합니다.'),
  ).toBe(true);
  await act(async () => tree.unmount());
});

test('step three uses a compact responsive calendar and keeps time entry available', async () => {
  let tree!: Renderer.ReactTestRenderer;

  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <CreateAppointmentStep3TimeScreen
          draft={{
            selectedCalendarDate: '2026-10-31',
            timeInput: {
              startHour: '09',
              startMinute: '30',
              endHour: '10',
              endMinute: '00',
            },
            timeSlots: [slot('saved', '2026-10-31', 570, 600)],
          }}
          onDraftChange={jest.fn()}
          onBack={jest.fn()}
          onRequestStep4={jest.fn()}
        />
      </SafeAreaProvider>,
    );
  });

  const dateCell = tree.root.findByProps({
    accessibilityLabel: '2026년 10월 31일',
  });
  const cellStyle = StyleSheet.flatten(dateCell.props.style);
  expect(cellStyle.height).toBeGreaterThanOrEqual(36);
  expect(cellStyle.height).toBeLessThanOrEqual(42);
  expect(cellStyle.aspectRatio).toBeUndefined();
  expect(dateCell.props.accessibilityState.selected).toBe(true);
  expect(tree.root.findAllByType(TextInput)).toHaveLength(4);
  expect(findButton(tree, '다음')).toBeDefined();
  expect(containsText(tree, '09:30 ~ 10:00')).toBe(true);

  await act(async () => tree.unmount());
});
