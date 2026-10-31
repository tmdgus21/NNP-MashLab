import React, { useMemo, useState } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  type StyleProp,
  type TextStyle,
  type ViewStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { potatoColors } from '../theme/colors';
import {
  formatTimeMinutes,
  isValidDateKey,
  isValidAppointmentTimeSlot,
} from '../services/appointmentTime';
import {
  getAppointmentRecommendationMessage,
  prepareAppointmentAiRecommendation,
} from '../services/appointmentRecommendation';
import type {
  AppointmentCreationDraft,
  AppointmentCreationTimeSlot,
} from '../types/appointmentCreation';
import type {
  AppointmentAiRecommendationPreparation,
} from '../types/appointmentRecommendation';

interface CreateAppointmentStep4AdjustScreenProps {
  nickname?: string;
  draft: AppointmentCreationDraft;
  onBack: () => void;
  onNavigateStep: (step: 1 | 2 | 3) => void;
  onRequestAiRecommendation: (
    preparation: AppointmentAiRecommendationPreparation,
  ) => void;
}

interface InviteeDisplayRow {
  key: string;
  name: string;
  status: string;
  availability: 'submitted' | 'unsubmitted';
  slots: AppointmentCreationTimeSlot[];
}

const steps = [
  { number: 1, title: '정보' },
  { number: 2, title: '초대' },
  { number: 3, title: '나의 시간' },
  { number: 4, title: '시간 조율' },
] as const;

const TIMELINE_WIDTH = 600;

function getWeekdayLabel(date: string): string {
  const [year, month, day] = date.split('-').map(Number);
  const weekday = new Date(year, month - 1, day).getDay();
  return ['일', '월', '화', '수', '목', '금', '토'][weekday];
}

function getDateLabel(date: string): string {
  const [year, month, day] = date.split('-').map(Number);
  return `${year}년 ${month}월 ${day}일`;
}

