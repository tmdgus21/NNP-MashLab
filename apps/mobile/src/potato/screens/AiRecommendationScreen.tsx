import React, { useEffect, useMemo, useState } from 'react';
import {
  KeyboardAvoidingView,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type StyleProp,
  type ViewStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { getAppointmentRecommendationMessage } from '../services/appointmentRecommendation';
import { getDisplayableRecommendationCandidates } from '../services/appointmentRecommendation';
import { potatoColors } from '../theme/colors';
import type { AppointmentCreationDraft } from '../types/appointmentCreation';
import type {
  AppointmentAiRecommendationPreparation,
  AppointmentAiRecommendationRequest,
  AppointmentRecommendationAgentSnapshot,
  AppointmentRecommendationCandidateCommand,
  AppointmentRecommendationCandidate,
  AppointmentRecommendationRescheduleCommand,
  AppointmentRecommendationApprovalCommand,
  AppointmentRecommendationRetryCommand,
} from '../types/appointmentRecommendation';

interface AiRecommendationScreenProps {
  draft: AppointmentCreationDraft;
  preparation: AppointmentAiRecommendationPreparation;
  snapshot: AppointmentRecommendationAgentSnapshot;
  currentSourceRevision?: string;
  apiConnected?: boolean;
  developmentFixture?: boolean;
  onBack: () => void;
  onStartRecommendation: (request: AppointmentAiRecommendationRequest) => void;
  onReschedule: (command: AppointmentRecommendationRescheduleCommand) => void;
  onCandidateSelected: (
    command: AppointmentRecommendationCandidateCommand,
  ) => void;
  onRequestApproval: (
    command: AppointmentRecommendationApprovalCommand,
  ) => void;
  onRetry: (command: AppointmentRecommendationRetryCommand) => void;
  onCancel: (agentRunId: string) => void;
}

const statusLabels: Record<
  AppointmentRecommendationAgentSnapshot['status'],
  string
> = {
  WAITING_FOR_INPUT: '추천 요청을 기다리고 있어요',
  ANALYZING: '참여자 응답과 조건을 분석하고 있어요',
  RUNNING_TOOLS: '일정 가능 여부를 계산하고 있어요',
  ALL_AVAILABLE: '전원이 참석할 수 있는 후보를 찾았어요',
  PARTIAL_ALTERNATIVE: '전원 참석 후보가 없어 대안을 찾았어요',
  NO_FEASIBLE_SCHEDULE: '조건에 맞는 일정을 찾지 못했어요',
  AWAITING_APPROVAL: '후보가 방장 승인을 기다리고 있어요',
  STALE: '입력 정보가 변경되어 다시 계산해야 해요',
  ERROR: '추천을 처리하지 못했어요',
};

function formatCandidateDate(date: string): string {
  const [year, month, day] = date.split('-').map(Number);
  return `${year}년 ${month}월 ${day}일`;
}

function formatCandidateTime(minutes: number): string {
  const hour = Math.floor(minutes / 60);
  const minute = minutes % 60;
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
}

function participantStatus(
  draft: AppointmentCreationDraft,
  participantId: string,
): string {
  const participant = draft.participants?.find(
    item => item.id === participantId,
  );
  if (!participant) {
    return '응답 정보 없음';
  }
  if (participant.role === 'organizer') {
    return '모임 생성자';
  }
  if (
    participant.invitationStatus === 'not_sent' &&
    participant.participationStatus === 'pending'
  ) {
    return '초대 미발송';
  }
  if (participant.participationStatus === 'pending') {
    return '응답 대기';
  }
  if (participant.participationStatus === 'declined') {
    return '참여 거절';
  }
  const submission = draft.availabilitySubmissions?.find(
    item => item.participantId === participantId,
  );
  return submission?.status === 'submitted' ? '시간 제출 완료' : '시간 미제출';
}

function participantName(
  draft: AppointmentCreationDraft,
  participantId: string,
): string {
  if (participantId === draft.organizerId) {
    return '나';
  }
  return draft.invitedFriendNameById?.[participantId] ?? '초대 친구';
}

function getParticipantIds(draft: AppointmentCreationDraft): string[] {
  const ids = new Set<string>();
  if (draft.organizerId) {
    ids.add(draft.organizerId);
  }
  for (const participant of draft.participants ?? []) {
    ids.add(participant.id);
  }
  for (const id of draft.invitedFriendIds ?? []) {
    ids.add(id);
  }
  return [...ids];
}

function getExpectedAttendeeIds(draft: AppointmentCreationDraft): string[] {
  const ids = new Set<string>();
  for (const participant of draft.participants ?? []) {
    if (
      participant.role === 'organizer' ||
      participant.participationStatus !== 'declined'
    ) {
      ids.add(participant.id);
    }
  }
  for (const id of draft.invitedFriendIds ?? []) {
    const participant = draft.participants?.find(item => item.id === id);
    if (!participant || participant.participationStatus !== 'declined') {
      ids.add(id);
    }
  }
  return [...ids];
}

export function AiRecommendationScreen({
  draft,
  preparation,
  snapshot,
  currentSourceRevision,
  apiConnected = false,
  developmentFixture = false,
  onBack,
  onStartRecommendation,
  onReschedule,
  onCandidateSelected,
  onRequestApproval,
  onRetry,
  onCancel,
}: AiRecommendationScreenProps) {
  const [selectedCandidateId, setSelectedCandidateId] = useState<string>();
  const [requestText, setRequestText] = useState('');
  const [requestSequence, setRequestSequence] = useState(0);
  const [startRequested, setStartRequested] = useState(false);
  const [approvalRequested, setApprovalRequested] = useState(false);
  const [rescheduleRequested, setRescheduleRequested] = useState(false);
  const isRunning =
    snapshot.status === 'ANALYZING' || snapshot.status === 'RUNNING_TOOLS';
  const canStart =
    snapshot.status === 'WAITING_FOR_INPUT' &&
    preparation.status === 'ready' &&
    !snapshot.agentRunId &&
    !startRequested;
  const expectedAttendeeIds = useMemo(
    () => getExpectedAttendeeIds(draft),
    [draft],
  );
  const displayable = useMemo(() => {
    if (preparation.status !== 'ready') {
      return undefined;
    }
    return getDisplayableRecommendationCandidates(
      snapshot,
      currentSourceRevision,
      expectedAttendeeIds,
    );
  }, [
    snapshot,
    currentSourceRevision,
    expectedAttendeeIds,
    preparation.status,
  ]);
  const candidates = displayable?.candidates ?? [];
  const selectedCandidate = candidates.find(
    candidate => candidate.candidateId === selectedCandidateId,
  );
  const participantIds = getParticipantIds(draft);
  const requestHistory = snapshot.history ?? [];
  const canReschedule =
    !isRunning &&
    !rescheduleRequested &&
    !!snapshot.agentRunId &&
    !!currentSourceRevision &&
    requestText.trim().length > 0;
  const canRetry =
    snapshot.status === 'STALE' ||
    (snapshot.status === 'ERROR' && snapshot.error?.retryable === true);
  const canRequestApproval =
    !!selectedCandidate &&
    !!snapshot.agentRunId &&
    !!currentSourceRevision &&
    snapshot.sourceRevision === currentSourceRevision &&
    snapshot.status !== 'AWAITING_APPROVAL' &&
    !isRunning &&
    !approvalRequested;
  const needsInformationMessage =
    preparation.status === 'needs_information'
      ? getAppointmentRecommendationMessage(preparation)
      : undefined;

  useEffect(() => {
    setStartRequested(false);
    setApprovalRequested(false);
    setRescheduleRequested(false);
  }, [snapshot.status, snapshot.agentRunId, snapshot.sourceRevision]);

  const sendRescheduleRequest = () => {
    const text = requestText.trim();
    if (!text || isRunning || !snapshot.agentRunId || !currentSourceRevision) {
      return;
    }

    onReschedule({
      agentRunId: snapshot.agentRunId,
      sourceRevision: currentSourceRevision,
      requestText: text,
    });
    setRequestSequence(sequence => sequence + 1);
    if (apiConnected) {
      setRescheduleRequested(true);
    }
    setRequestText('');
  };

  const requestApproval = () => {
    if (!canRequestApproval || !selectedCandidate) {
      return;
    }
    if (!snapshot.agentRunId || !currentSourceRevision) {
      return;
    }
    onRequestApproval({
      agentRunId: snapshot.agentRunId,
      sourceRevision: currentSourceRevision,
      candidateId: selectedCandidate.candidateId,
    });
    if (apiConnected) {
      setApprovalRequested(true);
    }
  };

  const retryAgent = () => {
    onRetry({
      ...(snapshot.agentRunId ? { agentRunId: snapshot.agentRunId } : {}),
      ...(currentSourceRevision
        ? { sourceRevision: currentSourceRevision }
        : {}),
    });
  };

  return (
    <SafeAreaView
      edges={['top', 'left', 'right', 'bottom']}
      style={styles.safeArea}
    >
      <View style={styles.header}>
        <Pressable
          accessibilityLabel="이전 화면"
          accessibilityRole="button"
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

      <KeyboardAvoidingView behavior="padding" style={styles.keyboardAvoiding}>
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="none"
          showsVerticalScrollIndicator={false}
        >
          <Text style={styles.title}>AI 일정 조율</Text>
          <Text style={styles.subtitle}>
            참여자의 응답과 가능한 시간을 바탕으로 일정을 찾아요.
          </Text>

          <View style={styles.connectionBanner}>
            <Text style={styles.connectionText}>
              {developmentFixture
                ? '개발 프리뷰 · 예시 화면 데이터이며 실제 추천 결과가 아닙니다.'
                : apiConnected
                ? '에이전트 연결됨'
                : 'AI 서버 미연결 · 추천 요청은 아직 전송되지 않습니다.'}
            </Text>
          </View>

          <View style={styles.card}>
            <Text style={styles.sectionTitle}>조건을 바꿔 재조율</Text>
            <Text style={styles.mutedText}>
              원하는 날짜, 시간 또는 참석 조건을 자연어로 입력할 수 있어요.
            </Text>
            <View style={styles.rescheduleRow}>
              <TextInput
                accessibilityLabel="재조율 요청"
                editable={!isRunning}
                multiline
                onChangeText={setRequestText}
                placeholder="예: 일요일 오후로 다시 찾아줘"
                placeholderTextColor={potatoColors.placeholder}
                style={styles.requestInput}
                value={requestText}
              />
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="재조율 요청 전송"
                accessibilityState={{ disabled: !canReschedule }}
                disabled={!canReschedule}
                onPress={sendRescheduleRequest}
                style={[
                  styles.sendButton,
                  !canReschedule && styles.disabledAction,
                ]}
              >
                <Text style={styles.sendButtonText}>전송</Text>
              </Pressable>
            </View>
            {requestText.trim().length === 0 && (
              <Text style={styles.inputHint}>요청 내용을 입력해주세요.</Text>
            )}
            {!snapshot.agentRunId && (
              <Text style={styles.inputHint}>
                먼저 에이전트 실행을 요청해야 재조율할 수 있어요.
              </Text>
            )}
            {!apiConnected && requestSequence > 0 && (
              <Text accessibilityLiveRegion="polite" style={styles.noticeText}>
                API 미연결 상태라 요청을 전송하지 않았습니다.
              </Text>
            )}
          </View>

          <View style={styles.card}>
            <Text style={styles.sectionTitle}>모임 정보</Text>
            <InfoRow label="모임" value={draft.title?.trim() || '입력 필요'} />
            <InfoRow
              label="활동"
              value={draft.category?.trim() || '입력 필요'}
            />
            <InfoRow
              label="소요시간"
              value={draft.duration?.trim() || '입력 필요'}
            />
            <InfoRow
              label="장소"
              value={draft.location?.trim() || '입력 필요'}
            />
            {draft.timeZone && (
              <InfoRow label="시간대" value={draft.timeZone} />
            )}
          </View>

          <View style={styles.card}>
            <Text style={styles.sectionTitle}>참여자 응답 및 시간 제출</Text>
            {participantIds.length === 0 ? (
              <Text style={styles.mutedText}>
                확인할 참여자 정보가 아직 없습니다.
              </Text>
            ) : (
              participantIds.map(id => (
                <View key={id} style={styles.participantRow}>
                  <Text style={styles.participantName}>
                    {participantName(draft, id)}
                  </Text>
                  <Text style={styles.participantStatus}>
                    {participantStatus(draft, id)}
                  </Text>
                </View>
              ))
            )}
            {(draft.unresolvedInvitedFriendNames ?? []).map((name, index) => (
              <View key={`${name}-${index}`} style={styles.participantRow}>
                <Text style={styles.participantName}>{name}</Text>
                <Text style={styles.participantStatus}>ID 확인 필요</Text>
              </View>
            ))}
            {participantIds.some(id => {
              const participant = draft.participants?.find(
                item => item.id === id,
              );
              return (
                participant?.role === 'invitee' &&
                participant.participationStatus === 'pending'
              );
            }) && (
              <Text style={styles.noticeText}>
                응답 대기 중인 참여자는 불참으로 간주하지 않습니다.
              </Text>
            )}
          </View>

          <View style={styles.statusCard}>
            <View
              accessibilityRole="text"
              accessibilityLabel={`에이전트 상태: ${
                statusLabels[snapshot.status]
              }`}
              style={[
                styles.statusDot,
                isRunning ? styles.statusDotRunning : styles.statusDotIdle,
              ]}
            />
            <View style={styles.statusCopy}>
              <Text style={styles.statusLabel}>
                {statusLabels[snapshot.status]}
              </Text>
              {snapshot.status === 'RUNNING_TOOLS' && (
                <Text style={styles.mutedText}>
                  일정 계산 및 제약조건 검증을 진행하고 있어요.
                </Text>
              )}
            </View>
            {isRunning && snapshot.agentRunId && (
              <Pressable
                accessibilityRole="button"
                onPress={() => {
                  if (snapshot.agentRunId) {
                    onCancel(snapshot.agentRunId);
                  }
                }}
                style={styles.inlineButton}
              >
                <Text style={styles.inlineButtonText}>취소</Text>
              </Pressable>
            )}
          </View>

          {needsInformationMessage && (
            <View style={styles.warningCard}>
              <Text style={styles.warningTitle}>추천 전에 확인이 필요해요</Text>
              <Text style={styles.bodyText}>{needsInformationMessage}</Text>
            </View>
          )}

          {snapshot.status === 'ERROR' && (
            <View style={styles.warningCard}>
              <Text style={styles.warningTitle}>
                추천 요청을 처리하지 못했어요
              </Text>
              <Text style={styles.bodyText}>
                {snapshot.error?.userMessage || '잠시 후 다시 시도해주세요.'}
              </Text>
              {canRetry && (
                <ActionButton
                  label="다시 시도"
                  onPress={retryAgent}
                  style={styles.secondaryAction}
                />
              )}
            </View>
          )}

          {snapshot.status === 'STALE' && (
            <View style={styles.warningCard}>
              <Text style={styles.warningTitle}>모임 정보가 변경됐어요</Text>
              <Text style={styles.bodyText}>
                변경된 정보를 기준으로 다시 추천을 요청해주세요.
              </Text>
              <ActionButton
                label="다시 추천 준비"
                onPress={retryAgent}
                style={styles.secondaryAction}
              />
            </View>
          )}

          {snapshot.status === 'NO_FEASIBLE_SCHEDULE' && (
            <View style={styles.emptyCard}>
              <Text style={styles.emptyTitle}>추천 가능한 시간이 없어요</Text>
              <Text style={styles.bodyText}>
                STEP 3의 가능 시간이나 참여자의 조건을 조정한 뒤 다시
                시도해주세요.
              </Text>
            </View>
          )}

          {(snapshot.status === 'ALL_AVAILABLE' ||
            snapshot.status === 'PARTIAL_ALTERNATIVE' ||
            snapshot.status === 'AWAITING_APPROVAL') && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>추천 후보</Text>
              {displayable ? (
                <>
                  {displayable.recommendationType === 'PARTIAL_ALTERNATIVE' && (
                    <View style={styles.alternativeNotice}>
                      <Text style={styles.alternativeText}>
                        전원 참석 가능 여부를 확인한 뒤 제공하는 일부 참석
                        대안입니다.
                      </Text>
                    </View>
                  )}
                  {candidates.map((candidate, index) => (
                    <RecommendationCard
                      candidate={candidate}
                      index={index}
                      key={candidate.candidateId}
                      selected={candidate.candidateId === selectedCandidateId}
                      onPress={() => {
                        if (snapshot.status === 'AWAITING_APPROVAL') {
                          return;
                        }
                        setSelectedCandidateId(candidate.candidateId);
                        if (snapshot.agentRunId && currentSourceRevision) {
                          onCandidateSelected({
                            agentRunId: snapshot.agentRunId,
                            sourceRevision: currentSourceRevision,
                            candidateId: candidate.candidateId,
                          });
                        }
                      }}
                      draft={draft}
                      disabled={snapshot.status === 'AWAITING_APPROVAL'}
                    />
                  ))}
                </>
              ) : (
                <View style={styles.emptyCard}>
                  <Text style={styles.bodyText}>
                    검증 상태와 입력 버전을 확인할 수 있는 추천 후보가 없습니다.
                  </Text>
                </View>
              )}
              {snapshot.status === 'AWAITING_APPROVAL' ? (
                <View style={styles.noticeCard}>
                  <Text style={styles.bodyText}>
                    방장의 승인을 기다리는 중입니다. 일정은 아직 확정되지
                    않았어요.
                  </Text>
                </View>
              ) : candidates.length > 0 ? (
                <ActionButton
                  disabled={!canRequestApproval}
                  label="선택한 후보로 방장 승인 요청"
                  onPress={requestApproval}
                  style={styles.primaryAction}
                />
              ) : null}
            </View>
          )}

          {snapshot.status === 'WAITING_FOR_INPUT' && (
            <ActionButton
              disabled={!canStart}
              label={
                preparation.status === 'ready'
                  ? 'AI 추천 요청'
                  : '필수 정보 확인 후 요청'
              }
              onPress={() => {
                if (canStart && preparation.status === 'ready') {
                  onStartRecommendation(preparation.request);
                  if (apiConnected) {
                    setStartRequested(true);
                  }
                }
              }}
              style={styles.primaryAction}
            />
          )}

          {requestHistory.length > 0 && (
            <View style={styles.card}>
              <Text style={styles.sectionTitle}>이전 요청</Text>
              {requestHistory.map(entry => (
                <View key={entry.requestId} style={styles.historyEntry}>
                  <Text style={styles.bodyText}>{entry.requestText}</Text>
                  <Text style={styles.historyStatus}>
                    {entry.status === 'not_sent'
                      ? '전송되지 않음'
                      : entry.status === 'sent'
                      ? '처리 중'
                      : entry.status === 'completed'
                      ? '결과 도착'
                      : '처리 실패'}
                  </Text>
                  {entry.responseSummary && (
                    <Text style={styles.mutedText}>
                      {entry.responseSummary}
                    </Text>
                  )}
                </View>
              ))}
            </View>
          )}
        </ScrollView>

        <View style={styles.footer}>
          <Pressable
            accessibilityRole="button"
            onPress={onBack}
            style={styles.backAction}
          >
            <Text style={styles.backActionText}>STEP 4로 돌아가기</Text>
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={styles.infoValue}>{value}</Text>
    </View>
  );
}

