import React, { useState } from 'react';
import { KeyboardAvoidingView, ScrollView, Text, View } from 'react-native';
import { useApp } from '../state/store';
import { Conditions, Preview, planLabel } from '../domain/model';
import { repository } from '../data/repositoryInstance';
import { Button, Chip, Field, StatusCard } from '../ui/components';
import { TimeGrid } from '../ui/TimeGrid';
import { PlanTable } from '../ui/PlanTable';
import { NaturalLanguageInput } from '../ui/NaturalLanguageInput';
import { ui } from '../ui/theme';
export function ConditionsScreen() {
  const { meeting, actorId } = useApp();
  return (
    <ConditionEditor key={`${meeting!.id}-${actorId}-${meeting!.round}`} />
  );
}
function ConditionEditor() {
  const app = useApp();
  const m = app.meeting!;
  const me = m.participants.find(p => p.id === app.actorId)!;
  const [draft, setDraft] = useState<Conditions>(me.conditions);
  const [drawing, setDrawing] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [saved, setSaved] = useState(false);
  const locked = m.status === 'finalized';
  const dirty = JSON.stringify(draft) !== JSON.stringify(me.conditions);
  const edit = (patch: Partial<Conditions>) => {
    setDraft(d => ({ ...d, ...patch }));
    setPreview(null);
    setSaved(false);
  };
  return (
    <KeyboardAvoidingView style={ui.flex} behavior="height">
      <ScrollView
        pointerEvents={app.busy ? 'none' : 'auto'}
        scrollEnabled={!drawing}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={ui.content}
      >
        <View>
          <Text style={ui.eyebrow}>MY CONDITIONS</Text>
          <Text style={ui.title}>{me.name}님의 조건</Text>
          <Text style={ui.muted}>
            {locked
              ? '확정된 조건입니다.'
              : '입력 중인 내용은 미리보기 후 적용해야 저장돼요.'}
          </Text>
        </View>
        {(locked || saved) && (
          <StatusCard
            title={locked ? '최종 확정된 모임' : '조건 저장 완료'}
            detail={
              locked
                ? '확정된 조건은 수정할 수 없습니다.'
                : '담당표에서 새 조건으로 계산해 주세요.'
            }
          />
        )}
        <View style={ui.card}>
          <Text style={ui.heading}>01 가능한 시간</Text>
          <TimeGrid
            dates={m.dates}
            value={draft.availability}
            onChange={availability => edit({ availability })}
            onDrawing={setDrawing}
            disabled={locked}
          />
        </View>
        <View style={ui.card}>
          <Text style={ui.heading}>02 할 수 있는 역할</Text>
          <Text style={ui.muted}>가능한 역할을 모두 선택하세요.</Text>
          <View style={ui.wrap}>
            {m.roles.map(role => (
              <Chip
                key={role}
                title={role}
                selected={draft.roles.includes(role)}
                onPress={() => {
                  if (!locked) {
                    edit({
                      roles: draft.roles.includes(role)
                        ? draft.roles.filter(r => r !== role)
                        : [...draft.roles, role],
                    });
                  }
                }}
              />
            ))}
          </View>
        </View>
        <View style={ui.card}>
          <Text style={ui.heading}>03 선호와 동반조건</Text>
          <View style={ui.wrap}>
            {(
              [
                ['balanced', '상관없어요'],
                ['early', '이른 시간'],
                ['late', '늦은 시간'],
              ] as const
            ).map(([value, label]) => (
              <Chip
                key={value}
                title={label}
                selected={draft.preference === value}
                onPress={() => {
                  if (!locked) {
                    edit({ preference: value });
                  }
                }}
              />
            ))}
          </View>
          <Text style={ui.muted}>
            동반자는 같은 시간에 참여 가능해야 해요. 담당 역할 배정까지 보장하는
            조건은 아닙니다.
          </Text>
          <View style={ui.wrap}>
            <Chip
              title="동반조건 없음"
              selected={!draft.companionId}
              onPress={() => {
                if (!locked) {
                  edit({ companionId: null });
                }
              }}
            />
            {m.participants
              .filter(p => p.id !== me.id)
              .map(p => (
                <Chip
                  key={p.id}
                  title={`${p.name}와 함께`}
                  selected={draft.companionId === p.id}
                  onPress={() => {
                    if (!locked) {
                      edit({ companionId: p.id });
                    }
                  }}
                />
              ))}
          </View>
          <Field
            label="추가 확인 메모"
            multiline
            value={draft.note}
            onChangeText={note => edit({ note })}
            editable={!locked}
            maxLength={1000}
          />
        </View>
        <NaturalLanguageInput
          parse={text => repository.parseConditions(text)}
          onAccept={edit}
          disabled={locked}
        />
        {!locked && (
          <Button
            testID="preview-change"
            title="변경 전 미리보기"
            disabled={!!app.busy || !dirty}
            onPress={() => {
              void app.preview(draft).then(result => {
                if (result) {
                  setPreview(result);
                }
              });
            }}
          />
        )}
        {preview && (
          <View style={ui.card}>
            <Text style={ui.heading}>적용하면 이렇게 바뀌어요</Text>
            {preview.changes.map(c => (
              <Text key={c} style={ui.muted}>
                • {c}
              </Text>
            ))}
            <Text style={ui.heading}>
              기존안 · {planLabel[preview.before.status]}
            </Text>
            <PlanTable plan={preview.before} meeting={m} />
            <Text style={ui.heading}>
              변경안 · {planLabel[preview.after.status]}
            </Text>
            <PlanTable plan={preview.after} meeting={m} />
            {preview.after.notices.map(n => (
              <StatusCard key={n.id} {...n} />
            ))}
            <Text style={ui.muted}>
              미리보기는 저장되지 않습니다. 적용 후 담당표를 다시 계산하고 전원
              동의를 받아야 해요.
            </Text>
            <Button
              title="변경 적용 · 새 조율 시작"
              disabled={!!app.busy}
              onPress={() => {
                void app.apply(draft, preview.revision).then(ok => {
                  if (ok) {
                    setPreview(null);
                    setSaved(true);
                  }
                });
              }}
            />
            <Button
              title="미리보기 닫기"
              secondary
              onPress={() => setPreview(null)}
            />
          </View>
        )}
        {dirty && !locked && (
          <Button
            title="입력 변경 취소"
            secondary
            onPress={() => {
              setDraft(me.conditions);
              setPreview(null);
            }}
          />
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
