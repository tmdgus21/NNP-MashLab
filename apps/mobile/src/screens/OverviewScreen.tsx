import React, { useState } from 'react';
import { RefreshControl, ScrollView, Share, Text, View } from 'react-native';
import { useApp } from '../state/store';
import { repository, mockRepository } from '../data/repositoryInstance';
import { Scenario } from '../data/RepositoryPort';
import { consentLabel, planLabel } from '../domain/model';
import { Button, Chip, StatusCard } from '../ui/components';
import { Timeline } from '../ui/Timeline';
import { colors, ui } from '../ui/theme';
const scenarios: [Scenario, string][] = [
  ['feasible', '배정 가능'],
  ['conflict', '시간 충돌'],
  ['infeasible', '역할 부족'],
  ['changed', '조건 변경 / 재동의'],
  ['finalized', '최종 확정'],
  ['empty', '빈 조건'],
];
export function OverviewScreen() {
  const app = useApp();
  const m = app.meeting!;
  const [demo, setDemo] = useState(false);
  const count = m.participants.filter(
    p => p.conditions.availability.length && p.conditions.roles.length,
  ).length;
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
        <Text style={ui.eyebrow}>TOGETHER, ON TIME</Text>
        <Text style={[ui.title, { marginTop: 6 }]}>{m.title}</Text>
        <Text style={[ui.muted, { marginTop: 6 }]}>
          {m.dates.map(d => d.slice(5).replace('-', '/')).join(' · ')} |{' '}
          {m.duration}분 | {m.round}차 조율
        </Text>
      </View>
      <View
        style={[ui.card, { backgroundColor: colors.primary, borderWidth: 0 }]}
      >
        <Text style={{ color: '#BEE9DC', fontSize: 13 }}>우리의 조율 현황</Text>
        <View style={ui.row}>
          <Text
            style={{ fontSize: 36, fontWeight: '800', color: colors.white }}
          >
            {count}
            <Text style={{ fontSize: 18, color: '#BEE9DC' }}>
              {' '}
              / {m.participants.length}명
            </Text>
          </Text>
          <Text style={{ color: colors.white }}>조건 입력 완료</Text>
        </View>
        <Text style={{ color: '#DBF0E9' }}>
          모임 → 조건 → 담당표 → 전원 동의 → 방장 확정
        </Text>
      </View>
      <StatusCard
        title={
          m.status === 'finalized'
            ? '함께 정한 일정, 확정 완료'
            : `${m.round}차 · ${planLabel[m.plan.status]}`
        }
        detail={
          m.status === 'finalized'
            ? '담당표에서 확정된 시간과 역할을 확인하세요.'
            : m.previousPlan
            ? '조건이 변경되어 새 회차가 시작됐어요. 이전 동의는 초기화됐습니다.'
            : '각자의 조건을 모아 같은 시간의 역할을 조율해요.'
        }
      />
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
            </View>
            <Text
              style={{
                fontSize: 12,
                color: p.consent === 'agreed' ? colors.primary : colors.muted,
              }}
            >
              {consentLabel[p.consent]}
            </Text>
          </View>
        ))}
        <Button
          title={`초대 코드 ${m.code} 공유`}
          secondary
          onPress={() => {
            void Share.share({
              message: `조건부 OK · ${m.title}\n초대 코드: ${m.code}`,
            });
          }}
        />
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
      {repository.mode === 'mock' && (
        <View style={ui.card}>
          <Button
            title={demo ? '데모 도구 접기' : '데모 시나리오 · 참가자 전환'}
            secondary
            onPress={() => setDemo(!demo)}
          />
          {demo && (
            <>
              <Text style={ui.muted}>
                Mock 전용 도구 · 시나리오 선택은 데모 모임을 초기화합니다. 실제
                모임은 별도로 보존돼요.
              </Text>
              <Text style={ui.heading}>현재 참가자</Text>
              <View style={ui.wrap}>
                {m.participants.map(p => (
                  <Chip
                    key={p.id}
                    title={`${p.name}로 전환`}
                    selected={p.id === app.actorId}
                    onPress={() => {
                      void app.switchActor(p.id);
                    }}
                  />
                ))}
              </View>
              <View style={ui.wrap}>
                {scenarios.map(([s, label]) => (
                  <Chip
                    key={s}
                    title={label}
                    onPress={() => {
                      void app.scenario(s);
                    }}
                  />
                ))}
              </View>
              <Button
                title="다음 조회 오류 재현"
                secondary
                onPress={() => {
                  mockRepository.simulateError();
                  void app.refresh();
                }}
              />
            </>
          )}
        </View>
      )}
    </ScrollView>
  );
}
