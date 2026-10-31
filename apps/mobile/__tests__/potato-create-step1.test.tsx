import React from 'react';
import { Pressable, Text, TextInput } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import Renderer, { act } from 'react-test-renderer';
import { CreateAppointmentStep1Screen } from '../src/potato/screens/CreateAppointmentStep1Screen';
import type { AppointmentCreationDraft } from '../src/potato/types/appointmentCreation';

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

test('step one preserves parent draft and validates before requesting step two', async () => {
  let draft: AppointmentCreationDraft = {};
  const onDraftChange = jest.fn((next: AppointmentCreationDraft) => {
    draft = next;
  });
  const onRequestStep2 = jest.fn();
  const onCancelClick = jest.fn();
  const onBackClick = jest.fn();
  let tree!: Renderer.ReactTestRenderer;

  const render = () => (
    <SafeAreaProvider>
      <CreateAppointmentStep1Screen
        draft={draft}
        onDraftChange={onDraftChange}
        onCancelClick={onCancelClick}
        onBackClick={onBackClick}
        onRequestStep2={onRequestStep2}
      />
    </SafeAreaProvider>
  );

  await act(async () => {
    tree = Renderer.create(render());
  });

  await act(async () => findButton(tree, '다음').props.onPress());
  expect(onRequestStep2).not.toHaveBeenCalled();
  expect(
    tree.root
      .findAllByType(Text)
      .some(
        text =>
          text.props.children ===
          '모임 이름, 활동, 예상 소요시간, 장소를 모두 입력해주세요.',
      ),
  ).toBe(true);

  const values = ['저녁 모임', '식사', '2시간', '서울'];
  for (const [index, value] of values.entries()) {
    const inputs = tree.root.findAllByType(TextInput);
    await act(async () => inputs[index].props.onChangeText(value));
    await act(async () => tree.update(render()));
  }

  expect(draft).toEqual({
    title: '저녁 모임',
    category: '식사',
    duration: '2시간',
    location: '서울',
  });
  expect(onDraftChange).toHaveBeenCalledTimes(4);

  await act(async () => findButton(tree, '다음').props.onPress());
  expect(onRequestStep2).toHaveBeenCalledWith({
    title: '저녁 모임',
    category: '식사',
    duration: '2시간',
    location: '서울',
  });

  await act(async () => findButton(tree, '취소').props.onPress());
  await act(async () => {
    tree.root.findByProps({ accessibilityLabel: '이전 화면' }).props.onPress();
  });
  expect(onCancelClick).toHaveBeenCalledTimes(1);
  expect(onBackClick).toHaveBeenCalledTimes(1);

  await act(async () => tree.unmount());
});
