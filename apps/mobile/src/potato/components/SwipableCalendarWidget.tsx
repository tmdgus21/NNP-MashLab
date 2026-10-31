import React, { useCallback, useMemo } from 'react';
import {
  PanResponder,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { potatoColors } from '../theme/colors';

interface SwipableCalendarWidgetProps {
  year: number;
  month: number;
  selectedDay: number;
  markedDates: ReadonlySet<string>;
  compact?: boolean;
  dayCellHeight?: number;
  onMonthChange: (year: number, month: number) => void;
  onDayChange: (year: number, month: number, day: number) => void;
}

const weekdays = ['일', '월', '화', '수', '목', '금', '토'];

function monthDate(year: number, month: number): Date {
  return new Date(year, month - 1, 1);
}

function monthKey(year: number, month: number, day: number): string {
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

export function SwipableCalendarWidget({
  year,
  month,
  selectedDay,
  markedDates,
  compact = false,
  dayCellHeight,
  onMonthChange,
  onDayChange,
}: SwipableCalendarWidgetProps) {
  const firstWeekday = monthDate(year, month).getDay();
  const daysInMonth = new Date(year, month, 0).getDate();
  const daysInPreviousMonth = new Date(year, month - 1, 0).getDate();
  const cells = useMemo(
    () =>
      Array.from({ length: 42 }, (_, index) => {
        const dayOffset = index - firstWeekday + 1;
        if (dayOffset < 1) {
          return {
            day: daysInPreviousMonth + dayOffset,
            monthOffset: -1 as const,
          };
        }
        if (dayOffset > daysInMonth) {
          return {
            day: dayOffset - daysInMonth,
            monthOffset: 1 as const,
          };
        }
        return { day: dayOffset, monthOffset: 0 as const };
      }),
    [daysInMonth, daysInPreviousMonth, firstWeekday],
  );

  const shiftMonth = useCallback((amount: number) => {
    const next = new Date(year, month - 1 + amount, 1);
    onMonthChange(next.getFullYear(), next.getMonth() + 1);
  }, [month, onMonthChange, year]);

  const panResponder = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_event, gesture) =>
          Math.abs(gesture.dx) > 24 &&
          Math.abs(gesture.dx) > Math.abs(gesture.dy) * 1.2,
        onPanResponderRelease: (_event, gesture) => {
          if (gesture.dx < -40) {
            shiftMonth(1);
          } else if (gesture.dx > 40) {
            shiftMonth(-1);
          }
        },
      }),
    [shiftMonth],
  );

  return (
    <View style={[styles.container, compact && styles.compactContainer]}>
      <View style={styles.monthHeader}>
        <Pressable
          accessibilityLabel="이전 달"
          accessibilityRole="button"
          hitSlop={8}
          onPress={() => shiftMonth(-1)}
          style={styles.monthArrow}
        >
          <Text style={styles.monthArrowText}>〈</Text>
        </Pressable>
        <Text style={styles.monthTitle}>
          {year}년 {month}월
        </Text>
        <Pressable
          accessibilityLabel="다음 달"
          accessibilityRole="button"
          hitSlop={8}
          onPress={() => shiftMonth(1)}
          style={styles.monthArrow}
        >
          <Text style={styles.monthArrowText}>〉</Text>
        </Pressable>
      </View>
      <View
        style={[
          styles.weekdayRow,
          compact && styles.compactWeekdayRow,
        ]}
      >
        {weekdays.map((weekday, index) => (
          <Text
            key={weekday}
            style={[
              styles.weekday,
              index === 0 && styles.sunday,
            ]}
          >
            {weekday}
          </Text>
        ))}
      </View>
      <View style={styles.grid} {...panResponder.panHandlers}>
        {cells.map((cell, index) => {
          const date = new Date(year, month - 1 + cell.monthOffset, cell.day);
          const cellYear = date.getFullYear();
          const cellMonth = date.getMonth() + 1;
          const key = monthKey(cellYear, cellMonth, cell.day);
          const marked = markedDates.has(key);
          const selected =
            cell.monthOffset === 0 && cell.day === selectedDay;

          return (
            <Pressable
              accessibilityLabel={`${cellYear}년 ${cellMonth}월 ${cell.day}일`}
              accessibilityRole="button"
              accessibilityState={{ selected }}
              key={index}
              onPress={() => onDayChange(cellYear, cellMonth, cell.day)}
              style={[
                styles.dayCell,
                dayCellHeight !== undefined && {
                  height: dayCellHeight,
                  aspectRatio: undefined,
                },
              ]}
            >
              <View
                style={[
                  styles.dayContent,
                  selected && styles.selectedDay,
                  marked && !selected && styles.markedDay,
                ]}
              >
                {marked && <View style={styles.markDot} />}
                <Text
                  style={[
                    styles.dayNumber,
                    cell.monthOffset !== 0 && styles.otherMonthDay,
                    marked && styles.boldDay,
                    selected && styles.boldDay,
                  ]}
                >
                  {cell.day}
                </Text>
              </View>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 12,
    borderWidth: 1,
    borderColor: '#FFE082',
    borderRadius: 12,
    backgroundColor: '#FFFDF9',
  },
  compactContainer: {
    padding: 8,
  },
  monthHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  monthArrow: {
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  monthArrowText: {
    color: potatoColors.brown,
    fontSize: 18,
    fontWeight: '700',
  },
  monthTitle: {
    color: potatoColors.brown,
    fontSize: 16,
    fontWeight: '700',
  },
  weekdayRow: {
    flexDirection: 'row',
    marginTop: 10,
    marginBottom: 8,
  },
  weekday: {
    flex: 1,
    color: '#666666',
    fontSize: 13,
    fontWeight: '700',
    textAlign: 'center',
  },
  compactWeekdayRow: {
    marginTop: 6,
    marginBottom: 4,
  },
  sunday: {
    color: '#D32F2F',
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  dayCell: {
    width: `${100 / 7}%`,
    aspectRatio: 1,
    padding: 2,
  },
  dayContent: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 0,
    borderColor: potatoColors.accentLight,
    borderRadius: 12,
  },
  selectedDay: {
    backgroundColor: potatoColors.accentLight,
  },
  markedDay: {
    borderWidth: 2,
  },
  markDot: {
    position: 'absolute',
    top: 3,
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: '#E53935',
  },
  dayNumber: {
    color: '#000000',
    fontSize: 13,
  },
  boldDay: {
    fontWeight: '700',
  },
  otherMonthDay: {
    color: '#BBBBBB',
  },
});
