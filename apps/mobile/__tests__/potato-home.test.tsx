import React from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import Renderer, { act } from 'react-test-renderer';
import { HomeScreen } from '../src/potato/screens/HomeScreen';
import type { PotatoAppointment } from '../src/potato/types/appointment';
import { findButton, hasText } from '../test-utils/potato-test-utils';

function localDateKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function appointment(id: string, title: string, date: string): PotatoAppointment {
  return {
    id,
    title,
    category: '식사',
    duration: '2시간',
    location: '서울',
    timeInfo: `${date} 12:00`,
    date,
    invitedFriends: [],
  };
}

test('calendar selection filters local appointments and exposes navigation callbacks', async () => {
  const today = new Date();
  const tomorrow = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1);
  const todayKey = localDateKey(today);
  const tomorrowKey = localDateKey(tomorrow);
  const onCreate = jest.fn();
  const onTabSelected = jest.fn();
  let tree!: Renderer.ReactTestRenderer;

  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <HomeScreen
          initialAppointments={[
            appointment('today', '오늘 모임', todayKey),
            appointment('tomorrow', '내일 모임', tomorrowKey),
          ]}
          onCreateAppointmentPress={onCreate}
          onTabSelected={onTabSelected}
        />
      </SafeAreaProvider>,
    );
  });

  expect(hasText(tree, '오늘 모임')).toBe(true);
  expect(hasText(tree, '내일 모임')).toBe(false);

  const tomorrowButton = tree.root.findByProps({
    accessibilityLabel: `${tomorrow.getFullYear()}년 ${tomorrow.getMonth() + 1}월 ${tomorrow.getDate()}일`,
  });
  await act(async () => tomorrowButton.props.onPress());

  expect(hasText(tree, '오늘 모임')).toBe(false);
  expect(hasText(tree, '내일 모임')).toBe(true);

  await act(async () => {
    tree.root.findByProps({ accessibilityLabel: '다음 달' }).props.onPress();
  });
  const followingMonth = new Date(
    tomorrow.getFullYear(),
    tomorrow.getMonth() + 1,
    1,
  );
  expect(
    hasText(
      tree,
      `${followingMonth.getFullYear()}년 ${followingMonth.getMonth() + 1}월`,
    ),
  ).toBe(true);

  await act(async () => {
    findButton(tree, '+ 모임 만들기').props.onPress();
    findButton(tree, '모임만들기').props.onPress();
  });
  expect(onCreate).toHaveBeenCalledTimes(1);
  expect(onTabSelected).toHaveBeenCalledWith('create_step1');

  await act(async () => tree.unmount());
});
