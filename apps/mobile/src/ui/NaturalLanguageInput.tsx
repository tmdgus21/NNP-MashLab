import React, { useState } from 'react';
import { Text, View } from 'react-native';
import { Conditions, ParseResult } from '../domain/model';
import { Button, Field, StatusCard } from './components';
import { ui } from './theme';

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
        자연어는 조건 초안으로만 제안돼요. 아래 입력에 반영한 뒤 직접
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
          title={result.source === 'mock' ? '데모 조건 초안' : '조건 초안'}
          detail={result.questions.join('\n')}
        >
          <Text style={ui.text}>
            선호:{' '}
            {result.draft.preference === 'early'
              ? '이른 시간'
              : result.draft.preference === 'late'
              ? '늦은 시간'
              : '변경 없음'}
          </Text>
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
