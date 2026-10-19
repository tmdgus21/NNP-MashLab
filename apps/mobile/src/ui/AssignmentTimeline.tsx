import React, { useState } from 'react';
import { ScrollView, Text, View, useWindowDimensions } from 'react-native';
import { Meeting } from '../domain/model';
import { timeLabel } from '../domain/time';
import { Chip } from './components';
import { colors, ui } from './theme';

/** Presentation only: bars come exclusively from the current server proposal. */
export function AssignmentTimeline({ meeting: m }: { meeting: Meeting }) {
  const [date, setDate] = useState(
    m.plan.assignments[0]?.interval.date ?? m.dates[0],
  );
  const { fontScale } = useWindowDimensions();
  const assignments = m.plan.assignments.filter(a => a.interval.date === date);
  const start = Math.min(
    m.windowStart,
    ...assignments.map(a => a.interval.start),
  );
  const end = Math.max(m.windowEnd, ...assignments.map(a => a.interval.end));
  const width = Math.max(320, ((end - start) / 30) * 48);
  const rowHeight = Math.max(60, 48 * fontScale);
  const x = (minute: number) =>
    ((minute - start) / Math.max(30, end - start)) * width;
  return (
    <View style={ui.section}>
      <Text style={ui.heading}>참가자별 배정 시간</Text>
      <View style={ui.wrap}>
        {m.dates.map(d => (
          <Chip
            key={d}
            title={d.slice(5)}
            selected={d === date}
            onPress={() => setDate(d)}
          />
        ))}
      </View>
      {!assignments.length ? (
        <Text style={ui.muted}>이 날짜에 배정된 역할이 없어요.</Text>
      ) : (
        <ScrollView horizontal accessibilityLabel="배정 시간표 · 가로로 스크롤">
          <View style={{ width: width + 100 }}>
            <View style={{ marginLeft: 100, height: 32 * fontScale }}>
              {Array.from({ length: Math.ceil((end - start) / 60) }, (_, i) => (
                <Text
                  key={i}
                  style={[
                    ui.small,
                    { position: 'absolute', left: x(start + i * 60) },
                  ]}
                >
                  {timeLabel(start + i * 60)}
                </Text>
              ))}
            </View>
            {m.participants.map(p => (
              <View
                key={p.id}
                style={{
                  minHeight: rowHeight,
                  flexDirection: 'row',
                  borderBottomWidth: 1,
                  borderColor: colors.border,
                }}
              >
                <Text
                  numberOfLines={2}
                  style={[ui.text, { width: 100, paddingRight: 8 }]}
                >
                  {p.name}
                </Text>
                <View style={{ width, minHeight: rowHeight }}>
                  {assignments
                    .filter(a => a.participantId === p.id)
                    .map(a => (
                      <View
                        key={a.id}
                        accessible
                        accessibilityLabel={`${p.name} · ${
                          a.role
                        } · ${timeLabel(a.interval.start)}부터 ${timeLabel(
                          a.interval.end,
                        )}`}
                        style={{
                          position: 'absolute',
                          left: x(a.interval.start),
                          width: Math.max(
                            2,
                            x(a.interval.end) - x(a.interval.start),
                          ),
                          minHeight: rowHeight - 8,
                          backgroundColor: colors.pale,
                          borderLeftWidth: 3,
                          borderColor: colors.primary,
                          borderRadius: 8,
                          padding: 4,
                        }}
                      >
                        <Text
                          numberOfLines={2}
                          style={[ui.small, { color: colors.primary }]}
                        >
                          {a.role}
                        </Text>
                      </View>
                    ))}
                </View>
              </View>
            ))}
          </View>
        </ScrollView>
      )}
      <Text style={ui.small}>
        막대는 서버가 제안한 배정 구간이에요. 정확한 시간과 상태는 아래 표에서
        확인하세요.
      </Text>
    </View>
  );
}
