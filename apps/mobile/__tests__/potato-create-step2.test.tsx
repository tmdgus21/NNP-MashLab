import React, { useState } from 'react';
import { Pressable, Text } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import Renderer, { act } from 'react-test-renderer';
import { CreateAppointmentStep2InviteScreen } from '../src/potato/screens/CreateAppointmentStep2InviteScreen';
import type { AppointmentCreationDraft } from '../src/potato/types/appointmentCreation';
import type { PotatoFriend } from '../src/potato/types/friend';
import {
  findButton,
  hasText as textExists,
} from '../test-utils/potato-test-utils';

const friends: PotatoFriend[] = [
  { id: 'friend-1', name: '민수' },
  { id: 'friend-2', name: '지훈' },
  { id: 'friend-3', name: '영희' },
];

test('step two keeps friend selection and step one draft across back and re-entry', async () => {
  const initialDraft: AppointmentCreationDraft = {
    title: '저녁 약속',
    category: '식사',
    duration: '2시간',
    location: '서울',
  };
  let latestDraft = initialDraft;
  const onDraftChange = jest.fn((draft: AppointmentCreationDraft) => {
    latestDraft = draft;
  });
  const onRequestStep3 = jest.fn();
  let tree!: Renderer.ReactTestRenderer;

  function FlowHarness() {
    const [draft, setDraft] = useState(initialDraft);
    const [step, setStep] = useState<'step1' | 'step2' | 'step3'>('step2');

    if (step === 'step1') {
      return (
        <Pressable
          accessibilityRole="button"
          onPress={() => setStep('step2')}
        >
          <Text>{`STEP 1: ${draft.title} · ${draft.category} · ${draft.duration} · ${draft.location}`}</Text>
          <Text>STEP 2로 돌아가기</Text>
        </Pressable>
      );
    }

    if (step === 'step3') {
      return (
        <ViewForTest>
          <Text>{`STEP 3: ${draft.invitedFriends?.join(', ') ?? ''}`}</Text>
          <Text>{`STEP 1 유지: ${draft.title} · ${draft.category} · ${draft.duration} · ${draft.location}`}</Text>
        </ViewForTest>
      );
    }

    return (
      <CreateAppointmentStep2InviteScreen
        friends={friends}
        draft={draft}
        onBack={() => setStep('step1')}
        onDraftChange={nextDraft => {
          latestDraft = nextDraft;
          onDraftChange(nextDraft);
          setDraft(nextDraft);
        }}
        onRequestStep3={() => {
          onRequestStep3();
          setStep('step3');
        }}
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

  const pressFriend = async (name: string) => {
    const control = tree.root.findByProps({
      accessibilityLabel: `${name} 선택`,
    });
    await act(async () => control.props.onPress());
    return tree.root.findByProps({
      accessibilityLabel: `${name} 선택`,
    });
  };

  expect(
    tree.root.findAll(
      element =>
        element.props.accessibilityRole === 'checkbox' &&
        typeof element.props.onPress === 'function',
    ),
  ).toHaveLength(3);
  expect(
    tree.root
      .findAllByType(Text)
      .some(element => element.props.children === '친구 검색하기'),
  ).toBe(true);

  let minsu = await pressFriend('민수');
  expect(minsu.props.accessibilityState.checked).toBe(true);
  let jihun = await pressFriend('지훈');
  expect(jihun.props.accessibilityState.checked).toBe(true);
  minsu = await pressFriend('민수');
  expect(minsu.props.accessibilityState.checked).toBe(false);
  expect(latestDraft.invitedFriends).toEqual(['지훈']);

  await pressFriend('민수');
  expect(latestDraft.invitedFriends).toEqual(['지훈', '민수']);
  expect(latestDraft).toMatchObject({
    title: '저녁 약속',
    category: '식사',
    duration: '2시간',
    location: '서울',
  });

  await act(async () => findButton(tree, '이전').props.onPress());
  expect(textExists(tree, 'STEP 1: 저녁 약속 · 식사 · 2시간 · 서울')).toBe(true);
  await act(async () => findButton(tree, 'STEP 2로 돌아가기').props.onPress());

  minsu = tree.root.findByProps({ accessibilityLabel: '민수 선택' });
  jihun = tree.root.findByProps({ accessibilityLabel: '지훈 선택' });
  expect(minsu.props.accessibilityState.checked).toBe(true);
  expect(jihun.props.accessibilityState.checked).toBe(true);

  await act(async () => findButton(tree, '다음').props.onPress());
  expect(onRequestStep3).toHaveBeenCalledTimes(1);
  expect(textExists(tree, 'STEP 3: 지훈, 민수')).toBe(true);
  expect(
    textExists(tree, 'STEP 1 유지: 저녁 약속 · 식사 · 2시간 · 서울'),
  ).toBe(true);

  await act(async () => tree.unmount());
});

function ViewForTest({ children }: React.PropsWithChildren) {
  return <>{children}</>;
}

test('step three can be requested without selecting friends', async () => {
  const onRequestStep3 = jest.fn();
  let tree!: Renderer.ReactTestRenderer;
  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <CreateAppointmentStep2InviteScreen
          friends={[]}
          draft={{ title: '모임', category: '카페', duration: '1시간', location: '서울' }}
          onBack={jest.fn()}
          onDraftChange={jest.fn()}
          onRequestStep3={onRequestStep3}
        />
      </SafeAreaProvider>,
    );
  });
  await act(async () => findButton(tree, '다음').props.onPress());
  expect(onRequestStep3).toHaveBeenCalledTimes(1);
  await act(async () => tree.unmount());
});

