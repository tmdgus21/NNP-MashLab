import React, { useState } from 'react';
import {
  Keyboard,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { AuthTextInput } from '../components/AuthTextInput';
import { potatoColors } from '../theme/colors';
import type {
  AppointmentCreationDraft,
  AppointmentCreationStep1Values,
} from '../types/appointmentCreation';

interface CreateAppointmentStep1ScreenProps {
  draft: AppointmentCreationDraft;
  onDraftChange: (draft: AppointmentCreationDraft) => void;
  onCancelClick: () => void;
  onBackClick: () => void;
  onRequestStep2: (values: AppointmentCreationStep1Values) => void;
}

const steps = [
  { number: '1', title: '모임 정보' },
  { number: '2', title: '친구 초대' },
  { number: '3', title: '나의 시간' },
  { number: '4', title: '시간 조율' },
] as const;

const fields = [
  {
    key: 'title',
    label: '모임 이름',
    placeholder: '예) 친구들과 저녁 모임',
    accessibilityLabel: '모임 이름',
    autoCapitalize: 'sentences' as const,
  },
  {
    key: 'category',
    label: '무엇을 할까요?',
    placeholder: '예) 식사, 카페, 스터디',
    accessibilityLabel: '무엇을 할까요?',
    autoCapitalize: 'sentences' as const,
  },
  {
    key: 'duration',
    label: '예상 소요시간',
    placeholder: '예) 2시간',
    accessibilityLabel: '예상 소요시간',
    autoCapitalize: 'sentences' as const,
  },
  {
    key: 'location',
    label: '장소',
    placeholder: '장소를 입력해주세요',
    accessibilityLabel: '장소',
    autoCapitalize: 'sentences' as const,
  },
] as const;

type Step1Field = keyof AppointmentCreationStep1Values;

function isStep1Values(
  draft: AppointmentCreationDraft,
): draft is AppointmentCreationDraft & AppointmentCreationStep1Values {
  return (
    typeof draft.title === 'string' &&
    typeof draft.category === 'string' &&
    typeof draft.duration === 'string' &&
    typeof draft.location === 'string' &&
    draft.title.trim().length > 0 &&
    draft.category.trim().length > 0 &&
    draft.duration.trim().length > 0 &&
    draft.location.trim().length > 0
  );
}

export function CreateAppointmentStep1Screen({
  draft,
  onDraftChange,
  onCancelClick,
  onBackClick,
  onRequestStep2,
}: CreateAppointmentStep1ScreenProps) {
  const [error, setError] = useState('');

  const changeField = (field: Step1Field, value: string) => {
    const updatedDraft: AppointmentCreationDraft = {
      ...draft,
      [field]: value,
    };
    onDraftChange(updatedDraft);
    if (error) {
      setError('');
    }
  };

  const continueToStep2 = () => {
    Keyboard.dismiss();
    if (!isStep1Values(draft)) {
      setError('모임 이름, 활동, 예상 소요시간, 장소를 모두 입력해주세요.');
      return;
    }

    setError('');
    onRequestStep2({
      title: draft.title,
      category: draft.category,
      duration: draft.duration,
      location: draft.location,
    });
  };

  return (
    <SafeAreaView
      edges={['top', 'left', 'right']}
      style={styles.safeArea}
    >
      <View style={styles.header}>
        <Pressable
          accessibilityLabel="이전 화면"
          accessibilityRole="button"
          hitSlop={8}
          onPress={onBackClick}
          style={styles.backButton}
        >
          <Text style={styles.backArrow}>〈</Text>
        </Pressable>
        <Text style={styles.wordmark}>
          <Text style={styles.wordmarkPotato}>potato </Text>
          <Text style={styles.wordmarkMeet}>meet</Text>
        </Text>
      </View>

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.stepIndicator}>
          {steps.map(step => {
            const active = step.number === '1';
            return (
              <View
                accessibilityLabel={`${step.number}단계 ${step.title}${active ? ', 현재 단계' : ''}`}
                key={step.number}
                style={styles.stepItem}
              >
                <View
                  style={[
                    styles.stepNumber,
                    active
                      ? styles.activeStepNumber
                      : styles.inactiveStepNumber,
                  ]}
                >
                  <Text
                    style={[
                      styles.stepNumberText,
                      active
                        ? styles.activeStepNumberText
                        : styles.inactiveStepNumberText,
                    ]}
                  >
                    {step.number}
                  </Text>
                </View>
                <Text
                  style={[
                    styles.stepTitle,
                    active ? styles.activeStepTitle : styles.inactiveStepTitle,
                  ]}
                >
                  {step.title}
                </Text>
              </View>
            );
          })}
        </View>

        <View style={styles.formCard}>
          <Text style={styles.formTitle}>모임 정보</Text>
          {fields.map((field, index) => (
            <View
              key={field.key}
              style={index === 0 ? styles.firstField : styles.field}
            >
              <Text style={styles.fieldLabel}>{field.label}</Text>
              <AuthTextInput
                accessibilityLabel={field.accessibilityLabel}
                autoCapitalize={field.autoCapitalize}
                containerStyle={styles.inputContainer}
                onChangeText={value => changeField(field.key, value)}
                placeholder={field.placeholder}
                returnKeyType={index === fields.length - 1 ? 'done' : 'next'}
                value={draft[field.key] ?? ''}
              />
            </View>
          ))}
          {!!error && (
            <Text accessibilityLiveRegion="assertive" style={styles.error}>
              {error}
            </Text>
          )}
        </View>
      </ScrollView>

      <View style={styles.footer}>
        <Pressable
          accessibilityRole="button"
          onPress={onCancelClick}
          style={({ pressed }) => [
            styles.cancelButton,
            pressed && styles.pressed,
          ]}
        >
          <Text style={styles.cancelText}>취소</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          onPress={continueToStep2}
          style={({ pressed }) => [
            styles.nextButton,
            pressed && styles.pressed,
          ]}
        >
          <Text style={styles.nextText}>다음</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: potatoColors.background,
  },
  header: {
    minHeight: 52,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 8,
    backgroundColor: potatoColors.background,
  },
  backButton: {
    marginRight: 12,
    paddingVertical: 4,
  },
  backArrow: {
    color: potatoColors.text,
    fontSize: 22,
    fontWeight: '700',
  },
  wordmark: {
    fontSize: 24,
    fontWeight: '800',
  },
  wordmarkPotato: {
    color: potatoColors.brown,
  },
  wordmarkMeet: {
    color: potatoColors.orange,
  },
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: 20,
    paddingBottom: 16,
  },
  stepIndicator: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'flex-start',
    marginTop: 8,
    marginBottom: 20,
  },
  stepItem: {
    minWidth: 62,
    alignItems: 'center',
  },
  stepNumber: {
    width: 26,
    height: 26,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 13,
  },
  activeStepNumber: {
    backgroundColor: potatoColors.accentLight,
  },
  inactiveStepNumber: {
    backgroundColor: '#E0E0E0',
  },
  stepNumberText: {
    fontSize: 11,
    fontWeight: '700',
  },
  activeStepNumberText: {
    color: '#3C1E1E',
  },
  inactiveStepNumberText: {
    color: potatoColors.muted,
  },
  stepTitle: {
    marginTop: 4,
  },
  activeStepTitle: {
    color: potatoColors.text,
    fontSize: 12,
    fontWeight: '700',
  },
  inactiveStepTitle: {
    color: potatoColors.placeholder,
    fontSize: 10,
  },
  formCard: {
    padding: 20,
    borderRadius: 20,
    backgroundColor: potatoColors.white,
    elevation: 2,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 3,
  },
  formTitle: {
    marginBottom: 16,
    color: potatoColors.text,
    fontSize: 18,
    fontWeight: '700',
  },
  firstField: {
    marginTop: 0,
  },
  field: {
    marginTop: 12,
  },
  fieldLabel: {
    marginBottom: 6,
    color: '#555555',
    fontSize: 13,
    fontWeight: '700',
  },
  inputContainer: {
    height: 48,
    borderRadius: 12,
  },
  error: {
    marginTop: 12,
    color: '#B33D46',
    fontSize: 13,
    lineHeight: 19,
  },
  footer: {
    flexDirection: 'row',
    gap: 10,
    paddingHorizontal: 20,
    paddingVertical: 12,
    backgroundColor: potatoColors.background,
  },
  cancelButton: {
    minWidth: 76,
    height: 52,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 16,
    borderWidth: 1,
    borderColor: potatoColors.border,
    borderRadius: 26,
    backgroundColor: potatoColors.white,
  },
  cancelText: {
    color: potatoColors.muted,
    fontSize: 15,
    fontWeight: '700',
  },
  nextButton: {
    flex: 1,
    height: 52,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 26,
    backgroundColor: potatoColors.accentLight,
  },
  nextText: {
    color: '#3C1E1E',
    fontSize: 16,
    fontWeight: '700',
  },
  pressed: {
    opacity: 0.8,
  },
});
