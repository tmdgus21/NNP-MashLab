import React from 'react';
import { Text, View } from 'react-native';
import { Meeting, Plan } from '../domain/model';
import { timeLabel } from '../domain/time';
import { colors, ui } from './theme';
export function PlanTable({ plan, meeting }: { plan: Plan; meeting: Meeting }) {
  return (
    <View style={{ gap: 0 }}>
      <View
        style={{
          flexDirection: 'row',
          backgroundColor: colors.pale,
          paddingVertical: 12,
        }}
      >
        {['역할', '시간', '담당자', '상태'].map((h, i) => (
          <Text
            key={h}
            style={{
              flex: i === 1 ? 1.8 : 1,
              fontSize: 12,
              fontWeight: '700',
              color: colors.primary,
              paddingLeft: 5,
            }}
          >
            {h}
          </Text>
        ))}
      </View>
      {plan.assignments.map(a => (
        <View
          key={a.id}
          style={{
            flexDirection: 'row',
            paddingVertical: 14,
            borderBottomWidth: 1,
            borderColor: colors.border,
            alignItems: 'center',
          }}
        >
          <Text
            style={{ flex: 1, fontSize: 13, color: colors.ink, paddingLeft: 5 }}
          >
            {a.role}
          </Text>
          <Text style={{ flex: 1.8, fontSize: 11, color: colors.ink }}>
            {a.interval.date.slice(5).replace('-', '/')} {'\n'}
            {timeLabel(a.interval.start)}–{timeLabel(a.interval.end)}
          </Text>
          <Text style={{ flex: 1, fontSize: 13, color: colors.ink }}>
            {meeting.participants.find(p => p.id === a.participantId)?.name ??
              '알 수 없음'}
          </Text>
          <Text style={{ flex: 1, fontSize: 11, color: colors.primary }}>
            {a.status === 'confirmed' ? '확정' : '제안'}
          </Text>
        </View>
      ))}
      {!plan.assignments.length && (
        <Text style={[ui.muted, { paddingVertical: 20 }]}>
          아직 배정된 담당표가 없어요.
        </Text>
      )}
    </View>
  );
}
