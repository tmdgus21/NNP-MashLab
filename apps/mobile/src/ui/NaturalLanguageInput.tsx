import React, { useState } from 'react';
import { Text, View } from 'react-native';
import { Conditions, ParseResult } from '../domain/model';
import { Button, Field, StatusCard } from './components';
import { ui } from './theme';
import { timeLabel } from '../domain/time';

/** Independent parser port: AI proposes conditions only, never a schedule. */
export function NaturalLanguageInput({
  parse,
  onAccept,
  disabled,
}: {
  parse(text: string): Promise<ParseResult>;
  onAccept(draft: Partial<Conditions>): void;
  disabled?: boolean;
}) {
  const [text, setText] = useState('');
  const [result, setResult] = useState<ParseResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const submit = async () => {
    setBusy(true);
    setError('');
    setResult(null);
    try {
      setResult(await parse(text));
    } catch (e) {
      setError(e instanceof Error ? e.message : '해석에 실패했어요.');
    } finally {
      setBusy(false);
    }
  };
  return (
    <View style={ui.card}>
      <Text style={ui.heading}>말로 적는 추가 조건</Text>
      <Text style={ui.muted}>
        자연어는 조건 초안으로만 제안돼요. 입력에 반영한 뒤 검토 단계에서 직접
        확인하세요.
      </Text>
      <Field
        label="자연어 조건"
        maxLength={1000}
        placeholder="예: 오전이 좋고 서연과 함께할 수 있어요"
        multiline
        value={text}
        onChangeText={v => {
          setText(v);
          setResult(null);
        }}
        editable={!disabled}
      />
      <Button
        title={busy ? '조건을 해석하는 중…' : '조건 초안 확인'}
        onPress={() => {
          void submit();
        }}
        disabled={busy || disabled || !text.trim()}
        secondary
      />
      {!!error && (
        <StatusCard kind="error" title="해석하지 못했어요" detail={error} />
      )}
      {result && (
        <StatusCard
          title="AI 조건 초안 · 제출 전 확인"
          kind={result.questions.length ? 'warning' : 'info'}
          detail={
            result.questions.length
              ? `확인이 필요한 내용 ${
                  result.questions.length
                }개\n${result.questions.join('\n')}`
              : '입력에 반영한 뒤 각 단계에서 수정할 수 있어요. 반영만으로 서버에 제출되지 않습니다.'
          }
        >
          <Text style={ui.text}>
            선호:{' '}
            {result.draft.preference === 'early'
              ? '이른 시간'
              : result.draft.preference === 'late'
              ? '늦은 시간'
              : '변경 없음'}
          </Text>
          {result.draft.availability?.map((v, i) => (
            <Text key={`a${i}`} style={ui.text}>
              가능: {v.date} {timeLabel(v.start)}~{timeLabel(v.end)}
            </Text>
          ))}
          {result.draft.unavailable?.map((v, i) => (
            <Text key={`u${i}`} style={ui.text}>
              불가: {v.date} {timeLabel(v.start)}~{timeLabel(v.end)}
            </Text>
          ))}
          {!!result.draft.requiredRoles?.length && (
            <Text style={ui.text}>
              필수 역할: {result.draft.requiredRoles.join(', ')}
            </Text>
          )}
          {!!result.draft.rolePreferences?.length && (
            <Text style={ui.text}>
              선호 역할: {result.draft.rolePreferences.join(', ')}
            </Text>
          )}
          {!!result.draft.roleUnavailable?.length && (
            <Text style={ui.text}>
              불가 역할: {result.draft.roleUnavailable.join(', ')}
            </Text>
          )}
          {!!result.draft.companionRequirements?.length && (
            <Text style={ui.text}>
              동반 조건 {result.draft.companionRequirements.length}개 · 반영 후
              참가자와 강도를 확인하세요.
            </Text>
          )}
          {!!result.draft.timePreferences?.length && (
            <Text style={ui.text}>
              선호 시간 {result.draft.timePreferences.length}개 · 선호 시간
              탭에서 수정하세요.
            </Text>
          )}
          <Button
            title="초안을 내 입력에 반영"
            onPress={() => {
              onAccept(result.draft);
              setResult(null);
            }}
            disabled={disabled}
          />
        </StatusCard>
      )}
    </View>
  );
}