export function CreateAppointmentStep4AdjustScreen({
  nickname = '',
  draft,
  onBack,
  onNavigateStep,
  onRequestAiRecommendation,
}: CreateAppointmentStep4AdjustScreenProps) {
  const preparation = useMemo(
    () => prepareAppointmentAiRecommendation(draft),
    [draft],
  );
  const displayName = nickname.trim() || '나';
  const slots = draft.timeSlots?.filter(isValidAppointmentTimeSlot) ?? [];
  const invitedFriendRows: InviteeDisplayRow[] =
    draft.invitedFriendIds !== undefined
      ? [
          ...draft.invitedFriendIds.map(id => {
            const participant = draft.participants?.find(
              item => item.id === id && item.role === 'invitee',
            );
            const submission = draft.availabilitySubmissions?.find(
              item => item.participantId === id,
            );
            const declined =
              participant?.role === 'invitee' &&
              participant.participationStatus === 'declined';
            const availabilitySubmitted =
              !declined &&
              participant?.role === 'invitee' &&
              participant.invitationStatus === 'sent' &&
              submission?.status === 'submitted';
            const status =
              participant?.role !== 'invitee' ||
              participant.invitationStatus === 'not_sent'
                ? '초대 미발송'
                : participant.participationStatus === 'pending'
                  ? '응답 대기'
                  : declined
                    ? '참여 거절'
                    : availabilitySubmitted
                      ? '시간 제출 완료'
                      : '시간 미제출';
            return {
              key: id,
              name: draft.invitedFriendNameById?.[id] ?? '초대 친구',
              status,
              availability: availabilitySubmitted
                ? ('submitted' as const)
                : ('unsubmitted' as const),
              slots:
                availabilitySubmitted &&
                submission?.status === 'submitted'
                  ? submission.timeSlots.filter(isValidAppointmentTimeSlot)
                  : [],
            };
          }),
          ...(draft.unresolvedInvitedFriendNames ?? []).map(
            (name, index) => ({
              key: `unresolved-${index}-${name}`,
              name,
              status: 'ID 확인 필요',
              availability: 'unsubmitted' as const,
              slots: [],
            }),
          ),
        ]
      : (draft.invitedFriends ?? []).map((name, index) => ({
          key: `legacy-${index}-${name}`,
          name,
          status: 'ID 확인 필요',
          availability: 'unsubmitted' as const,
          slots: [],
        }));
  const dates = [
    ...new Set([
      ...slots.map(slot => slot.date),
      ...invitedFriendRows.flatMap(friend =>
        friend.slots.map(slot => slot.date),
      ),
      ...(draft.selectedCalendarDate &&
      isValidDateKey(draft.selectedCalendarDate)
        ? [draft.selectedCalendarDate]
        : []),
    ]),
  ].sort();
  const [selectedDateState, setSelectedDateState] = useState<string | undefined>(
    () =>
      draft.selectedCalendarDate && isValidDateKey(draft.selectedCalendarDate)
        ? draft.selectedCalendarDate
        : slots[0]?.date ??
          invitedFriendRows.flatMap(friend =>
            friend.slots.map(slot => slot.date),
          )[0],
  );
  const selectedDate =
    selectedDateState && dates.includes(selectedDateState)
      ? selectedDateState
      : draft.selectedCalendarDate && dates.includes(draft.selectedCalendarDate)
        ? draft.selectedCalendarDate
        : dates[0];
  const selectedDateSlots = selectedDate
    ? slots.filter(slot => slot.date === selectedDate)
    : [];
  const selectedFriendRows = selectedDate
    ? invitedFriendRows.map(friend => ({
        ...friend,
        slots: friend.slots.filter(slot => slot.date === selectedDate),
      }))
    : invitedFriendRows;
  const hasSelectedFriendSlots = selectedFriendRows.some(
    friend => friend.slots.length > 0,
  );
  const hasSelectedDateAvailability =
    selectedDateSlots.length > 0 || hasSelectedFriendSlots;
  const headerLabel = selectedDate
    ? `${getDateLabel(selectedDate)} (${getWeekdayLabel(selectedDate)})`
    : '가능한 날짜가 없습니다';
  const hasInvitedFriends = invitedFriendRows.length > 0;
  const requestError = getAppointmentRecommendationMessage(preparation);
  const hasInvalidRecommendationInput =
    preparation.status === 'needs_information' &&
    preparation.invalidFields.length > 0;

  const requestRecommendation = () => {
    onRequestAiRecommendation(prepareAppointmentAiRecommendation(draft));
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right', 'bottom']} style={styles.safeArea}>
      <View style={styles.header}>
        <StepNavigationButton
          accessibilityLabel="이전 단계"
          label="〈"
          onPress={onBack}
          style={styles.backButton}
          textStyle={styles.backArrow}
        />
        <Text style={styles.wordmark}>
          <Text style={styles.wordmarkPotato}>potato </Text>
          <Text style={styles.wordmarkMeet}>meet</Text>
        </Text>
      </View>

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.stepIndicator}>
          {steps.map(step => {
            const active = step.number === 4;
            return (
              <StepNavigationButton
                accessibilityLabel={`${step.number}단계 ${step.title}`}
                key={step.number}
                label={step.number}
                onPress={() => {
                  if (
                    step.number === 1 ||
                    step.number === 2 ||
                    step.number === 3
                  ) {
                    onNavigateStep(step.number);
                  }
                }}
                style={styles.stepItem}
                textStyle={[
                  styles.stepNumberText,
                  active
                    ? styles.activeStepNumberText
                    : styles.inactiveStepNumberText,
                ]}
                indicatorStyle={[
                  styles.stepNumber,
                  active ? styles.activeStepNumber : styles.inactiveStepNumber,
                ]}
                caption={step.title}
                captionStyle={[
                  styles.stepTitle,
                  active
                    ? styles.activeStepTitle
                    : styles.inactiveStepTitle,
                ]}
                disabled={active}
              />
            );
          })}
        </View>

        <View style={styles.graphCard}>
          <View style={styles.graphHeader}>
            <Text style={styles.graphTitle}>{headerLabel}</Text>
            {hasSelectedDateAvailability && (
              <Text style={styles.graphHint}>그래프를 좌우로 밀어 확인</Text>
            )}
          </View>

          {dates.length > 0 && (
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.dateSelector}
            >
              {dates.map(date => {
                const selected = date === selectedDate;
                return (
                  <Pressable
                    accessibilityLabel={`${getDateLabel(date)} 날짜 선택`}
                    accessibilityRole="button"
                    accessibilityState={{ selected }}
                    key={date}
                    onPress={() => setSelectedDateState(date)}
                    style={[
                      styles.dateOption,
                      selected && styles.selectedDateOption,
                    ]}
                  >
                    <Text
                      style={[
                        styles.dateOptionText,
                        selected && styles.selectedDateOptionText,
                      ]}
                    >
                      {`${Number(date.slice(5, 7))}/${Number(date.slice(8, 10))} (${getWeekdayLabel(date)})`}
                    </Text>
                  </Pressable>
                );
              })}
            </ScrollView>
          )}

          {!hasSelectedDateAvailability ? (
            <View style={styles.emptyState}>
              <Text style={styles.emptyTitle}>
                {selectedDate
                  ? '이 날짜에 등록된 시간이 없습니다.'
                  : '등록된 시간이 없습니다.'}
              </Text>
              <Text style={styles.emptyDetail}>
                {selectedDate
                  ? 'STEP 3에서 이 날짜의 가능한 시간을 추가해주세요.'
                  : 'STEP 3에서 날짜와 가능한 시간을 추가해주세요.'}
              </Text>
              {hasInvitedFriends && (
                <Text style={styles.emptyDetail}>
                  초대 친구는 아직 가능한 시간을 제출하지 않았습니다.
                </Text>
              )}
            </View>
          ) : (
            <View style={styles.chart}>
              <View style={styles.memberColumn}>
                <View style={styles.memberHeader}>
                  <Text style={styles.memberHeaderText}>이름</Text>
                </View>
                <MemberLabel name={displayName} />
                {selectedFriendRows.map(friend => (
                  <MemberLabel
                    key={friend.key}
                    name={friend.name}
                    status={friend.status}
                  />
                ))}
              </View>

              <ScrollView
                horizontal
                nestedScrollEnabled
                showsHorizontalScrollIndicator
                style={styles.timelineScroll}
              >
                <View>
                  <View style={styles.hourLabels}>
                    {Array.from({ length: 13 }, (_, index) => index * 2).map(
                      hour => (
                        <Text
                          key={hour}
                          style={[
                            styles.hourLabel,
                            {
                              left: (hour / 24) * TIMELINE_WIDTH,
                              marginLeft:
                                hour === 0 ? 0 : hour === 24 ? -50 : -25,
                              textAlign:
                                hour === 0
                                  ? 'left'
                                  : hour === 24
                                    ? 'right'
                                    : 'center',
                            },
                          ]}
                        >
                          {hour}시
                        </Text>
                      ),
                    )}
                  </View>
                  <View style={styles.hourRows}>
                    <AvailabilityRow
                      availability="self"
                      slots={selectedDateSlots}
                    />
                    {selectedFriendRows.map(friend => (
                      <AvailabilityRow
                        key={friend.key}
                        availability={
                          friend.availability === 'submitted'
                            ? 'friend_submitted'
                            : 'unsubmitted'
                        }
                        slots={friend.slots}
                      />
                    ))}
                  </View>
                </View>
              </ScrollView>
            </View>
          )}

          <View style={styles.legend}>
            <LegendItem color="#81C784" label="내 가능 시간" />
            <LegendItem color="#F5F5F5" label="내 불가" />
            {invitedFriendRows.some(row => row.availability === 'submitted') && (
              <LegendItem color="#81C784" label="친구 제출 가능 시간" />
            )}
            {hasInvitedFriends && (
              <LegendItem color="#E0E0E0" label="친구 일정 미제출" />
            )}
          </View>
          {selectedDateSlots.length > 0 && (
            <View style={styles.exactTimes}>
              <Text style={styles.exactTimesTitle}>내 가능 시간</Text>
              {selectedDateSlots.map(slot => (
                <Text
                  accessibilityLabel={`${formatTimeMinutes(slot.startTimeMinutes)}부터 ${formatTimeMinutes(slot.endTimeMinutes)}까지`}
                  key={slot.id}
                  style={styles.exactTime}
                >
                  {formatTimeMinutes(slot.startTimeMinutes)} ~{' '}
                  {formatTimeMinutes(slot.endTimeMinutes)}
                </Text>
              ))}
            </View>
          )}
          {selectedFriendRows
            .filter(friend => friend.slots.length > 0)
            .map(friend => (
              <View key={`exact-${friend.key}`} style={styles.exactTimes}>
                <Text style={styles.exactTimesTitle}>
                  {friend.name} 가능 시간
                </Text>
                {friend.slots.map(slot => (
                  <Text
                    accessibilityLabel={`${friend.name} ${formatTimeMinutes(slot.startTimeMinutes)}부터 ${formatTimeMinutes(slot.endTimeMinutes)}까지`}
                    key={slot.id}
                    style={styles.exactTime}
                  >
                    {formatTimeMinutes(slot.startTimeMinutes)} ~{' '}
                    {formatTimeMinutes(slot.endTimeMinutes)}
                  </Text>
                ))}
              </View>
            ))}
        </View>

        {!!requestError &&
          (hasSelectedDateAvailability || hasInvalidRecommendationInput) && (
            <Text accessibilityLiveRegion="polite" style={styles.error}>
              {requestError}
            </Text>
          )}
      </ScrollView>

      <View style={styles.footer}>
        <StepNavigationButton
          label="이전"
          onPress={onBack}
          style={styles.previousButton}
          textStyle={styles.previousText}
        />
        <StepNavigationButton
          label="AI 조율"
          onPress={requestRecommendation}
          style={styles.aiButton}
          textStyle={styles.aiButtonText}
        />
      </View>
    </SafeAreaView>
  );
}

