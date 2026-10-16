import React from 'react';
import { RefreshControl, ScrollView, Text, View } from 'react-native';
import { useApp } from '../state/store';
import { consentLabel, planLabel } from '../domain/model';
import { useNavigation } from '@react-navigation/native';
import { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import { Button } from '../ui/components';
import { Timeline } from '../ui/Timeline';
import { MeetingActions } from '../ui/MeetingActions';
import { colors, ui } from '../ui/theme';
export function OverviewScreen() {
  const app = useApp();
  const navigation =
    useNavigation<
      BottomTabNavigationProp<{
        현황: undefined;
        '내 조건': undefined;
        담당표: undefined;
      }>
    >();
  const m = app.meeting!;
  const count = m.participants.filter(
    p =>
      p.submitted ??
      !!(p.conditions.availability.length && p.conditions.roles.length),
  ).length;
  const me = m.participants.find(p => p.id === app.actorId)!;
  const agreed = m.participants.filter(
    p => p.consent === 'agreed' && p.consentRound === m.round,
  ).length;
  const needsInput =
    me.submitted === false ||
    (!me.submitted && !me.conditions.availability.length);
  const nextTitle =
    m.status === 'finalized'
      ? '확정된 담당표 확인'
      : needsInput
      ? '내 조건 입력하기'
      : m.plan.status === 'feasible'
      ? '담당표 확인하고 응답하기'
      : m.hostId === app.actorId && count === m.participants.length
      ? '담당표 배정하러 가기'
      : '담당표 진행 상태 확인';
  return (
    <ScrollView
      contentContainerStyle={ui.content}
      refreshControl={
        <RefreshControl
          refreshing={app.busy === '최신 현황을 불러오는 중'}
          onRefresh={() => {
            void app.refresh();
          }}
          tintColor={colors.primary}
        />
      }
    >
      <View>
        <Text style={ui.eyebrow}>우리 모임 한눈에</Text>
        <Text style={[ui.title, { marginTop: 6 }]}>함께 맞추는 시간</Text>
        <Text style={[ui.muted, { marginTop: 6 }]}>
          {m.dates.map(d => d.slice(5).replace('-', '/')).join(' · ')} |{' '}
          {m.duration}분 | {m.round === 0 ? '조건 수집' : `${m.round}차 조율`}
        </Text>
      </View>
      <MeetingActions />
      <View style={ui.summary}>
        <Text style={ui.eyebrow}>지금 할 일</Text>
        <Text style={ui.heading}>
          {m.status === 'finalized'
            ? '함께 정한 일정이 확정됐어요'
            : planLabel[m.plan.status]}
        </Text>
        <Button
          title={nextTitle}
          onPress={() =>
            navigation.navigate(
              needsInput && m.status !== 'finalized' ? '내 조건' : '담당표',
            )
          }
        />
      </View>
      <View style={ui.bento}>
        <View style={ui.tile}>
          <Text style={ui.muted}>참여 인원</Text>
          <Text style={ui.metric}>{m.participants.length}명</Text>
          <Text style={ui.small}>현재 모임 참여자</Text>
        </View>
        <View style={ui.tile}>
          <Text style={ui.muted}>조건 제출률</Text>
          <Text style={ui.metric}>
            {Math.round((count / Math.max(1, m.participants.length)) * 100)}%
          </Text>
          <Text style={ui.small}>
            {count} / {m.participants.length}명 제출
          </Text>
        </View>
        <View style={ui.tile}>
          <Text style={ui.muted}>현재 회차 동의</Text>
          <Text style={ui.metric}>
            {agreed} / {m.participants.length}
          </Text>
          <Text style={ui.small}>
            {m.round ? `${m.round}차 담당표 기준` : '첫 배정 전'}
          </Text>
        </View>
      </View>
      <View style={ui.card}>
        <Text style={ui.heading}>한눈에 보는 가능시간</Text>
        <Timeline key={m.id} meeting={m} />
      </View>
      <View style={ui.card}>
        <Text style={ui.heading}>참가자 {m.participants.length}명</Text>
        {m.participants.map(p => (
          <View
            key={p.id}
            style={[ui.row, { justifyContent: 'space-between' }]}
          >
            <View style={ui.flex}>
              <Text style={ui.text}>
                {p.name}
                {p.id === m.hostId ? ' · 방장' : ''}
                {p.id === app.actorId ? ' · 나' : ''}
              </Text>
              <Text style={ui.small}>
                {p.conditions.roles.join(' · ') || '역할 미입력'}
              </Text>
              <Text style={ui.small}>
                {p.submitted === undefined
                  ? ''
                  : p.submitted
                  ? `제출 완료 · v${p.conditionVersion}`
                  : '아직 제출하지 않았어요'}
              </Text>
              {!!p.conditions.requiredRoles?.length && (
                <Text style={ui.small}>
                  필수: {p.conditions.requiredRoles.join(', ')}
                </Text>
              )}
              {!!p.conditions.roleUnavailable?.length && (
                <Text style={ui.small}>
                  불가: {p.conditions.roleUnavailable.join(', ')}
                </Text>
              )}
              {!!p.conditions.rolePreferences?.length && (
                <Text style={ui.small}>
                  선호: {p.conditions.rolePreferences.join(', ')}
                </Text>
              )}
            </View>
            <Text
              style={{
                fontSize: 12,
                color: p.consent === 'agreed' ? colors.primary : colors.muted,
              }}
            >
              {p.consentRound !== m.round
                ? '재동의 필요'
                : consentLabel[p.consent]}
            </Text>
          </View>
        ))}
      </View>
      <View style={ui.card}>
        <Text style={ui.heading}>조율 기록</Text>
        {m.history
          .slice(-5)
          .reverse()
          .map((h, i) => (
            <Text key={`${i}-${h}`} style={ui.muted}>
              • {h}
            </Text>
          ))}
      </View>
      <Button
        title="현황 새로고침"
        secondary
        onPress={() => {
          void app.refresh();
        }}
        disabled={!!app.busy}
      />
    </ScrollView>
  );
}
