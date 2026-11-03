import React from 'react';
import { Text } from 'react-native';
import Renderer, { act } from 'react-test-renderer';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { PotatoApp } from '../src/potato/PotatoApp';
import { createPotatoRuntime } from '../src/potato/services/potatoRuntime';
import { memorySessionStore } from '../src/potato/services/potatoSession';
import { hasText, textContent } from '../test-utils/potato-test-utils';

// Only the network is replaced (with the server's documented response shapes).
// PotatoApp, the API client, the session store and the screens are the real code.
function serverStub(handlers: Record<string, () => Response>) {
  const calls: string[] = [];
  const fetcher = (async (url: string, init: { method?: string }) => {
    const key = `${init.method ?? 'GET'} ${new URL(url).pathname}`;
    calls.push(key);
    const handler = handlers[key];
    return handler ? handler() : new Response(JSON.stringify({ detail: 'unexpected' }), { status: 500 });
  }) as unknown as typeof fetch;
  return { fetcher, calls };
}

const json = (body: unknown, status = 200) => () => new Response(JSON.stringify(body), { status });

const session = {
  token: 't'.repeat(48),
  accountId: 'acc-1',
  email: 'host@example.test',
  nickname: '방장',
};

const roomSummary = {
  roomId: 'room-1', code: 'AB23CD45', title: '금요 저녁', activity: '식사', location: '강남역',
  durationMinutes: 60, dates: ['2030-01-10'], role: 'organizer', myNickname: '방장',
  eligibleParticipantCount: 2, coordinationRound: 0, finalized: false,
  finalStartsAt: null, finalEndsAt: null,
};

async function mount(runtime: ReturnType<typeof createPotatoRuntime>) {
  let tree!: Renderer.ReactTestRenderer;
  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <PotatoApp runtime={runtime} listenForLinks={false} />
      </SafeAreaProvider>,
    );
  });
  await act(async () => {
    await new Promise<void>(resolve => setTimeout(resolve, 20));
  });
  return tree;
}

function texts(tree: Renderer.ReactTestRenderer) {
  return tree.root.findAllByType(Text).map(item => textContent(item.props.children));
}

test('without a stored session the app shows the real login and no preview data', async () => {
  const stub = serverStub({});
  const runtime = createPotatoRuntime({ baseUrl: 'http://server.test', sessions: memorySessionStore(), fetcher: stub.fetcher });
  const tree = await mount(runtime);
  expect(hasText(tree, '로그인하기')).toBe(true);
  expect(hasText(tree, '인증코드 보내기')).toBe(false); // the server has no email verification
  expect(stub.calls).toEqual([]); // nothing was fetched without a login
  expect(texts(tree).some(text => text.includes('개발 프리뷰'))).toBe(false);
});

test('with a stored session the home screen lists the server rooms, unconfirmed ones as coordinating', async () => {
  const sessions = memorySessionStore();
  await sessions.save(session);
  const stub = serverStub({ 'GET /v2/rooms': json({ rooms: [roomSummary] }) });
  const runtime = createPotatoRuntime({ baseUrl: 'http://server.test', sessions, fetcher: stub.fetcher });
  const tree = await mount(runtime);
  expect(stub.calls).toContain('GET /v2/rooms');
  expect(hasText(tree, '조율 중')).toBe(true);
  expect(hasText(tree, '확정')).toBe(false); // nothing is confirmed, so nothing says so
  expect(hasText(tree, '초대 코드로 참가')).toBe(true);
});

test('an expired session on the home screen signs the user out instead of showing stale data', async () => {
  const sessions = memorySessionStore();
  await sessions.save(session);
  const stub = serverStub({
    'GET /v2/rooms': json({ detail: '로그인이 필요합니다.' }, 401),
    'POST /v1/auth/logout': json({ ok: true }),
  });
  const runtime = createPotatoRuntime({ baseUrl: 'http://server.test', sessions, fetcher: stub.fetcher });
  const tree = await mount(runtime);
  await act(async () => {
    await new Promise<void>(resolve => setTimeout(resolve, 20));
  });
  expect(hasText(tree, '로그인하기')).toBe(true);
  expect(await sessions.load()).toBeNull();
});
