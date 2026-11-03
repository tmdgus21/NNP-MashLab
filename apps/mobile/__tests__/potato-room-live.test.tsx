/**
 * The REAL screens (JoinRoomScreen, RoomScreen) driven like a person, against a
 * RUNNING server + Worker. Skipped unless POTATO_LIVE_API_URL is set; never
 * runs against the production host.
 */
import React from 'react';
import { TextInput } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import Renderer, { act } from 'react-test-renderer';
import { JoinRoomScreen } from '../src/potato/screens/JoinRoomScreen';
import { RoomScreen } from '../src/potato/screens/RoomScreen';
import { createPotatoApi, newRequestKey, type PotatoApi } from '../src/potato/services/potatoApi';
import { findButton, hasText } from '../test-utils/potato-test-utils';

const baseUrl = (
  globalThis as { process?: { env?: Record<string, string | undefined> } }
).process?.env?.POTATO_LIVE_API_URL;
const live = baseUrl ? describe : describe.skip;
if (baseUrl && /oranganman/i.test(baseUrl)) {
  throw new Error('Refusing to run against production.');
}

const seoulDate = (offset: number) =>
  new Date(Date.now() + 9 * 3600 * 1000 + offset * 86400 * 1000).toISOString().slice(0, 10);

interface Player {
  api: PotatoApi;
  nickname: string;
}

async function makePlayer(name: string, nickname: string): Promise<Player> {
  let token: string | null = null;
  const api = createPotatoApi({
    baseUrl: baseUrl ?? 'http://skipped.invalid',
    token: async () => token,
    fetcher: (globalThis as { fetch: typeof fetch }).fetch,
  });
  const email = `${name}-${Date.now().toString(36)}@example.test`;
  await api.auth.register(email, 'screen-pass-123456');
  token = (await api.auth.login(email, 'screen-pass-123456')).token;
  return { api, nickname };
}

async function until(check: () => boolean, label: string, ms = 20000): Promise<void> {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    if (check()) {
      return;
    }
    await act(async () => {
      await new Promise<void>(resolve => setTimeout(resolve, 150));
    });
  }
  throw new Error(`timed out waiting for: ${label}`);
}

const mounted: Renderer.ReactTestRenderer[] = [];

afterEach(async () => {
  // RoomScreen polls on a timer; leaving trees mounted would keep the process alive.
  await act(async () => {
    while (mounted.length > 0) {
      mounted.pop()!.unmount();
    }
  });
});

async function mount(element: React.ReactElement) {
  let tree!: Renderer.ReactTestRenderer;
  await act(async () => {
    tree = Renderer.create(<SafeAreaProvider>{element}</SafeAreaProvider>);
  });
  mounted.push(tree);
  return tree;
}

async function press(tree: Renderer.ReactTestRenderer, label: string) {
  await act(async () => {
    findButton(tree, label).props.onPress();
  });
}

live('Potato screens against a live server', () => {
  test('three phones join with the code, then the room screens carry the whole decision', async () => {
    const host = await makePlayer('host', '방장');
    const guests = [await makePlayer('g1', '민수'), await makePlayer('g2', '지훈'), await makePlayer('g3', '영희')];
    const day = seoulDate(3);
    const room = await host.api.rooms.create(
      {
        title: '화면 통합 테스트', activity: '식사', location: '강남역', durationMinutes: 60,
        dates: [day], minimumAttendeeCount: 2, nickname: host.nickname,
      },
      newRequestKey('screen'),
    );

    // each guest types the code on the real Join screen
    for (const guest of guests) {
      const onJoined = jest.fn();
      const tree = await mount(
        <JoinRoomScreen api={guest.api} defaultNickname={guest.nickname} onBack={jest.fn()} onJoined={onJoined} />,
      );
      const input = tree.root.findAllByType(TextInput).find(i => i.props.accessibilityLabel === '초대 코드 입력')!;
      await act(async () => input.props.onChangeText(room.code.toLowerCase()));
      await press(tree, '참가하기');
      await until(() => onJoined.mock.calls.length > 0, `${guest.nickname} joined`);
      expect(onJoined.mock.calls[0][0].me.role).toBe('invitee');
    }
    const wrong = await mount(
      <JoinRoomScreen api={guests[0].api} defaultNickname="x" onBack={jest.fn()} onJoined={jest.fn()} />,
    );
    const wrongInput = wrong.root.findAllByType(TextInput).find(i => i.props.accessibilityLabel === '초대 코드 입력')!;
    await act(async () => wrongInput.props.onChangeText('ZZZZZZZZ'));
    await press(wrong, '참가하기');
    await until(() => hasText(wrong, '초대 코드를 다시 확인해 주세요.'), 'unknown code message');

    for (const [index, player] of [host, ...guests].entries()) {
      await player.api.availability.put(room.roomId, [
        { date: day, startTimeMinutes: 540 + index * 30, endTimeMinutes: 900 },
      ]);
    }

    const open = (player: Player) =>
      mount(<RoomScreen api={player.api} roomId={room.roomId} pollMs={250} onBack={jest.fn()} onEditAvailability={jest.fn()} onLeft={jest.fn()} />);
    const hostTree = await open(host);
    const guestTrees: Renderer.ReactTestRenderer[] = [];
    for (const guest of guests) {
      guestTrees.push(await open(guest)); // sequential: act() calls must not overlap
    }

    await until(() => hasText(hostTree, '참여자 (4명)'), 'host sees 4 participants');
    await until(() => hasText(hostTree, '일정 계산하기'), 'compute button');
    expect(hasText(guestTrees[0], '일정 계산하기')).toBe(false); // only the host computes
    await press(hostTree, '일정 계산하기');
    await until(() => hasText(hostTree, '계산이 끝났어요. 후보를 확인해 주세요.'), 'Worker finished');
    await until(() => hasText(guestTrees[2], '추천 후보'), 'a guest phone follows the same run');

    await press(hostTree, '이 시간으로 정하기');
    for (const tree of [hostTree, ...guestTrees]) {
      await until(() => hasText(tree, '참석 동의'), 'consent section');
    }
    for (const tree of [hostTree, ...guestTrees]) {
      await until(() => hasText(tree, '동의하기'), 'agree button');
      await press(tree, '동의하기');
    }
    await until(() => hasText(hostTree, '승인하기'), 'host can approve once all agreed');
    await press(hostTree, '승인하기');
    await until(() => hasText(hostTree, '최종 확정하기'), 'finalize button');
    await press(hostTree, '최종 확정하기');

    for (const tree of [hostTree, ...guestTrees]) {
      await until(() => hasText(tree, '✅ 모임이 확정됐어요'), 'final banner on every phone');
    }
    const finalResult = await host.api.decision.finalResult(room.roomId);
    expect(finalResult.finalized).toBe(true);
  }, 90000);
});