interface StepNavigationButtonProps {
  label: string | number;
  onPress: () => void;
  style?: StyleProp<ViewStyle>;
  textStyle?: StyleProp<TextStyle>;
  indicatorStyle?: StyleProp<ViewStyle>;
  caption?: string;
  captionStyle?: StyleProp<TextStyle>;
  accessibilityLabel?: string;
  disabled?: boolean;
}

function StepNavigationButton({
  label,
  onPress,
  style,
  textStyle,
  indicatorStyle,
  caption,
  captionStyle,
  accessibilityLabel,
  disabled = false,
}: StepNavigationButtonProps) {
  return (
    <Pressable
      accessibilityLabel={accessibilityLabel}
      accessibilityRole="button"
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      style={style}
    >
      {indicatorStyle ? (
        <View style={indicatorStyle}>
          <Text style={textStyle}>{label}</Text>
        </View>
      ) : (
        <Text style={textStyle}>{label}</Text>
      )}
      {!!caption && <Text style={captionStyle}>{caption}</Text>}
    </Pressable>
  );
}

interface MemberLabelProps {
  name: string;
  status?: string;
}

function MemberLabel({ name, status }: MemberLabelProps) {
  return (
    <View style={styles.memberLabel}>
      <View style={styles.avatar}>
        <Text style={styles.avatarText}>{name.slice(0, 1)}</Text>
      </View>
      <Text numberOfLines={1} style={styles.memberName}>
        {name}
      </Text>
      {!!status && <Text style={styles.memberStatus}>{status}</Text>}
    </View>
  );
}

