import React, { useMemo, useRef, useState } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { SwipableCalendarWidget } from '../components/SwipableCalendarWidget';
import { potatoColors } from '../theme/colors';
import {
  formatDateKey,
  formatTimeMinutes,
  isValidDateKey,
  mergeAppointmentTimeSlots,
  parseTimeRange,
  splitTimeMinutes,
} from '../services/appointmentTime';
import type { PotatoAppointment } from '../types/appointment';
import type {
  AppointmentCreationDraft,
  AppointmentCreationTimeInput,
  AppointmentCreationTimeSlot,
} from '../types/appointmentCreation';

interface CreateAppointmentStep3TimeScreenProps {
  appointments?: readonly PotatoAppointment[];
  draft: AppointmentCreationDraft;
  onDraftChange: (draft: AppointmentCreationDraft) => void;
  onBack: () => void;
  onRequestStep4: (draft: AppointmentCreationDraft) => void;
}

const steps = [
  { number: '1', title: '모임 정보' },
  { number: '2', title: '친구 초대' },
  { number: '3', title: '나의 시간' },
  { number: '4', title: '시간 조율' },
] as const;

type TimeInputField = keyof AppointmentCreationTimeInput;

function currentTimeInput(): AppointmentCreationTimeInput {
  const now = new Date();
  const startTime = Math.floor(now.getMinutes() / 10) * 10 + now.getHours() * 60;
  const endTime = Math.min(startTime + 120, 24 * 60);
  const start = splitTimeMinutes(startTime);
  const end = splitTimeMinutes(endTime);
  return {
    startHour: start.hour,
    startMinute: start.minute,
    endHour: end.hour,
    endMinute: end.minute,
  };
}

function getSelectedDate(draft: AppointmentCreationDraft): string {
  if (draft.selectedCalendarDate && isValidDateKey(draft.selectedCalendarDate)) {
    return draft.selectedCalendarDate;
  }
  const now = new Date();
  return formatDateKey(now.getFullYear(), now.getMonth() + 1, now.getDate());
}

function dateLabel(date: string): string {
  const [year, month, day] = date.split('-').map(Number);
  return `${year}년 ${month}월 ${day}일`;
}

function updateSlot(
  slots: readonly AppointmentCreationTimeSlot[],
  editingId: string | undefined,
  updated: AppointmentCreationTimeSlot,
): AppointmentCreationTimeSlot[] {
  const next = editingId
    ? slots.map(slot => (slot.id === editingId ? updated : slot))
    : [...slots, updated];
  return mergeAppointmentTimeSlots(next);
}

