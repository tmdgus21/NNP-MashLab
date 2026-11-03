import React from 'react';
import { Share } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import Renderer, { act } from 'react-test-renderer';
import { RoomScreen } from '../src/potato/screens/RoomScreen';
import type { PotatoApi } from '../src/potato/services/potatoApi';
import { findButton, hasText } from '../test-utils/potato-test-utils';

// A host who just created a room: alone, nothing computed. Only the API object is a
// stand-in (server-shaped data); RoomScreen and its state loader are the real code.
const api = {
  rooms: {
    get: async () => ({
      roomId: 'r1', code: 'AB23CD45', title: '금요 저녁', activity: '식사', location: '강남역',
      durationMinutes: 60, dates: ['2030-01-10'], minimumAttendeeCount: 2, hostMemberId: 'm1',
      status: 'collecting', coordinationRound: 0, agentInputRevision: 2, eligibleParticipantCount: 1,
      me: { memberId: 'm1', accountId: 'a1', role: 'organizer' },
    }),
    participants: async () => ({
      roomId: 'r1', eligibleParticipantCount: 1,
      participants: [{
        participantId: 'a1', memberId: 'm1', displayName: '방장', role: 'organizer',
        invitationStatus: 'not_applicable', participationStatus: 'accepted', eligibility: 'active',
        joinPath: 'organizer', availability: { status: 'submitted', version: 1, updatedAt: null },
      }],
    }),
  },
  availability: { get: async () => ({ status: 'submitted', version: 1, timeSlots: [] }) },
  runs: { latest: async () => ({ roomId: 'r1', currentInputRevision: 2, run: null }) },
  decision: { finalResult: async () => ({ finalized: false, coordinationRound: 0 }) },
} as unknown as PotatoApi;

test('right after creating a room the host sees the code, an invitation hint, and shares code-only text', async () => {
  const share = jest.spyOn(Share, 'share').mockResolvedValue({ action: 'sharedAction', activityType: undefined });
  let tree!: Renderer.ReactTestRenderer;
  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <RoomScreen api={api} roomId="r1" pollMs={0} onBack={jest.fn()} onEditAvailability={jest.fn()} onLeft={jest.fn()} />
      </SafeAreaProvider>,
    );
  });
  await act(async () => {
    await new Promise<void>(resolve => setTimeout(resolve, 20));
  });
  expect(hasText(tree, 'AB23CD45')).toBe(true);
  expect(hasText(tree, '아직 아무도 참여하지 않았어요. 코드를 공유해 친구를 초대해 주세요. 친구가 코드로 참가하면 이곳에 나타나요.')).toBe(true);
  await act(async () => {
    findButton(tree, '코드 공유').props.onPress();
  });
  const message = (share.mock.calls[0][0] as { message: string }).message;
  expect(message).toContain('AB23CD45');
  expect(message).toContain('Potato Meet');
  expect(message).not.toMatch(/https?:\/\//); // the web /join page is v1-only: never share a link
  expect(message).not.toContain('조건부');
  share.mockRestore();
  await act(async () => tree.unmount());
});
