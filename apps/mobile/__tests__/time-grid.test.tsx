import React, { useState } from 'react';
import { ScrollView } from 'react-native';
import Renderer, { act } from 'react-test-renderer';
import { TimeGrid } from '../src/ui/TimeGrid';
import { Chip } from '../src/ui/components';
import { Interval } from '../src/domain/model';
let mockPan: any;
jest.mock('react-native-gesture-handler', () => ({
  GestureDetector: ({ children }: any) => children,
  usePanGesture: (config: any) => {
    mockPan = config;
    return config;
  },
}));
const changed = jest.fn();
const drawing = jest.fn();
const other = { date: '2026-10-18', start: 600, end: 660 };
function Harness() {
  const [value, setValue] = useState<Interval[]>([other]);
  return (
    <TimeGrid
      dates={['2026-10-17', '2026-10-18']}
      value={value}
      onChange={next => {
        changed(next);
        setValue(next);
      }}
      onDrawing={drawing}
    />
  );
}
let tree: Renderer.ReactTestRenderer;
beforeEach(async () => {
  jest.useFakeTimers();
  jest.clearAllMocks();
  await act(async () => {
    tree = Renderer.create(<Harness />);
  });
});
afterEach(async () => {
  await act(async () => tree.unmount());
  jest.useRealTimers();
});
test('all 48 slots remain; ordinary scrolling never paints and long press crosses the old 06:00 boundary', async () => {
  expect(
    tree.root.findAllByType(Chip).some(c => c.props.title === '06–12'),
  ).toBe(false);
  expect(mockPan.activateAfterLongPress).toBe(300);
  await act(async () => mockPan.onUpdate({ x: 10, y: 144 }));
  expect(changed).not.toHaveBeenCalled();
  await act(async () => mockPan.onActivate({ x: 10, y: 144 }));
  await act(async () => mockPan.onUpdate({ x: 210, y: 240 }));
  await act(async () => mockPan.onFinalize());
  expect(changed).toHaveBeenLastCalledWith([
    other,
    { date: '2026-10-17', start: 270, end: 540 },
  ]);
  expect(drawing).toHaveBeenLastCalledWith(false);
  await act(async () =>
    tree.root
      .findAllByType(Chip)
      .find(c => c.props.title === '− 지우기')!
      .props.onPress(),
  );
  await act(async () => mockPan.onActivate({ x: 10, y: 144 }));
  await act(async () => mockPan.onUpdate({ x: 210, y: 240 }));
  await act(async () => mockPan.onFinalize());
  expect(changed).toHaveBeenLastCalledWith([other]);
});
test('edge auto-scroll reaches 24:00 and stops publishing after finger release', async () => {
  await act(async () =>
    tree.root
      .findByType(ScrollView)
      .props.onScroll({ nativeEvent: { contentOffset: { y: 0 } } }),
  );
  await act(async () => mockPan.onActivate({ x: 210, y: 300 }));
  await act(async () => {
    jest.advanceTimersByTime(4000);
  });
  expect(changed.mock.calls.at(-1)[0]).toEqual([
    other,
    { date: '2026-10-17', start: 600, end: 1440 },
  ]);
  await act(async () => mockPan.onFinalize());
  const count = changed.mock.calls.length;
  await act(async () => {
    jest.advanceTimersByTime(1000);
  });
  expect(changed).toHaveBeenCalledTimes(count);
});