export function CreateAppointmentStep3TimeScreen({
  appointments = [],
  draft,
  onDraftChange,
  onBack,
  onRequestStep4,
}: CreateAppointmentStep3TimeScreenProps) {
  const [error, setError] = useState('');
  const idCounter = useRef(0);
  const selectedDate = getSelectedDate(draft);
  const [selectedYear, selectedMonth, selectedDay] = selectedDate
    .split('-')
    .map(Number);
  const timeInput = draft.timeInput ?? currentTimeInput();

  const markedDates = useMemo(
    () =>
      new Set([
        ...(draft.timeSlots ?? []).map(slot => slot.date),
        ...appointments
          .map(appointment => appointment.date)
          .filter(isValidDateKey),
      ]),
    [appointments, draft.timeSlots],
  );

  const changeDate = (year: number, month: number, day: number) => {
    onDraftChange({
      ...draft,
      selectedCalendarDate: formatDateKey(year, month, day),
      editingTimeSlotId: undefined,
    });
    setError('');
  };

  const changeMonth = (year: number, month: number) => {
    const lastDay = new Date(year, month, 0).getDate();
    changeDate(year, month, Math.min(selectedDay, lastDay));
  };

  const changeTimeInput = (field: TimeInputField, value: string) => {
    if (value !== '' && !/^\d{0,2}$/.test(value)) {
      return;
    }
    onDraftChange({
      ...draft,
      timeInput: {
        ...timeInput,
        [field]: value,
      },
    });
    if (error) {
      setError('');
    }
  };

  const validateCurrentInput = () => {
    if (!isValidDateKey(selectedDate)) {
      return { valid: false as const, message: '올바른 날짜를 선택해주세요.' };
    }
    return parseTimeRange(
      timeInput.startHour,
      timeInput.startMinute,
      timeInput.endHour,
      timeInput.endMinute,
    );
  };

  const saveTimeSlot = () => {
    const result = validateCurrentInput();
    if (!result.valid) {
      setError(result.message);
      return;
    }

    const editingId = draft.editingTimeSlotId;
    const slot: AppointmentCreationTimeSlot = {
      id: editingId ?? `time-slot-${Date.now()}-${idCounter.current++}`,
      date: selectedDate,
      ...result.value,
    };
    onDraftChange({
      ...draft,
      timeSlots: updateSlot(draft.timeSlots ?? [], editingId, slot),
      editingTimeSlotId: undefined,
    });
    setError('');
  };

  const editTimeSlot = (slot: AppointmentCreationTimeSlot) => {
    const start = splitTimeMinutes(slot.startTimeMinutes);
    const end = splitTimeMinutes(slot.endTimeMinutes);
    onDraftChange({
      ...draft,
      selectedCalendarDate: slot.date,
      editingTimeSlotId: slot.id,
      timeInput: {
        startHour: start.hour,
        startMinute: start.minute,
        endHour: end.hour,
        endMinute: end.minute,
      },
    });
    setError('');
  };

  const cancelEdit = () => {
    onDraftChange({ ...draft, editingTimeSlotId: undefined });
    setError('');
  };

  const deleteTimeSlot = (id: string) => {
    const nextDraft: AppointmentCreationDraft = {
      ...draft,
      timeSlots: (draft.timeSlots ?? []).filter(slot => slot.id !== id),
      editingTimeSlotId:
        draft.editingTimeSlotId === id ? undefined : draft.editingTimeSlotId,
    };
    onDraftChange(nextDraft);
    setError('');
  };

  const continueToStep4 = () => {
    const result = validateCurrentInput();
    if (!result.valid) {
      setError(result.message);
      return;
    }

    const editingId = draft.editingTimeSlotId;
    const nextSlot: AppointmentCreationTimeSlot = {
      id: editingId ?? `time-slot-${Date.now()}-${idCounter.current++}`,
      date: selectedDate,
      ...result.value,
    };
    const nextDraft: AppointmentCreationDraft = {
      ...draft,
      timeSlots: updateSlot(draft.timeSlots ?? [], editingId, nextSlot),
      editingTimeSlotId: undefined,
    };
    onDraftChange(nextDraft);
    setError('');
    onRequestStep4(nextDraft);
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={styles.safeArea}>
      <View style={styles.header}>
        <Pressable
          accessibilityLabel="이전 단계"
          accessibilityRole="button"
          hitSlop={8}
          onPress={onBack}
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
            const active = step.number === '3';
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

        <View style={styles.calendarCard}>
          <SwipableCalendarWidget
            year={selectedYear}
            month={selectedMonth}
            selectedDay={selectedDay}
            markedDates={markedDates}
            onMonthChange={changeMonth}
            onDayChange={changeDate}
          />
        </View>

        <View style={styles.timeCard}>
          <Text style={styles.sectionTitle}>나의 가능한 시간</Text>
          <Text style={styles.selectedDate}>{dateLabel(selectedDate)}</Text>
          <View style={styles.timeFields}>
            <TimePartInput
              label="시작 시"
              value={timeInput.startHour}
              onChangeText={value => changeTimeInput('startHour', value)}
            />
            <Text style={styles.timeColon}>:</Text>
            <TimePartInput
              label="시작 분"
              value={timeInput.startMinute}
              onChangeText={value => changeTimeInput('startMinute', value)}
            />
            <Text style={styles.rangeSeparator}>~</Text>
            <TimePartInput
              label="종료 시"
              value={timeInput.endHour}
              onChangeText={value => changeTimeInput('endHour', value)}
            />
            <Text style={styles.timeColon}>:</Text>
            <TimePartInput
              label="종료 분"
              value={timeInput.endMinute}
              onChangeText={value => changeTimeInput('endMinute', value)}
            />
            <Pressable
              accessibilityLabel={
                draft.editingTimeSlotId ? '시간 수정' : '시간 추가'
              }
              accessibilityRole="button"
              onPress={saveTimeSlot}
              style={({ pressed }) => [
                styles.addButton,
                pressed && styles.pressed,
              ]}
            >
              <Text style={styles.addButtonText}>
                {draft.editingTimeSlotId ? '✓' : '+'}
              </Text>
            </Pressable>
          </View>
          {!!draft.editingTimeSlotId && (
            <Pressable
              accessibilityRole="button"
              onPress={cancelEdit}
              style={styles.cancelEdit}
            >
              <Text style={styles.cancelEditText}>수정 취소</Text>
            </Pressable>
          )}
          {!!error && (
            <Text accessibilityLiveRegion="assertive" style={styles.error}>
              {error}
            </Text>
          )}
        </View>

        <View style={styles.slotSection}>
          <Text style={styles.sectionTitle}>선택한 시간</Text>
          {(draft.timeSlots ?? []).length === 0 ? (
            <View style={styles.emptySlots}>
              <Text style={styles.emptyText}>
                날짜와 시간을 선택해 추가해주세요.
              </Text>
            </View>
          ) : (
            (draft.timeSlots ?? []).map(slot => {
              const editing = slot.id === draft.editingTimeSlotId;
              return (
                <View
                  key={slot.id}
                  style={[
                    styles.slotRow,
                    editing && styles.editingSlotRow,
                  ]}
                >
                  <View style={styles.slotTextContainer}>
                    <Text style={styles.slotDate}>{dateLabel(slot.date)}</Text>
                    <Text style={styles.slotTime}>
                      {formatTimeMinutes(slot.startTimeMinutes)} ~{' '}
                      {formatTimeMinutes(slot.endTimeMinutes)}
                    </Text>
                  </View>
                  <Pressable
                    accessibilityLabel={`${dateLabel(slot.date)} ${formatTimeMinutes(slot.startTimeMinutes)} 시간 수정`}
                    accessibilityRole="button"
                    onPress={() => editTimeSlot(slot)}
                    style={styles.slotAction}
                  >
                    <Text style={styles.editText}>수정</Text>
                  </Pressable>
                  <Pressable
                    accessibilityLabel={`${dateLabel(slot.date)} ${formatTimeMinutes(slot.startTimeMinutes)} 시간 삭제`}
                    accessibilityRole="button"
                    onPress={() => deleteTimeSlot(slot.id)}
                    style={styles.slotAction}
                  >
                    <Text style={styles.deleteText}>삭제</Text>
                  </Pressable>
                </View>
              );
            })
          )}
        </View>
      </ScrollView>

      <View style={styles.footer}>
        <Pressable
          accessibilityRole="button"
          onPress={onBack}
          style={({ pressed }) => [
            styles.backAction,
            pressed && styles.pressed,
          ]}
        >
          <Text style={styles.backActionText}>이전</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          onPress={continueToStep4}
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

interface TimePartInputProps {
  label: string;
  value: string;
  onChangeText: (value: string) => void;
}

function TimePartInput({ label, value, onChangeText }: TimePartInputProps) {
  return (
    <TextInput
      accessibilityLabel={label}
      keyboardType="number-pad"
      maxLength={2}
      onChangeText={onChangeText}
      placeholder="00"
      placeholderTextColor={potatoColors.placeholder}
      returnKeyType="done"
      selectTextOnFocus
      style={styles.timePartInput}
      value={value}
    />
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
  calendarCard: {
    padding: 16,
    borderRadius: 18,
    backgroundColor: potatoColors.white,
    elevation: 2,
  },
  timeCard: {
    marginTop: 16,
    padding: 16,
    borderRadius: 16,
    backgroundColor: potatoColors.white,
    elevation: 1,
  },
  sectionTitle: {
    color: potatoColors.text,
    fontSize: 16,
    fontWeight: '700',
  },
  selectedDate: {
    marginTop: 6,
    marginBottom: 12,
    color: potatoColors.muted,
    fontSize: 13,
  },
  timeFields: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: '#FFE082',
    borderRadius: 12,
  },
  timePartInput: {
    width: 36,
    height: 40,
    padding: 0,
    borderRadius: 8,
    backgroundColor: '#FFFDF9',
    color: potatoColors.text,
    fontSize: 14,
    fontWeight: '700',
    textAlign: 'center',
  },
  timeColon: {
    color: potatoColors.text,
    fontSize: 14,
    fontWeight: '700',
  },
  rangeSeparator: {
    marginHorizontal: 2,
    color: potatoColors.text,
    fontSize: 13,
    fontWeight: '700',
  },
  addButton: {
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: 2,
    borderRadius: 10,
    backgroundColor: potatoColors.accentLight,
  },
  addButtonText: {
    color: '#3C1E1E',
    fontSize: 20,
    fontWeight: '700',
  },
  pressed: {
    opacity: 0.8,
  },
  cancelEdit: {
    alignSelf: 'flex-end',
    paddingTop: 8,
  },
  cancelEditText: {
    color: potatoColors.muted,
    fontSize: 12,
  },
  error: {
    marginTop: 10,
    color: '#B33D46',
    fontSize: 13,
    lineHeight: 19,
  },
  slotSection: {
    marginTop: 16,
    gap: 8,
  },
  emptySlots: {
    minHeight: 60,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 12,
    backgroundColor: potatoColors.white,
  },
  emptyText: {
    color: potatoColors.placeholder,
    fontSize: 13,
  },
  slotRow: {
    minHeight: 58,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: '#FFE082',
    borderRadius: 12,
    backgroundColor: potatoColors.white,
  },
  editingSlotRow: {
    borderColor: potatoColors.orange,
  },
  slotTextContainer: {
    flex: 1,
    minWidth: 0,
  },
  slotDate: {
    color: potatoColors.text,
    fontSize: 12,
    fontWeight: '700',
  },
  slotTime: {
    marginTop: 2,
    color: '#555555',
    fontSize: 14,
    fontWeight: '700',
  },
  slotAction: {
    marginLeft: 8,
    paddingHorizontal: 4,
    paddingVertical: 8,
  },
  editText: {
    color: potatoColors.orange,
    fontSize: 12,
    fontWeight: '700',
  },
  deleteText: {
    color: '#B33D46',
    fontSize: 12,
    fontWeight: '700',
  },
  footer: {
    flexDirection: 'row',
    gap: 10,
    paddingHorizontal: 20,
    paddingVertical: 12,
    backgroundColor: potatoColors.background,
  },
  backAction: {
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
  backActionText: {
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
});
