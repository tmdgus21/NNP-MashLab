import React, { useState } from 'react';
import { Alert, RefreshControl, ScrollView, Text, View } from 'react-native';
import { useApp } from '../state/store';
import { canFinalize } from '../domain/rules';
import { consentLabel, planLabel } from '../domain/model';
import { Button, Field, StatusCard } from '../ui/components';
import { AssignmentTimeline } from '../ui/AssignmentTimeline';
import { PlanTable } from '../ui/PlanTable';
import { intervalLabel } from '../domain/time';
import { Disclosure } from '../ui/Disclosure';
import { colors, ui } from '../ui/theme';
export function ScheduleScreen() {
  const app = useApp();
  const m = app.meeting!;
  const me = m.participants.find(p => p.id === app.actorId)!;
  const [note, setNote] = useState('');
  const [old, setOld] = useState(false);
  const agreed = m.participants.filter(
    p => p.consent === 'agreed' && p.consentRound === m.round,
  ).length;
  const finished = m.status === 'finalized';
  const mine = m.plan.assignments.filter(a => a.participantId === app.actorId);
  const hasAgreed = me.consent === 'agreed' && me.consentRound === m.round;
  const mayFinalize = canFinalize(m, app.actorId);
  const host = m.hostId === app.actorId;
  const waiting = m.plan.status === 'idle' && !host;
  const actionLabel = mayFinalize
    ? '전원 동의 · 최종 확정'
    : m.plan.status === 'feasible'
    ? hasAgreed
      ? agreed === m.participants.length
        ? '방장의 최종 확정을 기다려요'
        : '동의 완료 · 다른 참여자를 기다려요'
      : '이번 담당표에 동의'
    : m.plan.status === 'calculating'
    ? '계산 결과 확인'
    : host
    ? '담당표 계산하기'
    : '방장의 배정을 기다려요';
  const act = () => {
    if (mayFinalize) {
      Alert.alert(
        '이 담당표로 최종 확정할까요?',
        '확정 후에는 조건을 수정할 수 없어요.',
        [
          { text: '더 살펴보기', style: 'cancel' },
          {
            text: '최종 확정',
            onPress: () => {
              void app.finalize();
            },
          },
        ],
      );
    } else if (m.plan.status === 'feasible') {
      void app.consent('agreed');
    } else if (m.plan.status === 'calculating') {
      void app.refresh();
    } else {
      void app.calculate();
    }
  };
  return (
    <View style={ui.flex}>
      <ScrollView
        refreshControl={
          <RefreshControl
            refreshing={app.busy === '최신 현황을 불러오는 중'}
            onRefresh={() => {
              void app.refresh();
            }}
          />
        }
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={ui.content}
      >
        <View>
          <Text style={ui.eyebrow}>함께 정한 담당표</Text>
          <Text style={ui.title}>
            {finished
              ? '모두의 OK, 조율 완료'
              : m.round === 0
              ? '첫 담당표 준비'
              : `${m.round}차 제안 담당표`}
          </Text>
          <Text style={ui.muted}>역할 · 시간 · 담당자 · 상태</Text>
        </View>
        <View style={ui.hero}>
          <Text style={{ color: '#DEDBFF', fontSize: 13 }}>
            나의 배정 · {me.name}
          </Text>
          {mine.length ? (
            mine.map(a => (
              <View key={a.id} style={{ gap: 6 }}>
                <Text
                  style={{
                    color: colors.white,
                    fontSize: 26,
                    fontWeight: '800',
                  }}
                >
                  {a.role}
                </Text>
                <Text style={{ color: colors.white, fontSize: 16 }}>
                  {intervalLabel(a.interval)}
                </Text>
                <Text style={{ color: '#DEDBFF' }}>
                  {finished
                    ? '최종 확정'
                    : '제안된 배정 · 전체 담당표도 확인해 주세요'}
                </Text>
              </View>
            ))
          ) : (
            <Text style={{ color: colors.white, fontSize: 18 }}>
              {m.plan.status === 'feasible'
                ? '이번 담당표에는 내 배정이 없어요'
                : '아직 배정이 없어요'}
            </Text>
          )}
        </View>
        <StatusCard
          title={finished ? '최종 확정 완료' : planLabel[m.plan.status]}
          detail={
            finished
              ? '전원 동의 후 방장이 확정했어요. 이 담당표를 기준으로 함께해요.'
              : m.plan.status === 'idle'
              ? host
                ? '모든 참가자의 조건을 확인하고 배정해 주세요.'
                : '조건 제출 후 방장의 배정을 기다려 주세요.'
              : m.plan.status === 'calculating'
              ? '서버가 조건을 계산하고 있어요. 새로고침으로 결과를 확인하세요.'
              : '담당표와 확인사항을 검토한 뒤 이번 회차에 응답해 주세요.'
          }
        />
        <Disclosure title="전체 담당표 · 시간표">
          <View style={ui.card}>
            <Text style={ui.heading}>전체 담당표</Text>
            <Text style={ui.muted}>
              {m.plan.solverStatus === 'OPTIMAL'
                ? '배정 가능 · 선호조건의 최적성 확인됨'
                : m.plan.solverStatus === 'FEASIBLE'
                ? '배정 가능 · 최적성은 아직 미확인'
                : m.plan.solverStatus === 'INFEASIBLE'
                ? '현재 필수조건으로 배정 불가'
                : m.plan.solverStatus === 'UNKNOWN'
                ? '계산 제한 내 배정 가능 여부를 확인하지 못했어요'
                : m.plan.status === 'feasible'
                ? '배정 가능 · 최적성 정보 없음'
                : m.plan.status === 'infeasible'
                ? '현재 필수조건으로 배정 불가'
                : m.plan.status === 'unknown'
                ? '배정 가능 여부 미확인'
                : '계산 결과 대기'}
            </Text>
            <AssignmentTimeline meeting={m} />
            <PlanTable plan={m.plan} meeting={m} />
          </View>
        </Disclosure>
        {m.plan.notices.map(n => (
          <StatusCard key={n.id} {...n} />
        ))}
        {m.previousPlan && (
          <>
            <Button
              title={
                old
                  ? '이전 회차 접기'
                  : `${m.previousPlan.round}차 기존 담당표와 비교`
              }
              secondary
              onPress={() => setOld(!old)}
            />
            {old && (
              <View style={ui.card}>
                <Text style={ui.heading}>이전 회차 · 참고용</Text>
                <PlanTable plan={m.previousPlan} meeting={m} />
              </View>
            )}
          </>
        )}
        <Disclosure
          title={`동의 현황 · ${agreed}/${m.participants.length}명 · 철회 / 검토요청`}
        >
          {m.plan.status === 'feasible' && (
            <View style={ui.card}>
              <Text style={ui.heading}>
                이번 회차 동의 {agreed} / {m.participants.length}
              </Text>
              <View
                style={{
                  height: 7,
                  borderRadius: 4,
                  backgroundColor: colors.pale,
                  overflow: 'hidden',
                }}
              >
                <View
                  style={{
                    height: 7,
                    width: `${(100 * agreed) / m.participants.length}%`,
                    backgroundColor: colors.primary,
                  }}
                />
              </View>
              {m.participants.map(p => (
                <View key={p.id}>
                  <View style={[ui.row, { justifyContent: 'space-between' }]}>
                    <Text style={ui.text}>
                      {p.name}
                      {p.id === app.actorId ? ' · 나' : ''}
                    </Text>
                    <Text
                      style={{
                        color:
                          p.consent === 'agreed' && p.consentRound === m.round
                            ? colors.primary
                            : colors.muted,
                        fontSize: 13,
                      }}
                    >
                      {p.consentRound !== m.round
                        ? '재동의 필요'
                        : consentLabel[p.consent]}
                    </Text>
                  </View>
                  {!!p.reviewNote && (
                    <Text style={ui.muted}>검토: {p.reviewNote}</Text>
                  )}
                </View>
              ))}
              {!finished && (
                <>
                  <Button
                    title="동의 / 검토요청 철회"
                    secondary
                    disabled={!!app.busy || me.consent === 'pending'}
                    onPress={() => {
                      void app.consent('pending');
                    }}
                  />
                  <Field
                    label="검토 요청 사유"
                    multiline
                    value={note}
                    onChangeText={setNote}
                    placeholder="다시 조율이 필요한 내용을 적어 주세요"
                    maxLength={500}
                  />
                  <Button
                    title="검토 요청하기"
                    secondary
                    disabled={!!app.busy || !note.trim()}
                    onPress={() => {
                      void app.consent('review', note);
                    }}
                  />
                </>
              )}
            </View>
          )}
        </Disclosure>
        {!finished && m.plan.status === 'feasible' && (
          <StatusCard
            title={
              m.hostId === app.actorId
                ? '방장 최종 확인'
                : '방장의 최종 확정을 기다려요'
            }
            detail="전원이 현재 회차에 동의해야 방장이 확정할 수 있어요. 검토 요청이나 철회가 있으면 확정할 수 없습니다."
          ></StatusCard>
        )}
        <Disclosure title="새로고침 · 재배정">
          {!finished && host && m.plan.status === 'feasible' && (
            <Button
              title="새 회차로 다시 배정"
              secondary
              disabled={!!app.busy}
              onPress={() => {
                Alert.alert(
                  '새 회차를 시작할까요?',
                  '기존 동의를 이어 쓰지 않고 모두 다시 동의해야 해요.',
                  [
                    { text: '취소', style: 'cancel' },
                    {
                      text: '다시 배정',
                      onPress: () => {
                        void app.calculate();
                      },
                    },
                  ],
                );
              }}
            />
          )}
          {!finished &&
            m.hostId !== app.actorId &&
            m.plan.status === 'idle' && (
              <Text style={ui.muted}>
                조건 제출 후 방장의 배정을 기다려 주세요.
              </Text>
            )}
          <Button
            title="최신 담당표 새로고침"
            secondary
            onPress={() => {
              void app.refresh();
            }}
            disabled={!!app.busy}
          />
        </Disclosure>
      </ScrollView>
      {!finished && (
        <View style={ui.dock}>
          <Text style={ui.small}>
            {m.plan.status === 'feasible'
              ? `${m.round}차 · ${agreed}/${m.participants.length}명 동의${
                  host ? ' · 최종 확정은 방장이 진행해요' : ''
                }`
              : '배정 상태를 확인한 뒤 다음으로 진행해요'}
          </Text>
          <Button
            title={app.busy || actionLabel}
            disabled={
              !!app.busy ||
              waiting ||
              (m.plan.status === 'feasible' && hasAgreed && !mayFinalize) ||
              (!host &&
                m.plan.status !== 'feasible' &&
                m.plan.status !== 'calculating')
            }
            onPress={act}
          />
        </View>
      )}
    </View>
  );
}
