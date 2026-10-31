import React from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import Renderer, { act } from 'react-test-renderer';
import { PotatoMeetDevPreview } from '../src/potato/PotatoMeetDevPreview';
import { findButton, hasText } from '../test-utils/potato-test-utils';

test('developer preview controls collapse without covering the current screen', async () => {
  let tree!: Renderer.ReactTestRenderer;

  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <PotatoMeetDevPreview />
      </SafeAreaProvider>,
    );
  });

  expect(hasText(tree, '로그인하기')).toBe(true);
  expect(
    tree.root.findAllByProps({ testID: 'dev-preview-route-login' }).length,
  ).toBeGreaterThan(0);

  await act(async () => findButton(tree, '도구 접기').props.onPress());

  expect(
    tree.root.findAllByProps({ testID: 'dev-preview-route-login' }),
  ).toHaveLength(0);
  expect(hasText(tree, '로그인하기')).toBe(true);
  expect(hasText(tree, '개발 프리뷰 · 로그인')).toBe(true);

  await act(async () => findButton(tree, '도구 열기').props.onPress());
  expect(
    tree.root.findAllByProps({ testID: 'dev-preview-route-login' }).length,
  ).toBeGreaterThan(0);

  await act(async () => tree.unmount());
});
