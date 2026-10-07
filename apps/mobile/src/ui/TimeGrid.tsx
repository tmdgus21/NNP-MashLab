import React, { useRef, useState } from 'react';
import { Text, View } from 'react-native';
import { GestureDetector, usePanGesture } from 'react-native-gesture-handler';
import { Interval } from '../domain/model';
import {
  intervalLabel,
  intervalsToSlots,
  paintSlots,
  slotsToIntervals,
  timeLabel,
} from '../domain/time';
import { Chip } from './components';
import { colors, ui } from './theme';

export function TimeGrid({
  dates,
  value,
  onChange,
  onDrawing,
  disabled,
}: {
  dates: string[];
  value: Interval[];
  onChange(value: Interval[]): void;
  onDrawing(active: boolean): void;
  disabled?: boolean;
}) {
  const [date, setDate] = useState(dates[0]);
  const [band, setBand] = useState(1);
  const [erase, setErase] = useState(false);
  const width = useRef(300);
  const stroke = useRef<{
    base: number[];
    start: number;
    erase: boolean;
  } | null>(null);
  const current = useRef({ value, date, band, erase, onChange });
  current.current = { value, date, band, erase, onChange };
  const selected = intervalsToSlots(value, date);
  const hit = (x: number, y: number) =>
    current.current.band * 12 +
    Math.min(3, Math.max(0, Math.floor(y / 48))) * 3 +
    Math.min(2, Math.max(0, Math.floor(x / (width.current / 3))));
  const publish = (slots: number[]) => {
    const c = current.current;
    c.onChange([
      ...c.value.filter(i => i.date !== c.date),
      ...slotsToIntervals(c.date, slots),
    ]);
  };
  const pan = usePanGesture({
    minDistance: 0,
    maxPointers: 1,
    enabled: !disabled,
    disableReanimated: true,
    onBegin: e => {
      const c = current.current;
      const start = hit(e.x, e.y);
      const base = intervalsToSlots(c.value, c.date);
      stroke.current = { base, start, erase: c.erase };
      onDrawing(true);
      publish(paintSlots(base, start, start, c.erase));
    },
    onUpdate: e => {
      const s = stroke.current;
      if (s) {
        publish(paintSlots(s.base, s.start, hit(e.x, e.y), s.erase));
      }
    },
    onFinalize: () => {
      stroke.current = null;
      onDrawing(false);
    },
  });
  return (
    <View style={{ gap: 12 }}>
      <View style={ui.wrap}>
        {dates.map(d => (
          <Chip
            key={d}
            title={d.slice(5).replace('-', '/')}
            selected={d === date}
            onPress={() => setDate(d)}
          />
        ))}
      </View>
      <View style={ui.wrap}>
        {['00–06', '06–12', '12–18', '18–24'].map((label, i) => (
          <Chip
            key={label}
            title={label}
            selected={band === i}
            onPress={() => setBand(i)}
          />
        ))}
      </View>
      <View style={ui.row}>
        <Chip
          title="＋ 칠하기"
          selected={!erase}
          onPress={() => setErase(false)}
        />
        <Chip
          title="− 지우기"
          selected={erase}
          onPress={() => setErase(true)}
        />
        <Text style={ui.small}>한 칸 30분</Text>
      </View>
      <GestureDetector gesture={pan}>
        <View
          testID="time-grid"
          collapsable={false}
          onLayout={e => {
            width.current = e.nativeEvent.layout.width;
          }}
          style={{
            flexDirection: 'row',
            flexWrap: 'wrap',
            borderRadius: 12,
            overflow: 'hidden',
            opacity: disabled ? 0.5 : 1,
          }}
        >
          {Array.from({ length: 12 }, (_, index) => {
            const slot = band * 12 + index;
            const active = selected.includes(slot);
            return (
              <View
                key={slot}
                accessible
                accessibilityRole="checkbox"
                accessibilityLabel={`${date} ${timeLabel(slot * 30)}부터 30분`}
                accessibilityState={{ checked: active, disabled: !!disabled }}
                accessibilityActions={[
                  { name: 'activate', label: '선택 변경' },
                ]}
                onAccessibilityAction={() => {
                  if (!disabled) {
                    publish(paintSlots(selected, slot, slot, active));
                  }
                }}
                style={{
                  width: '33.3333%',
                  height: 48,
                  borderWidth: 1,
                  borderColor: colors.white,
                  backgroundColor: active ? colors.primary : '#EAF0EE',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Text
                  style={{
                    color: active ? colors.white : colors.muted,
                    fontSize: 13,
                    fontWeight: '600',
                  }}
                >
                  {active ? '✓ ' : ''}
                  {timeLabel(slot * 30)}
                </Text>
              </View>
            );
          })}
        </View>
      </GestureDetector>
      <Text style={ui.muted}>
        손가락을 끌어 연속 시간을 선택하세요. 다른 구간도 이어서 추가할 수
        있어요.
      </Text>
      <Text
        accessibilityLiveRegion="polite"
        testID="selected-intervals"
        style={[ui.text, { color: colors.primary }]}
      >
        {value.length
          ? value.map(intervalLabel).join('\n')
          : '선택한 시간이 없어요'}
      </Text>
    </View>
  );
}
