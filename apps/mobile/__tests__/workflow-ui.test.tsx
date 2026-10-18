import React from 'react';
import { Alert } from 'react-native';
import Renderer, { act } from 'react-test-renderer';
import { ConditionsScreen } from '../src/screens/ConditionsScreen';
import { ScheduleScreen } from '../src/screens/ScheduleScreen';
import { Button, Field } from '../src/ui/components';
import { fixture } from '../src/data/fixtures';

jest.mock('../src/state/store', () => ({ useApp: () => mockState }));
jest.mock('../src/data/repositoryInstance', () => ({
  repository: { mode: 'http' },
}));
jest.mock('../src/ui/TimeGrid', () => ({ TimeGrid: () => null }));
const mockState = {
  meeting: fixture('finalized'),
  actorId: 'p1',
  busy: null,
  preview: jest.fn(),
  apply: jest.fn(),
  consent: jest.fn(),
  calculate: jest.fn(),
  refresh: jest.fn(),
  finalize: jest.fn(),
};
let tree: Renderer.ReactTestRenderer;
beforeEach(() => {
  jest.clearAllMocks();
  mockState.meeting = fixture('finalized');
  mockState.meeting.status = 'reviewing';
  mockState.actorId = 'p1';
});
afterEach(async () => {
  if (tree) {
    await act(async () => tree.unmount());
  }
});
const press = async (title: string) => {
  const button = tree.root
    .findAllByType(Button)
    .find(b => b.props.title === title)!;
  expect(button).toBeDefined();
  expect(button.props.disabled).not.toBe(true);
  await act(async () => button.props.onPress());
};
test('step navigation preserves edits; preview does not submit and changing an input invalidates preview', async () => {
  const m = mockState.meeting;
  mockState.preview.mockResolvedValue({
    revision: m.revision,
    before: m.plan,
    after: m.plan,
    changes: [],
  });
  await act(async () => {
    tree = Renderer.create(<ConditionsScreen />);
  });
  await press('역할로 다음');
  await press('추가조건으로 다음');
  const note = () =>
    tree.root
      .findAllByType(Field)
      .find(f => f.props.label === '추가 확인 메모')!;
  await act(async () => note().props.onChangeText('메모 유지 확인'));
  await press('이전');
  await press('추가조건으로 다음');
  expect(note().props.value).toBe('메모 유지 확인');
  await press('검토로 다음');
  await press('조건 미리보기');
  expect(mockState.preview).toHaveBeenCalledWith(
    expect.objectContaining({ note: '메모 유지 확인' }),
  );
  expect(mockState.apply).not.toHaveBeenCalled();
  expect(
    tree.root
      .findAllByType(Button)
      .some(b => b.props.testID === 'submit-conditions'),
  ).toBe(true);
  await press('이전');
  await act(async () => note().props.onChangeText('변경된 메모'));
  await press('검토로 다음');
  expect(
    tree.root
      .findAllByType(Button)
      .some(b => b.props.testID === 'preview-change'),
  ).toBe(true);
});
test('host finalization needs an explicit confirmation even after everyone agrees', async () => {
  const dialog = jest.spyOn(Alert, 'alert').mockImplementation(() => {});
  await act(async () => {
    tree = Renderer.create(<ScheduleScreen />);
  });
  await press('전원 동의 · 최종 확정');
  expect(mockState.finalize).not.toHaveBeenCalled();
  const buttons = dialog.mock.calls[0][2]!;
  await act(async () => buttons.find(b => b.text === '최종 확정')!.onPress!());
  expect(mockState.finalize).toHaveBeenCalledTimes(1);
  dialog.mockRestore();
});
test('a participant cannot see host finalization, and an old round agreement still requires consent', async () => {
  mockState.actorId = 'p2';
  mockState.meeting.participants[1].consentRound -= 1;
  await act(async () => {
    tree = Renderer.create(<ScheduleScreen />);
  });
  expect(
    tree.root
      .findAllByType(Button)
      .some(b => b.props.title.includes('최종 확정')),
  ).toBe(false);
  await press('이번 담당표에 동의');
  expect(mockState.consent).toHaveBeenCalledWith('agreed');
});