interface AvailabilityRowProps {
  availability: 'self' | 'friend_submitted' | 'unsubmitted';
  slots: readonly AppointmentCreationTimeSlot[];
}

function AvailabilityRow({
  availability,
  slots,
}: AvailabilityRowProps) {
  return (
    <View
      accessible
      accessibilityLabel={
        availability === 'unsubmitted'
          ? '친구 가능 시간 미제출'
          : availability === 'friend_submitted'
            ? '친구가 제출한 가능 시간'
            : '내 시간대'
      }
      style={[
        styles.availabilityRow,
        availability === 'unsubmitted' && styles.unsubmittedRow,
      ]}
    >
      {availability !== 'unsubmitted' &&
        slots.map(slot => {
          const left =
            (slot.startTimeMinutes / (24 * 60)) * TIMELINE_WIDTH;
          const width =
            ((slot.endTimeMinutes - slot.startTimeMinutes) / (24 * 60)) *
            TIMELINE_WIDTH;
          return (
            <View
              accessibilityLabel={`${formatTimeMinutes(slot.startTimeMinutes)}부터 ${formatTimeMinutes(slot.endTimeMinutes)}까지 가능`}
              accessible
              key={slot.id}
              testID="time-segment"
              style={[styles.timeSegment, { left, width }]}
            />
          );
        })}
    </View>
  );
}

interface LegendItemProps {
  color: string;
  label: string;
}