test('friends with the same name are toggled and retained by stable IDs', async () => {
  const sameNamedFriends: PotatoFriend[] = [
    { id: 'person-a', name: '민수' },
    { id: 'person-b', name: '민수' },
  ];
  let latestDraft: AppointmentCreationDraft = {
    title: '동명이인 모임',
    category: '식사',
    duration: '90분',
    location: '서울',
  };
  let tree!: Renderer.ReactTestRenderer;

  const renderScreen = () => (
    <SafeAreaProvider>
      <CreateAppointmentStep2InviteScreen
        friends={sameNamedFriends}
        draft={latestDraft}
        onBack={jest.fn()}
        onDraftChange={draft => {
          latestDraft = draft;
        }}
        onRequestStep3={jest.fn()}
      />
    </SafeAreaProvider>
  );

  await act(async () => {
    tree = Renderer.create(renderScreen());
  });

  await act(async () =>
    tree.root
      .findByProps({ testID: 'friend-option-person-b' })
      .props.onPress(),
  );
  expect(latestDraft.invitedFriendIds).toEqual(['person-b']);
  expect(latestDraft.invitedFriendNameById).toEqual({ 'person-b': '민수' });
  expect(latestDraft.invitedFriends).toEqual(['민수']);
  expect(latestDraft.unresolvedInvitedFriendNames).toEqual([]);
  expect(latestDraft.participants).toEqual([
    {
      id: 'person-b',
      role: 'invitee',
      invitationStatus: 'not_sent',
      participationStatus: 'pending',
    },
  ]);
  expect(latestDraft.availabilitySubmissions).toEqual([
    { participantId: 'person-b', status: 'not_submitted' },
  ]);

  await act(async () => tree.update(renderScreen()));
  await act(async () =>
    tree.root
      .findByProps({ testID: 'friend-option-person-b' })
      .props.onPress(),
  );
  expect(latestDraft.invitedFriendIds).toEqual([]);
  expect(latestDraft.invitedFriends).toEqual([]);
  expect(latestDraft.participants).toEqual([]);
  expect(latestDraft.availabilitySubmissions).toEqual([]);

  await act(async () => tree.unmount());
});

test('legacy unique names are migrated to IDs before leaving step two', async () => {
  const legacyDraft: AppointmentCreationDraft = {
    title: '기존 모임',
    category: '식사',
    duration: '90분',
    location: '서울',
    invitedFriends: ['지훈'],
  };
  let latestDraft = legacyDraft;
  const onRequestStep3 = jest.fn();
  let tree!: Renderer.ReactTestRenderer;

  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <CreateAppointmentStep2InviteScreen
          friends={friends}
          draft={legacyDraft}
          onBack={jest.fn()}
          onDraftChange={draft => {
            latestDraft = draft;
          }}
          onRequestStep3={onRequestStep3}
        />
      </SafeAreaProvider>,
    );
  });

  expect(
    tree.root.findByProps({ testID: 'friend-option-friend-2' }).props
      .accessibilityState.checked,
  ).toBe(true);
  await act(async () => findButton(tree, '다음').props.onPress());

  expect(latestDraft.invitedFriendIds).toEqual(['friend-2']);
  expect(latestDraft.invitedFriendNameById).toEqual({ 'friend-2': '지훈' });
  expect(latestDraft.invitedFriends).toEqual(['지훈']);
  expect(onRequestStep3).toHaveBeenCalledTimes(1);
  await act(async () => tree.unmount());
});
