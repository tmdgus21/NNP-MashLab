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

test('developer preview exposes AI recommendation fixtures as non-production examples', async () => {
  let tree!: Renderer.ReactTestRenderer;

  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <PotatoMeetDevPreview />
      </SafeAreaProvider>,
    );
  });

  await act(async () => findButton(tree, 'AI 추천').props.onPress());
  expect(
    hasText(
      tree,
      '개발 프리뷰 · 예시 화면 데이터이며 실제 추천 결과가 아닙니다.',
    ),
  ).toBe(true);
  expect(hasText(tree, '참여자 응답 상태를 확인해주세요')).toBe(true);

  await act(async () => findButton(tree, '전원 참석 추천').props.onPress());
  expect(hasText(tree, '전원 참석 추천')).toBe(true);
  expect(hasText(tree, '전원 참석')).toBe(true);
  expect(hasText(tree, '일정 검증 완료')).toBe(true);

  await act(async () => tree.unmount());
});

test('STEP 4 passes its actual preparation result into the AI screen without fabricating a result', async () => {
  let tree!: Renderer.ReactTestRenderer;

  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <PotatoMeetDevPreview />
      </SafeAreaProvider>,
    );
  });

  await act(async () => findButton(tree, '생성 4').props.onPress());
  await act(async () => findButton(tree, 'AI 조율').props.onPress());

  expect(hasText(tree, 'AI 일정 조율')).toBe(true);
  expect(hasText(tree, '추가 정보가 필요')).toBe(false);
  expect(
    hasText(
      tree,
      '개발 프리뷰 · 예시 화면 데이터이며 실제 추천 결과가 아닙니다.',
    ),
  ).toBe(false);
  expect(
    hasText(tree, 'AI 서버 미연결 · 추천 요청은 아직 전송되지 않습니다.'),
  ).toBe(true);
  expect(
    hasText(
      tree,
      '검증 상태와 입력 버전을 확인할 수 있는 추천 후보가 없습니다.',
    ),
  ).toBe(false);

  await act(async () => tree.unmount());
});
