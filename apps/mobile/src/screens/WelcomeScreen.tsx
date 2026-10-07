import React, { useState } from 'react';
import { KeyboardAvoidingView, ScrollView, Text, View } from 'react-native';
import { useApp } from '../state/store';
import { parseTime } from '../domain/time';
import { Button, Chip, Field, StatusCard } from '../ui/components';
import { colors, ui } from '../ui/theme';
import { repository } from '../data/repositoryInstance';
export function WelcomeScreen() {
  const app = useApp();
  const [mode, setMode] = useState<'create' | 'join'>('create');
  const [name, setName] = useState('');
  const [title, setTitle] = useState('');
  const [code, setCode] = useState('');
  const [dates, setDates] = useState('2026-10-17, 2026-10-18');
  const [roles, setRoles] = useState('진행, 기록, 촬영');
  const [start, setStart] = useState('09:00');
  const [end, setEnd] = useState('18:00');
  const [duration, setDuration] = useState('60');
  const [error, setError] = useState('');
  const create = () => {
    try {
      setError('');
      void app.create({
        name,
        title,
        dates: dates
          .split(',')
          .map(v => v.trim())
          .filter(Boolean),
        roles: roles
          .split(',')
          .map(v => v.trim())
          .filter(Boolean),
        duration: Number(duration),
        windowStart: parseTime(start),
        windowEnd: parseTime(end),
      });
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <KeyboardAvoidingView style={ui.flex} behavior="height">
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={ui.content}
      >
        <View
          style={[
            ui.card,
            {
              backgroundColor: colors.primary,
              borderWidth: 0,
              padding: 24,
              gap: 16,
            },
          ]}
        >
          <Text style={[ui.eyebrow, { color: '#AEE0D2' }]}>CONDITIONAL OK</Text>
          <Text style={[ui.title, { color: colors.white, fontSize: 32 }]}>
            우리 모두의 조건,{'\n'}하나의 좋은 일정.
          </Text>
          <Text style={{ color: '#D9EFE8', lineHeight: 22 }}>
            가능한 시간과 역할을 모으면{'\n'}함께 동의할 수 있는 담당표가
            만들어져요.
          </Text>
        </View>
        <View style={ui.row}>
          <Chip
            title="모임 만들기"
            selected={mode === 'create'}
            onPress={() => setMode('create')}
          />
          <Chip
            title="코드로 참가"
            selected={mode === 'join'}
            onPress={() => setMode('join')}
          />
        </View>
        <View style={ui.card}>
          <Text style={ui.heading}>
            {mode === 'create' ? '새로운 조율 시작' : '초대받은 모임에 참가'}
          </Text>
          <Field
            label="내 이름"
            value={name}
            onChangeText={setName}
            placeholder="참가자에게 보여줄 이름"
            maxLength={20}
          />
          {mode === 'create' ? (
            <>
              <Field
                label="모임 이름"
                value={title}
                onChangeText={setTitle}
                placeholder="예: 주말 프로젝트 모임"
                maxLength={60}
              />
              <Field
                label="후보 날짜 (쉼표로 구분)"
                value={dates}
                onChangeText={setDates}
                placeholder="YYYY-MM-DD"
              />
              <Field
                label="필요한 역할 (역할마다 1명, 최대 6개)"
                value={roles}
                onChangeText={setRoles}
              />
              <View style={ui.row}>
                <View style={ui.flex}>
                  <Field
                    label="시작 HH:MM"
                    value={start}
                    onChangeText={setStart}
                  />
                </View>
                <View style={ui.flex}>
                  <Field label="종료 HH:MM" value={end} onChangeText={setEnd} />
                </View>
              </View>
              <Field
                label="함께 활동할 시간 (분, 30분 단위)"
                value={duration}
                onChangeText={setDuration}
                keyboardType="number-pad"
              />
              <Text style={ui.small}>
                Asia/Seoul · 후보 날짜 중 한 날의 같은 시간에 역할을 나누어요.
              </Text>
              <Button
                title="모임 만들고 조건 입력하기"
                onPress={create}
                disabled={!!app.busy}
              />
            </>
          ) : (
            <>
              <Field
                label="초대 코드"
                autoCapitalize="characters"
                value={code}
                onChangeText={setCode}
                placeholder="예: OK2026"
              />
              <Button
                title="모임 참가하기"
                onPress={() => {
                  void app.join(code, name);
                }}
                disabled={!!app.busy}
              />
            </>
          )}
        </View>
        {!!error && (
          <StatusCard
            title="입력을 확인해 주세요"
            detail={error}
            kind="error"
          />
        )}
        {repository.mode === 'mock' && (
          <View style={ui.card}>
            <Text style={ui.eyebrow}>MOCK DEMO</Text>
            <Text style={ui.heading}>먼저 4명의 모임을 둘러보세요</Text>
            <Text style={ui.muted}>
              서버 없이 생성 → 조건 → 합의 → 확정까지 체험할 수 있어요. 데모
              데이터는 이 기기에 저장됩니다.
            </Text>
            <Button
              testID="open-demo"
              title="데모 모임 체험하기"
              secondary
              onPress={() => {
                void app.scenario('feasible');
              }}
              disabled={!!app.busy}
            />
          </View>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