function ActionButton({
  label,
  onPress,
  disabled = false,
  style,
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  style: StyleProp<ViewStyle>;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      style={[styles.actionButton, style, disabled && styles.disabledAction]}
    >
      <Text style={styles.actionButtonText}>{label}</Text>
    </Pressable>
  );
}

function RecommendationCard({
  candidate,
  index,
  selected,
  onPress,
  draft,
  disabled,
}: {
  candidate: AppointmentRecommendationCandidate;
  index: number;
  selected: boolean;
  onPress: () => void;
  draft: AppointmentCreationDraft;
  disabled: boolean;
}) {
  const attendees = candidate.attendeeIds.map(id => participantName(draft, id));
  const unavailable = candidate.unavailableIds.map(id =>
    participantName(draft, id),
  );

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`추천 후보 ${index + 1}, ${formatCandidateDate(
        candidate.date,
      )} ${formatCandidateTime(
        candidate.startMinute,
      )}부터 ${formatCandidateTime(candidate.endMinute)}, ${
        selected ? '선택됨' : '선택 안 됨'
      }`}
      accessibilityState={{ disabled, selected }}
      disabled={disabled}
      onPress={onPress}
      style={[styles.recommendationCard, selected && styles.selectedCard]}
    >
      <View style={styles.candidateHeader}>
        <Text style={styles.rank}>추천 {index + 1}</Text>
        <Text style={styles.candidateType}>
          {candidate.recommendationType === 'ALL_AVAILABLE'
            ? '전원 참석'
            : '일부 참석 대안'}
        </Text>
      </View>
      <Text style={styles.candidateDate}>
        {formatCandidateDate(candidate.date)}
      </Text>
      <Text style={styles.candidateTime}>
        {formatCandidateTime(candidate.startMinute)} ~{' '}
        {formatCandidateTime(candidate.endMinute)} ({candidate.timeZone})
      </Text>
      <Text style={styles.attendeeLabel}>
        참석 가능: {attendees.join(', ')}
      </Text>
      {candidate.recommendationType === 'PARTIAL_ALTERNATIVE' && (
        <Text style={styles.unavailableLabel}>
          참석 불가: {unavailable.join(', ')}
        </Text>
      )}
      <Text style={styles.explanation}>
        {candidate.explanation.agentSummary}
      </Text>
      {candidate.explanation.optimizerSummary && (
        <Text style={styles.optimizerSummary}>
          계산 검증: {candidate.explanation.optimizerSummary}
        </Text>
      )}
      <Text style={styles.verifiedLabel}>일정 검증 완료</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: potatoColors.background,
  },
  keyboardAvoiding: {
    flex: 1,
  },
  header: {
    minHeight: 52,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 8,
  },
  backButton: {
    marginRight: 12,
    paddingVertical: 6,
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
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 20,
    gap: 12,
  },
  title: {
    color: potatoColors.text,
    fontSize: 22,
    fontWeight: '800',
  },
  subtitle: {
    marginTop: -8,
    color: potatoColors.muted,
    fontSize: 14,
    lineHeight: 20,
  },
  connectionBanner: {
    padding: 12,
    borderRadius: 12,
    backgroundColor: '#FFF4D6',
  },
  connectionText: {
    color: potatoColors.brown,
    fontSize: 12,
    fontWeight: '700',
    lineHeight: 18,
  },
  card: {
    padding: 16,
    borderRadius: 18,
    backgroundColor: potatoColors.white,
    elevation: 2,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 3,
  },
  section: {
    gap: 10,
  },
  sectionTitle: {
    marginBottom: 8,
    color: potatoColors.text,
    fontSize: 16,
    fontWeight: '700',
  },
  infoRow: {
    minHeight: 28,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  infoLabel: {
    color: potatoColors.muted,
    fontSize: 13,
  },
  infoValue: {
    flexShrink: 1,
    color: potatoColors.text,
    fontSize: 13,
    fontWeight: '600',
    textAlign: 'right',
  },
  participantRow: {
    minHeight: 36,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: potatoColors.border,
  },
  participantName: {
    flexShrink: 1,
    color: potatoColors.text,
    fontSize: 13,
    fontWeight: '600',
  },
  participantStatus: {
    color: potatoColors.muted,
    fontSize: 12,
  },
  statusCard: {
    minHeight: 68,
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    borderRadius: 16,
    backgroundColor: potatoColors.white,
  },
  statusDot: {
    width: 12,
    height: 12,
    marginRight: 12,
    borderRadius: 6,
  },
  statusDotRunning: {
    backgroundColor: potatoColors.orange,
  },
  statusDotIdle: {
    backgroundColor: potatoColors.accent,
  },
  statusCopy: {
    flex: 1,
    gap: 4,
  },
  statusLabel: {
    color: potatoColors.text,
    fontSize: 14,
    fontWeight: '700',
  },
  mutedText: {
    color: potatoColors.muted,
    fontSize: 12,
    lineHeight: 18,
  },
  noticeText: {
    marginTop: 8,
    color: potatoColors.errorText,
    fontSize: 12,
    lineHeight: 18,
  },
  noticeCard: {
    marginTop: 10,
    padding: 14,
    borderRadius: 14,
    backgroundColor: '#FFF4D6',
  },
  warningCard: {
    gap: 8,
    padding: 16,
    borderRadius: 16,
    backgroundColor: potatoColors.errorBackground,
  },
  warningTitle: {
    color: potatoColors.errorText,
    fontSize: 15,
    fontWeight: '700',
  },
  bodyText: {
    color: potatoColors.text,
    fontSize: 13,
    lineHeight: 19,
  },
  emptyCard: {
    gap: 8,
    padding: 18,
    borderRadius: 16,
    backgroundColor: potatoColors.white,
  },
  emptyTitle: {
    color: potatoColors.text,
    fontSize: 15,
    fontWeight: '700',
  },
  alternativeNotice: {
    padding: 12,
    borderRadius: 12,
    backgroundColor: '#FFF4D6',
  },
  alternativeText: {
    color: potatoColors.brown,
    fontSize: 12,
    lineHeight: 18,
  },
  recommendationCard: {
    marginBottom: 10,
    padding: 16,
    borderWidth: 1,
    borderColor: potatoColors.border,
    borderRadius: 16,
    backgroundColor: potatoColors.white,
    elevation: 2,
  },
  selectedCard: {
    borderWidth: 2,
    borderColor: potatoColors.accent,
  },
  candidateHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  rank: {
    color: potatoColors.orange,
    fontSize: 14,
    fontWeight: '800',
  },
  candidateType: {
    color: potatoColors.brown,
    fontSize: 12,
    fontWeight: '700',
  },
  candidateDate: {
    marginTop: 10,
    color: potatoColors.text,
    fontSize: 16,
    fontWeight: '700',
  },
  candidateTime: {
    marginTop: 4,
    color: potatoColors.brown,
    fontSize: 15,
    fontWeight: '700',
  },
  attendeeLabel: {
    marginTop: 10,
    color: '#2E7D32',
    fontSize: 12,
    lineHeight: 18,
  },
  unavailableLabel: {
    marginTop: 3,
    color: '#A94442',
    fontSize: 12,
    lineHeight: 18,
  },
  explanation: {
    marginTop: 10,
    color: potatoColors.text,
    fontSize: 13,
    lineHeight: 19,
  },
  optimizerSummary: {
    marginTop: 4,
    color: potatoColors.muted,
    fontSize: 12,
    lineHeight: 18,
  },
  verifiedLabel: {
    marginTop: 10,
    color: '#2E7D32',
    fontSize: 11,
    fontWeight: '700',
  },
  actionButton: {
    minHeight: 48,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 16,
    borderRadius: 24,
  },
  primaryAction: {
    backgroundColor: potatoColors.accentLight,
  },
  secondaryAction: {
    marginTop: 4,
    backgroundColor: potatoColors.white,
    borderWidth: 1,
    borderColor: potatoColors.border,
  },
  disabledAction: {
    opacity: 0.45,
  },
  actionButtonText: {
    color: potatoColors.brown,
    fontSize: 14,
    fontWeight: '700',
    textAlign: 'center',
  },
  historyEntry: {
    paddingVertical: 10,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: potatoColors.border,
  },
  historyStatus: {
    marginTop: 4,
    color: potatoColors.muted,
    fontSize: 11,
  },
  rescheduleRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
    marginTop: 12,
  },
  requestInput: {
    flex: 1,
    minHeight: 48,
    maxHeight: 120,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: potatoColors.border,
    borderRadius: 12,
    color: potatoColors.text,
    fontSize: 14,
  },
  sendButton: {
    minHeight: 44,
    minWidth: 64,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 22,
    backgroundColor: potatoColors.accentLight,
  },
  sendButtonText: {
    color: potatoColors.brown,
    fontSize: 13,
    fontWeight: '700',
  },
  inputHint: {
    marginTop: 6,
    color: potatoColors.muted,
    fontSize: 11,
  },
  inlineButton: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 16,
    backgroundColor: potatoColors.errorBackground,
  },
  inlineButtonText: {
    color: potatoColors.errorText,
    fontSize: 12,
    fontWeight: '700',
  },
  footer: {
    paddingHorizontal: 20,
    paddingTop: 8,
    paddingBottom: 8,
    backgroundColor: potatoColors.background,
  },
  backAction: {
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  backActionText: {
    color: potatoColors.muted,
    fontSize: 13,
    fontWeight: '700',
  },
});