function LegendItem({ color, label }: LegendItemProps) {
  return (
    <View style={styles.legendItem}>
      <View style={[styles.legendSwatch, { backgroundColor: color }]} />
      <Text style={styles.legendLabel}>{label}</Text>
    </View>
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
  graphCard: {
    padding: 16,
    borderRadius: 20,
    backgroundColor: potatoColors.white,
    elevation: 2,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 3,
  },
  graphHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  graphTitle: {
    flexShrink: 1,
    color: potatoColors.text,
    fontSize: 18,
    fontWeight: '700',
  },
  graphHint: {
    flexShrink: 1,
    color: '#FF8F00',
    fontSize: 11,
    fontWeight: '700',
  },
  dateSelector: {
    gap: 8,
    paddingTop: 14,
  },
  dateOption: {
    minHeight: 36,
    justifyContent: 'center',
    paddingHorizontal: 12,
    borderWidth: 1,
    borderColor: potatoColors.border,
    borderRadius: 18,
    backgroundColor: '#FFFDF9',
  },
  selectedDateOption: {
    borderColor: potatoColors.accent,
    backgroundColor: potatoColors.accentLight,
  },
  dateOptionText: {
    color: potatoColors.muted,
    fontSize: 12,
    fontWeight: '600',
  },
  selectedDateOptionText: {
    color: '#3C1E1E',
    fontWeight: '700',
  },
  chart: {
    flexDirection: 'row',
    marginTop: 16,
  },
  memberColumn: {
    width: 96,
    marginRight: 8,
  },
  memberHeader: {
    height: 24,
    justifyContent: 'center',
    marginBottom: 12,
  },
  memberHeaderText: {
    color: potatoColors.muted,
    fontSize: 12,
    fontWeight: '700',
  },
  memberLabel: {
    height: 24,
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  avatar: {
    width: 22,
    height: 22,
    flexShrink: 0,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 11,
    backgroundColor: '#E0E0E0',
  },
  avatarText: {
    color: '#424242',
    fontSize: 10,
    fontWeight: '700',
  },
  memberName: {
    flex: 1,
    marginLeft: 4,
    color: potatoColors.text,
    fontSize: 11,
    fontWeight: '700',
  },
  memberStatus: {
    marginLeft: 2,
    color: potatoColors.muted,
    fontSize: 8,
  },
  timelineScroll: {
    flex: 1,
  },
  hourLabels: {
    width: TIMELINE_WIDTH,
    height: 24,
    position: 'relative',
    marginBottom: 12,
  },
  hourLabel: {
    position: 'absolute',
    top: 0,
    width: 50,
    color: potatoColors.placeholder,
    fontSize: 11,
  },
  hourRows: {
    gap: 12,
  },
  availabilityRow: {
    width: TIMELINE_WIDTH,
    height: 24,
    position: 'relative',
    overflow: 'hidden',
    borderRadius: 4,
    backgroundColor: '#F5F5F5',
  },
  unsubmittedRow: {
    backgroundColor: '#E0E0E0',
  },
  timeSegment: {
    position: 'absolute',
    top: 0,
    height: '100%',
    backgroundColor: '#81C784',
  },
  legend: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: 16,
    marginTop: 20,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  legendSwatch: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  legendLabel: {
    color: '#666666',
    fontSize: 12,
  },
  exactTimes: {
    alignItems: 'center',
    gap: 4,
    marginTop: 14,
  },
  exactTimesTitle: {
    color: potatoColors.text,
    fontSize: 12,
    fontWeight: '700',
  },
  exactTime: {
    color: potatoColors.muted,
    fontSize: 12,
    fontVariant: ['tabular-nums'],
  },
  emptyState: {
    minHeight: 120,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 16,
    padding: 16,
    borderRadius: 16,
    backgroundColor: '#FFFDF9',
  },
  emptyTitle: {
    color: potatoColors.text,
    fontSize: 15,
    fontWeight: '700',
    textAlign: 'center',
  },
  emptyDetail: {
    marginTop: 6,
    color: potatoColors.muted,
    fontSize: 13,
    lineHeight: 19,
    textAlign: 'center',
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
  previousButton: {
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
  previousText: {
    color: potatoColors.muted,
    fontSize: 15,
    fontWeight: '700',
  },
  aiButton: {
    flex: 1,
    height: 52,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 26,
    backgroundColor: potatoColors.accentLight,
  },
  aiButtonText: {
    color: '#3C1E1E',
    fontSize: 16,
    fontWeight: '700',
  },
});
