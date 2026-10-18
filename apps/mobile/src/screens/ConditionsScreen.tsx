import React, { useRef, useState } from 'react';
import {
  Alert,
  Keyboard,
  KeyboardAvoidingView,
  ScrollView,
  Text,
  View,
} from 'react-native';
import { useApp } from '../state/store';
import { Conditions, Preview, planLabel } from '../domain/model';
import { repository } from '../data/repositoryInstance';
import { Button, Chip, Field, StatusCard } from '../ui/components';
import { TimeGrid } from '../ui/TimeGrid';
import { PlanTable } from '../ui/PlanTable';
import { NaturalLanguageInput } from '../ui/NaturalLanguageInput';
import { intervalLabel } from '../domain/time';
import { Disclosure } from '../ui/Disclosure';
import { colors, ui } from '../ui/theme';
export function ConditionsScreen() {
  const { meeting, actorId } = useApp();
  return (
    <ConditionEditor key={`${meeting!.id}-${actorId}-${meeting!.round}`} />
  );
}
function ConditionEditor() {
  const app = useApp();
  const scroll = useRef<React.ComponentRef<typeof ScrollView>>(null);
  const revealPreview = useRef(false);
  const m = app.meeting!;
  const me = m.participants.find(p => p.id === app.actorId)!;
  const [draft, setDraft] = useState<Conditions>(me.conditions);
  const [drawing, setDrawing] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [details, setDetails] = useState(false);
  const [saved, setSaved] = useState(false);
  const [timeMode, setTimeMode] = useState<
    'availability' | 'unavailable' | 'preferred' | 'avoid'
  >('availability');
  const [parseDate, setParseDate] = useState(m.dates[0]);
  const locked = m.status === 'finalized';
  const dirty =
    JSON.stringify(draft) !== JSON.stringify(me.conditions) ||
    me.submitted === false;
  const edit = (patch: Partial<Conditions>) => {
    setDraft(d => ({ ...d, ...patch }));
    setPreview(null);
    setSaved(false);
  };
  return (
    <KeyboardAvoidingView style={ui.flex} behavior="height">
      <ScrollView
        ref={scroll}
        onContentSizeChange={() => {
          if (revealPreview.current) {
            revealPreview.current = false;
            scroll.current?.scrollToEnd({ animated: true });
          }
        }}
        pointerEvents={app.busy ? 'none' : 'auto'}
        scrollEnabled={!drawing}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={ui.content}
      >
        <View>
          <Text style={ui.heading}>{me.name}님의 조건</Text>
          <Text style={ui.muted}>
            {locked
              ? '확정된 조건입니다.'
              : '가능한 시간과 역할을 선택하고 조건을 검토해 주세요.'}
          </Text>
        </View>
        {(locked || saved) && (
          <StatusCard
            title={locked ? '최종 확정된 모임' : '조건 저장 완료'}
            detail={
              locked
                ? '확정된 조건은 수정할 수 없습니다.'
                : m.hostId === app.actorId
                ? '담당표에서 새 조건으로 계산해 주세요.'
                : '조건을 제출했어요. 방장이 배정하면 담당표에서 확인해 주세요.'
            }
          />
        )}
        <View style={ui.section}>
          <View style={ui.card}>
            <Text style={ui.heading}>가능한 시간</Text>
            <Button
              title={details ? '상세 조건 접기' : '상세 조건 펼치기'}
              secondary
              onPress={() => {
                setDetails(!details);
                setTimeMode('availability');
              }}
            />
            {details && repository.mode === 'http' && (
              <View style={ui.wrap}>
                {(
                  [
                    ['availability', '가능'],
                    ['unavailable', '불가'],
                    ['preferred', '선호'],
                    ['avoid', '회피'],
                  ] as const
                ).map(([value, label]) => (
                  <Chip
                    key={value}
                    title={label}
                    selected={timeMode === value}
                    onPress={() => setTimeMode(value)}
                  />
                ))}
              </View>
            )}
            <TimeGrid
              label={
                {
                  availability: '가능 · 필수',
                  unavailable: '불가 · 필수',
                  preferred: '선호 · 희망',
                  avoid: '회피 · 희망',
                }[timeMode]
              }
              tone={
                timeMode === 'unavailable'
                  ? colors.danger
                  : timeMode === 'avoid'
                  ? colors.warn
                  : timeMode === 'preferred'
                  ? colors.ink
                  : colors.primary
              }
              dates={m.dates}
              value={
                timeMode === 'availability'
                  ? draft.availability
                  : timeMode === 'unavailable'
                  ? draft.unavailable ?? []
                  : (draft.timePreferences ?? []).filter(
                      i =>
                        i.kind ===
                        (timeMode === 'preferred'
                          ? 'available'
                          : 'unavailable'),
                    )
              }
              onChange={value => {
                if (timeMode === 'availability') {
                  edit({ availability: value });
                } else if (timeMode === 'unavailable') {
                  edit({ unavailable: value });
                } else {
                  const kind =
                    timeMode === 'preferred' ? 'available' : 'unavailable';
                  edit({
                    timePreferences: [
                      ...(draft.timePreferences ?? []).filter(
                        i => i.kind !== kind,
                      ),
                      ...value.map(i => ({
                        ...i,
                        kind: kind as 'available' | 'unavailable',
                      })),
                    ],
                  });
                }
              }}
              onDrawing={setDrawing}
              disabled={locked}
            />
          </View>
        </View>
        <View style={ui.section}>
          <View style={ui.card}>
            <Text style={ui.heading}>할 수 있는 역할 · 필수</Text>
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
          {repository.mode === 'http' && (
            <View style={ui.card}>
              <Text style={ui.heading}>역할별 조건</Text>
              <Text style={ui.small}>
                필수 역할도 '할 수 있는 역할'에 포함돼야 배정할 수 있어요.
              </Text>
              {(
                [
                  ['requiredRoles', '반드시 맡기'],
                  ['roleUnavailable', '맡을 수 없음'],
                  ['rolePreferences', '가능하면 맡기'],
                ] as const
              ).map(([key, label]) => (
                <View
                  key={key}
                  style={{
                    display:
                      details || key === 'requiredRoles' ? 'flex' : 'none',
                  }}
                >
                  <Text style={ui.muted}>{label}</Text>
                  <View style={ui.wrap}>
                    {m.roles.map(role => (
                      <Chip
                        key={role}
                        title={role}
                        selected={(draft[key] ?? []).includes(role)}
                        onPress={() => {
                          if (!locked) {
                            const items = draft[key] ?? [];
                            edit({
                              [key]: items.includes(role)
                                ? items.filter(r => r !== role)
                                : [...items, role],
                            });
                          }
                        }}
                      />
                    ))}
                  </View>
                </View>
              ))}
            </View>
          )}
        </View>
        <View style={[ui.section, { display: details ? 'flex' : 'none' }]}>
          <View style={ui.card}>
            <Text style={ui.heading}>선호와 동반조건</Text>
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
              {repository.mode === 'http'
                ? '필수 동반자는 내가 배정될 때 같은 담당표에 함께 배정돼야 해요.'
                : '동반자는 같은 시간에 참여 가능해야 해요. 담당 역할 배정까지 보장하는 조건은 아닙니다.'}
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
          {repository.mode === 'http' && (
            <View style={ui.card}>
              <Text style={ui.heading}>동반 세부조건</Text>
              {m.participants
                .filter(p => p.id !== me.id)
                .map(p => (
                  <View key={p.id}>
                    <Text style={ui.muted}>{p.name}</Text>
                    <View style={ui.wrap}>
                      {(
                        [
                          ['together', 'required', '함께 필수'],
                          ['together', 'preferred', '함께 선호'],
                          ['apart', 'required', '함께 불가'],
                          ['apart', 'preferred', '따로 선호'],
                        ] as const
                      ).map(([relation, strength, label]) => {
                        const selected = (
                          draft.companionRequirements ?? []
                        ).some(
                          c =>
                            c.participantId === p.id &&
                            c.relation === relation &&
                            c.strength === strength,
                        );
                        return (
                          <Chip
                            key={label}
                            title={label}
                            selected={selected}
                            onPress={() => {
                              if (!locked) {
                                edit({
                                  companionId: null,
                                  companionRequirements: [
                                    ...(
                                      draft.companionRequirements ?? []
                                    ).filter(c => c.participantId !== p.id),
                                    ...(selected
                                      ? []
                                      : [
                                          {
                                            participantId: p.id,
                                            relation,
                                            strength,
                                          },
                                        ]),
                                  ],
                                });
                              }
                            }}
                          />
                        );
                      })}
                    </View>
                  </View>
                ))}
              <Text style={ui.muted}>
                AI가 제안한 세부조건도 여기서 수정할 수 있어요.
              </Text>
            </View>
          )}
          {repository.mode === 'http' && (
            <View style={ui.wrap}>
              {m.dates.map(date => (
                <Chip
                  key={date}
                  title={`자연어 기준 ${date}`}
                  selected={parseDate === date}
                  onPress={() => setParseDate(date)}
                />
              ))}
            </View>
          )}
          <NaturalLanguageInput
            parse={text =>
              repository.parseConditions(text, {
                meetingId: m.id,
                date: parseDate,
              })
            }
            onAccept={edit}
            disabled={locked}
          />
        </View>
        <View style={ui.section}>
          <View style={ui.card}>
            <Text style={ui.heading}>제출 전 확인</Text>
            <Text style={ui.muted}>
              입력한 시간과 역할을 확인해 주세요. 상세 조건도 제출에 함께
              반영됩니다.
            </Text>
            <Text style={ui.text}>
              가능 시간 ·{' '}
              {draft.availability.map(intervalLabel).join(', ') || '미입력'}
            </Text>
            <Text style={ui.text}>
              가능 역할 · {draft.roles.join(', ') || '미입력'}
            </Text>
            <Text style={ui.text}>
              필수 역할 · {draft.requiredRoles?.join(', ') || '없음'}
            </Text>
            <Disclosure title="상세 조건 요약">
              <Text style={ui.text}>
                불가 시간 ·{' '}
                {(draft.unavailable ?? []).map(intervalLabel).join(', ') ||
                  '없음'}
              </Text>
              <Text style={ui.text}>
                가능 역할 · {draft.roles.join(', ') || '미입력'}
              </Text>
              <Text style={ui.text}>
                필수 역할 · {draft.requiredRoles?.join(', ') || '없음'}
              </Text>
              <Text style={ui.text}>
                불가 역할 · {draft.roleUnavailable?.join(', ') || '없음'}
              </Text>
              <Text style={ui.text}>
                선호 역할 · {draft.rolePreferences?.join(', ') || '없음'}
              </Text>
              <Text style={ui.text}>
                시간 선호 ·{' '}
                {
                  {
                    balanced: '상관없음',
                    early: '이른 시간',
                    late: '늦은 시간',
                  }[draft.preference]
                }
              </Text>
              {(draft.timePreferences ?? []).map((t, i) => (
                <Text key={i} style={ui.text}>
                  {t.kind === 'available' ? '선호' : '회피'} ·{' '}
                  {intervalLabel(t)}
                </Text>
              ))}
              {!!draft.companionId && (
                <Text style={ui.text}>
                  함께 필수 ·{' '}
                  {m.participants.find(p => p.id === draft.companionId)?.name}
                </Text>
              )}
              {(draft.companionRequirements ?? []).map((c, i) => (
                <Text key={i} style={ui.text}>
                  {m.participants.find(p => p.id === c.participantId)?.name} ·{' '}
                  {c.relation === 'together' ? '함께' : '따로'} ·{' '}
                  {c.strength === 'required' ? '필수' : '선호'}
                </Text>
              ))}
              {!!draft.note && <Text style={ui.text}>메모 · {draft.note}</Text>}
            </Disclosure>
          </View>
          {draft.aiDraftId && (
            <View style={ui.card}>
              <Text style={ui.muted}>
                AI에서 가져온 시간·역할·동반조건을 상세 조건에서 수정한 뒤
                확인해 주세요.
              </Text>
              <Chip
                title="확인사항을 해결하고 입력을 검토했어요"
                selected={draft.ambiguitiesResolved}
                onPress={() => {
                  if (!locked) {
                    edit({ ambiguitiesResolved: !draft.ambiguitiesResolved });
                  }
                }}
              />
            </View>
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
                미리보기는 저장되지 않습니다. 적용 후 담당표를 다시 계산하고
                전원 동의를 받아야 해요.
              </Text>
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
                Alert.alert(
                  '입력 변경을 취소할까요?',
                  '마지막으로 저장한 조건으로 돌아갑니다.',
                  [
                    { text: '계속 입력', style: 'cancel' },
                    {
                      text: '변경 취소',
                      style: 'destructive',
                      onPress: () => {
                        setDraft(me.conditions);
                        setPreview(null);
                        setSaved(false);
                      },
                    },
                  ],
                );
              }}
            />
          )}
        </View>
      </ScrollView>
      <View style={ui.dock}>
        <Text accessibilityLiveRegion="polite" style={ui.small}>
          {locked
            ? '최종 확정된 조건입니다'
            : saved
            ? '조건 제출 완료'
            : dirty
            ? '아직 저장되지 않았어요 · 검토 후 제출'
            : '저장된 조건을 확인하고 있어요'}
        </Text>
        <View style={ui.row}>
          <View style={ui.flex}>
            {!locked && (
              <Button
                testID={preview ? 'submit-conditions' : 'preview-change'}
                title={
                  app.busy ||
                  (preview
                    ? me.submitted === false
                      ? '조건 제출하기'
                      : '변경 적용 · 재조율 시작'
                    : '조건 미리보기')
                }
                disabled={
                  !!app.busy ||
                  !dirty ||
                  (!!draft.aiDraftId && !draft.ambiguitiesResolved)
                }
                onPress={() => {
                  Keyboard.dismiss();
                  if (preview) {
                    void app.apply(draft, preview.revision).then(ok => {
                      if (ok) {
                        setPreview(null);
                        setSaved(true);
                        scroll.current?.scrollTo({ y: 0, animated: true });
                      }
                    });
                  } else {
                    void app.preview(draft).then(result => {
                      if (result) {
                        revealPreview.current = true;
                        setPreview(result);
                      }
                    });
                  }
                }}
              />
            )}
          </View>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}
