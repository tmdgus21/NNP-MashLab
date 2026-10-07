import React, { useState } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { Meeting } from '../domain/model';
import { intervalsToSlots, timeLabel } from '../domain/time';
import { Chip } from './components';
import { colors, ui } from './theme';
const CELL = 30;
export function Timeline({ meeting: m }: { meeting: Meeting }) {
  const [date, setDate] = useState(m.dates[0]);
  const slots = Array.from(
    { length: (m.windowEnd - m.windowStart) / 30 },
    (_, i) => m.windowStart / 30 + i,
  );
  const people = m.participants.map(p => ({
    ...p,
    slots: intervalsToSlots(p.conditions.availability, date),
  }));
  const counts = slots.map(s => people.filter(p => p.slots.includes(s)).length);
  return (
    <View style={{ gap: 12 }}>
      <View style={ui.wrap}>
        {m.dates.map(d => (
          <Chip
            key={d}
            title={d.slice(5).replace('-', '/')}
            selected={d === date}
            onPress={() => setDate(d)}
          />
        ))}
      </View>
      <View style={{ flexDirection: 'row' }}>
        <View style={{ width: 62 }}>
          <Text style={[ui.small, { height: 28 }]}>참가자</Text>
          {people.map(p => (
            <Text
              key={p.id}
              numberOfLines={1}
              style={[ui.text, { height: 36, paddingTop: 7 }]}
            >
              {p.name}
            </Text>
          ))}
          <Text style={[ui.small, { height: 36, paddingTop: 10 }]}>
            가능 인원
          </Text>
        </View>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator
          accessibilityLabel="참가자별 가능시간 가로 타임라인"
        >
          <View>
            <View style={{ flexDirection: 'row' }}>
              {slots.map(s => (
                <Text
                  key={s}
                  style={{
                    width: CELL,
                    height: 28,
                    fontSize: 9,
                    color: colors.muted,
                  }}
                >
                  {timeLabel(s * 30)}
                </Text>
              ))}
            </View>
            {people.map(p => (
              <View key={p.id} style={{ flexDirection: 'row', height: 36 }}>
                {slots.map(s => (
                  <View
                    key={s}
                    accessible
                    accessibilityLabel={`${p.name} ${timeLabel(s * 30)} ${
                      p.slots.includes(s) ? '가능' : '불가'
                    }`}
                    style={{
                      width: CELL,
                      height: 28,
                      marginTop: 4,
                      borderRightWidth: 2,
                      borderColor: colors.white,
                      backgroundColor: p.slots.includes(s)
                        ? '#65B8A5'
                        : '#EFF2F1',
                    }}
                  />
                ))}
              </View>
            ))}
            <View style={{ flexDirection: 'row' }}>
              {counts.map((count, i) => (
                <View
                  key={i}
                  style={{
                    width: CELL,
                    height: 34,
                    alignItems: 'center',
                    justifyContent: 'center',
                    backgroundColor:
                      count >= m.roles.length ? colors.primary : colors.pale,
                    borderRightWidth: 2,
                    borderColor: colors.white,
                  }}
                >
                  <Text
                    style={{
                      fontSize: 12,
                      fontWeight: '700',
                      color:
                        count >= m.roles.length ? colors.white : colors.primary,
                    }}
                  >
                    {count}
                  </Text>
                </View>
              ))}
            </View>
          </View>
        </ScrollView>
      </View>
      <Text style={ui.small}>
        가로로 밀어 비교 · 진한 칸은 필요 인원 이상{'\n'}가능 인원은 참고치이며
        역할·동반조건 충족 여부는 계산 후 확인해요.
      </Text>
    </View>
  );
}
