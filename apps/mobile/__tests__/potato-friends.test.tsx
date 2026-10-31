import React from 'react';
import { TextInput } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import Renderer, { act } from 'react-test-renderer';
import { FriendsScreen } from '../src/potato/screens/FriendsScreen';
import { findButton, hasText } from '../test-utils/potato-test-utils';

test('friend list supports local add, selection, deletion and empty state', async () => {
  const onSelectionChange = jest.fn();
  let tree!: Renderer.ReactTestRenderer;

  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <FriendsScreen
          initialFriends={[]}
          onSelectionChange={onSelectionChange}
        />
      </SafeAreaProvider>,
    );
  });
  expect(hasText(tree, '등록된 친구가 없습니다.')).toBe(true);

  await act(async () => {
    tree.root.findByType(TextInput).props.onChangeText('새 친구');
  });
  await act(async () => {
    findButton(tree, '추가').props.onPress();
  });
  expect(hasText(tree, '새 친구')).toBe(true);
  expect(hasText(tree, '등록된 친구가 없습니다.')).toBe(false);

  const friendCheckbox = tree.root.findAll(
    element =>
      element.props.accessibilityRole === 'checkbox' &&
      typeof element.props.onPress === 'function',
  )[0];
  await act(async () => friendCheckbox.props.onPress());
  expect(friendCheckbox.props.accessibilityState.checked).toBe(true);
  expect(onSelectionChange).toHaveBeenLastCalledWith([
    { id: 'local-1', name: '새 친구' },
  ]);

  await act(async () => {
    tree.root.findByProps({ accessibilityLabel: '새 친구 삭제' }).props.onPress();
  });
  expect(hasText(tree, '등록된 친구가 없습니다.')).toBe(true);
  expect(onSelectionChange).toHaveBeenLastCalledWith([]);

  await act(async () => tree.unmount());
});
