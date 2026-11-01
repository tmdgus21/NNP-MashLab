import React from 'react';
import { Alert, Text } from 'react-native';
import Renderer, { act } from 'react-test-renderer';
import { MeetingActions } from '../src/ui/MeetingActions';
import { Button } from '../src/ui/components';
import { fixture } from '../src/data/fixtures';
jest.mock('../src/state/store', () => ({ useApp: () => mockState }));
jest.mock('../src/ui/InvitationSheet', () => ({ InvitationSheet: () => null }));
const mockState = {
  meeting: fixture('feasible'),
  actorId: 'p1',
  busy: null,
  leave: jest.fn(),
  deleteMeeting: jest.fn(),
};
let tree: Renderer.ReactTestRenderer;
afterEach(async () => {
  await act(async () => tree.unmount());
  jest.restoreAllMocks();
  jest.clearAllMocks();
});
test('code is immediately visible and only host can confirm deletion', async () => {
  mockState.actorId = mockState.meeting.hostId;
  const alert = jest.spyOn(Alert, 'alert').mockImplementation(() => {});
  await act(async () => {
    tree = Renderer.create(<MeetingActions />);
  });
  expect(
    tree.root
      .findAllByType(Text)
      .some(t => t.props.children === mockState.meeting.roomCode),
  ).toBe(true);
  const buttons = tree.root.findAllByType(Button);
  await act(async () =>
    buttons
      .find(b => b.props.title === '새 모임 만들기 / 내 모임 목록')!
      .props.onPress(),
  );
  expect(mockState.leave).toHaveBeenCalledTimes(1);
  await act(async () =>
    buttons.find(b => b.props.title === '모임 삭제')!.props.onPress(),
  );
  expect(mockState.deleteMeeting).not.toHaveBeenCalled();
  const actions = alert.mock.calls[0][2]!;
  expect(actions.find(a => a.text === '취소')?.style).toBe('cancel');
  await act(async () => actions.find(a => a.text === '모임 삭제')!.onPress!());
  expect(mockState.deleteMeeting).toHaveBeenCalledTimes(1);
});
test('participant never sees a delete control', async () => {
  mockState.actorId = 'p2';
  await act(async () => {
    tree = Renderer.create(<MeetingActions />);
  });
  expect(
    tree.root.findAllByType(Button).some(b => b.props.title === '모임 삭제'),
  ).toBe(false);
});
