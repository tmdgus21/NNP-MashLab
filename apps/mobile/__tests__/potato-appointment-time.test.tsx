import React, { useState } from 'react';
import { Pressable, Text, TextInput } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import Renderer, { act } from 'react-test-renderer';
import { CreateAppointmentStep3TimeScreen } from '../src/potato/screens/CreateAppointmentStep3TimeScreen';
import {
  formatDateKey,
  isValidDateKey,
  mergeAppointmentTimeSlots,
  parseTimeRange,
} from '../src/potato/services/appointmentTime';
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

function findButton(
  tree: Renderer.ReactTestRenderer,
  label: string,
): Renderer.ReactTestInstance {
  return tree.root
    .findAllByType(Pressable)
    .find(button =>
      button.findAllByType(Text).some(text => text.props.children === label),
    )!;
}

function containsText(tree: Renderer.ReactTestRenderer, text: string): boolean {
  return tree.root
    .findAllByType(Text)
    .some(element => element.props.children === text);
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
