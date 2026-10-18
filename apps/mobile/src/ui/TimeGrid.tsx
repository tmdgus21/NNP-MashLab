import React, { useEffect, useRef, useState } from 'react';
import { ScrollView, Text, View } from 'react-native';
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
  tone = colors.primary,
  label = '가능',
}: {
  dates: string[];
  value: Interval[];
  onChange(value: Interval[]): void;
  onDrawing(active: boolean): void;
  disabled?: boolean;
  tone?: string;
  label?: string;
}) {
  const [date, setDate] = useState(dates[0]);
  const viewport = useRef<React.ComponentRef<typeof ScrollView>>(null);
  const offset = useRef(0);
  const pointer = useRef({ x: 0, y: 0 });
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const [drawing, setDrawing] = useState(false);
  const stop = () => {
    if (timer.current) {
      clearInterval(timer.current);
      timer.current = null;
    }
  };
  useEffect(
    () => () => {
      stop();
      onDrawing(false);
    },
    [onDrawing],
  );
  const [erase, setErase] = useState(false);
  const width = useRef(300);
  const stroke = useRef<{
    base: number[];
    start: number;
    last: number;
    erase: boolean;
  } | null>(null);
  const current = useRef({ value, date, erase, onChange });
  current.current = { value, date, erase, onChange };
  const selected = intervalsToSlots(value, date);
  const hit = (x: number, y: number) =>
    Math.min(15, Math.max(0, Math.floor((y + offset.current) / 48))) * 3 +
    Math.min(2, Math.max(0, Math.floor(x / (width.current / 3))));
  const publish = (slots: number[]) => {
    const c = current.current;
    c.onChange([
      ...c.value.filter(i => i.date !== c.date),
      ...slotsToIntervals(c.date, slots),
    ]);
  };
  const pan = usePanGesture({
    activateAfterLongPress: 300,
    maxPointers: 1,
    enabled: !disabled,
    disableReanimated: true,
    onActivate: e => {
      const c = current.current;
      const start = hit(e.x, e.y);
      const base = intervalsToSlots(c.value, c.date);
      stroke.current = { base, start, last: start, erase: c.erase };
      onDrawing(true);
      setDrawing(true);
      pointer.current = { x: e.x, y: e.y };
      stop();
      timer.current = setInterval(() => {
        const { x, y } = pointer.current;
        const delta = y < 40 ? -16 : y > 280 ? 16 : 0;
        if (!delta || !stroke.current) {
          return;
        }
        offset.current = Math.max(0, Math.min(448, offset.current + delta));
        viewport.current?.scrollTo({ y: offset.current, animated: false });
        const slot = hit(x, y);
        stroke.current.last = slot;
        publish(
          paintSlots(
            stroke.current.base,
            stroke.current.start,
            slot,
            stroke.current.erase,
          ),
        );
      }, 80);
      publish(paintSlots(base, start, start, c.erase));
    },
    onUpdate: e => {
      pointer.current = { x: e.x, y: e.y };
      const s = stroke.current;
      const slot = hit(e.x, e.y);
      if (s && s.last !== slot) {
        s.last = slot;
        publish(paintSlots(s.base, s.start, slot, s.erase));
      }
    },
    onFinalize: () => {
      stop();
      setDrawing(false);
      stroke.current = null;
      onDrawing(false);
    },
  });
  return (
    <View style={{ gap: 12 }}>
      {dates.length === 1 ? (
        <Text style={ui.small}>{date.replace(/-/g, '.')} · 한 칸 30분</Text>
      ) : (
        <View style={ui.wrap}>
          {dates.map(d => (
            <Chip
              key={d}
              title={d.slice(5).replace('-', '/')}
              selected={d === date}
              onPress={() => {
                setDate(d);
                offset.current = 0;
                viewport.current?.scrollTo({ y: 0, animated: false });
              }}
            />
          ))}
        </View>
      )}
      <View style={ui.wrap}>
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
      <Text style={ui.small}>
        밀어서 스크롤 · 길게 누른 뒤 끌어서 {erase ? '지우기' : '선택'} ·
        가장자리에서 자동 스크롤
      </Text>
      <GestureDetector gesture={pan}>
        <View collapsable={false} style={{ height: 320 }}>
          <ScrollView
            ref={viewport}
            nestedScrollEnabled
            scrollEnabled={!drawing}
            scrollEventThrottle={16}
            onScroll={e => {
              offset.current = e.nativeEvent.contentOffset.y;
            }}
          >
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
              {Array.from({ length: 48 }, (_, index) => {
                const slot = index;
                const active = selected.includes(slot);
                return (
                  <View
                    key={slot}
                    accessible
                    accessibilityRole="checkbox"
                    accessibilityLabel={`${label} · ${date} ${timeLabel(
                      slot * 30,
                    )}부터 30분`}
                    accessibilityState={{
                      checked: active,
                      disabled: !!disabled,
                    }}
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
                      backgroundColor: active ? tone : colors.bg,
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
          </ScrollView>
        </View>
      </GestureDetector>
      <View style={ui.summary}>
        <Text style={ui.small}>{label} · 선택한 시간</Text>
        <Text
          accessibilityLiveRegion="polite"
          testID="selected-intervals"
          style={[ui.text, { color: tone }]}
        >
          {value.length
            ? value.map(intervalLabel).join('\n')
            : '선택한 시간이 없어요'}
        </Text>
      </View>
    </View>
  );
}
