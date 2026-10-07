import React, { useState } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { useApp } from '../state/store';
import { canFinalize } from '../domain/rules';
import { consentLabel, planLabel } from '../domain/model';
import { Button, Field, StatusCard } from '../ui/components';
import { PlanTable } from '../ui/PlanTable';
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
  return (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={ui.content}
    >
      <View>
        <Text style={ui.eyebrow}>OUR SCHEDULE</Text>
        <Text style={ui.title}>
          {finished ? '모두의 OK, 조율 완료' : `${m.round}차 제안 담당표`}
        </Text>
        <Text style={ui.muted}>역할 · 시간 · 담당자 · 상태</Text>
      </View>
      <StatusCard
        title={finished ? '최종 확정 완료' : planLabel[m.plan.status]}
        detail={
          finished
            ? '전원 동의 후 방장이 확정했어요. 이 담당표를 기준으로 함께해요.'
            : m.plan.status === 'idle'
            ? '입력한 조건을 바탕으로 담당표를 계산해 주세요.'
            : m.plan.status === 'calculating'
            ? '서버가 조건을 계산하고 있어요. 새로고침으로 결과를 확인하세요.'
            : '담당표와 확인사항을 검토한 뒤 이번 회차에 응답해 주세요.'
        }
      />
      {(m.plan.status === 'idle' || m.plan.status === 'calculating') && (
        <Button
          title={
            m.plan.status === 'idle' ? '담당표 계산하기' : '계산 결과 새로고침'
          }
          onPress={() => {
            void (m.plan.status === 'idle' ? app.calculate() : app.refresh());
          }}
          disabled={!!app.busy}
        />
      )}
      <View style={ui.card}>
        <PlanTable plan={m.plan} meeting={m} />
      </View>
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
                      p.consent === 'agreed' ? colors.primary : colors.muted,
                    fontSize: 13,
                  }}
                >
                  {consentLabel[p.consent]}
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
                title={
                  me.consent === 'agreed'
                    ? '이번 회차에 동의했어요'
                    : '이번 담당표에 동의'
                }
                disabled={!!app.busy || me.consent === 'agreed'}
                onPress={() => {
                  void app.consent('agreed');
                }}
              />
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
      {!finished && m.plan.status === 'feasible' && (
        <StatusCard
          title={
            m.hostId === app.actorId
              ? '방장 최종 확인'
              : '방장의 최종 확정을 기다려요'
          }
          detail="전원이 현재 회차에 동의해야 방장이 확정할 수 있어요. 검토 요청이나 철회가 있으면 확정할 수 없습니다."
        >
          {m.hostId === app.actorId && (
            <Button
              title="전원 동의 확인 · 최종 확정"
              disabled={!!app.busy || !canFinalize(m, app.actorId)}
              onPress={() => {
                void app.finalize();
              }}
            />
          )}
        </StatusCard>
      )}
    </ScrollView>
  );
}
