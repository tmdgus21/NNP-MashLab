import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { potatoColors } from '../theme/colors';
import {
  newRequestKey,
  PotatoApiError,
  type PotatoApi,
} from '../services/potatoApi';
import {
  loadRoomState,
  participantLabel,
  runStatusMessage,
  type RoomState,
} from '../services/roomState';
import { formatDateKo, formatClock, formatSeoulRange } from '../services/seoulTime';

interface RoomScreenProps {
  api: PotatoApi;
  roomId: string;
  onBack: () => void;
  onEditAvailability: (state: RoomState) => void;
  onLeft: () => void;
  /** Poll interval; tests pass 0 to disable the timer. */
  pollMs?: number;
}

const CONSENT_LABEL: Record<string, string> = { AGREE: '동의', DISAGREE: '거절' };

export function RoomScreen({
  api,
  roomId,
  onBack,
  onEditAvailability,
  onLeft,
  pollMs = 3000,
}: RoomScreenProps) {
  const [state, setState] = useState<RoomState | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const loading = useRef(false);

  const refresh = useCallback(async () => {
    if (loading.current) {
      return;
    }
    loading.current = true;
    try {
      setState(await loadRoomState(api, roomId));
      setError('');
    } catch (failure) {
      setError(failure instanceof PotatoApiError ? failure.message : '불러오지 못했어요.');
    } finally {
      loading.current = false;
    }
  }, [api, roomId]);

  useEffect(() => {
    void refresh();
    if (!pollMs) {
      return undefined;
    }
    const timer = setInterval(() => void refresh(), pollMs);
    return () => clearInterval(timer);
  }, [refresh, pollMs]);

  const act = async (work: () => Promise<unknown>) => {
    setBusy(true);
    setError('');
    try {
      await work();
      await refresh();
    } catch (failure) {
      setError(failure instanceof PotatoApiError ? failure.message : '요청을 처리하지 못했어요.');
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  if (!state) {
    return (
      <SafeAreaView style={styles.safe}>
        <Header title="모임" onBack={onBack} />
        <Text style={styles.muted}>{error || '불러오는 중…'}</Text>
      </SafeAreaView>
    );
  }

  const { room, participants, myAvailability, latest, candidates, decision, finalResult } = state;
  const isHost = room.me?.role === 'organizer';
  const myMemberId = room.me?.memberId;
  const nameOf = (memberId: string) =>
    participants.find(person => person.memberId === memberId)?.displayName ?? '참여자';
  const run = latest.run;
  const runCurrent = !!run && run.current && run.status !== 'STALE';
  const selectedId = decision?.selectedCandidateId ?? null;
  const iAmAttendee = !!decision?.attendees.some(item => item.roomMemberId === myMemberId);
  const myConsent = decision?.attendees.find(item => item.roomMemberId === myMemberId)?.consentStatus ?? null;
  const approved = decision?.approvalStatus === 'APPROVED';

  const shareCode = () =>
    void Share.share({
      message: `[Potato Meet] "${room.title}" 모임에 초대합니다! Potato Meet 앱에서 '초대 코드로 참가'를 누르고 코드 ${room.code} 를 입력해 주세요.`,
    });

  const leave = () =>
    Alert.alert('모임 나가기', '나가면 이 모임에 다시 참가할 수 없어요. 계속할까요?', [
      { text: '취소', style: 'cancel' },
      {
        text: '나가기',
        style: 'destructive',
        onPress: () => void act(async () => {
          await api.rooms.leave(roomId);
          onLeft();
        }),
      },
    ]);

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={styles.safe}>
      <Header title={room.title} onBack={onBack} />
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={busy} onRefresh={() => void refresh()} />}
      >
        {!!error && <Text accessibilityLiveRegion="assertive" style={styles.error}>{error}</Text>}

        <Card>
          <Text style={styles.line}>{room.activity} · {room.location} · {room.durationMinutes}분</Text>
          <Text style={styles.muted}>후보 날짜: {room.dates.map(formatDateKo).join(', ')}</Text>
          <View style={styles.codeRow}>
            <View>
              <Text style={styles.muted}>초대 코드</Text>
              <Text accessibilityLabel={`초대 코드 ${room.code}`} style={styles.code}>{room.code}</Text>
            </View>
            <Button title="코드 공유" secondary onPress={shareCode} />
          </View>
          {room.eligibleParticipantCount < 2 && (
            <Text style={styles.muted}>
              아직 아무도 참여하지 않았어요. 코드를 공유해 친구를 초대해 주세요. 친구가 코드로 참가하면 이곳에 나타나요.
            </Text>
          )}
        </Card>

        {finalResult.finalized && finalResult.startsAt && finalResult.endsAt && (
          <Card highlight>
            <Text style={styles.sectionTitle}>✅ 모임이 확정됐어요</Text>
            <Text style={styles.final}>{formatSeoulRange(finalResult.startsAt, finalResult.endsAt)}</Text>
            <Text style={styles.muted}>참석자 {finalResult.attendeeMemberIds?.length ?? 0}명</Text>
          </Card>
        )}

        <Card>
          <Text style={styles.sectionTitle}>참여자 ({room.eligibleParticipantCount}명)</Text>
          {participants.map(person => (
            <View key={person.participantId} style={styles.row}>
              <Text style={styles.name}>
                {person.displayName ?? '초대한 사람'}
                {person.role === 'organizer' ? ' (방장)' : ''}
                {person.memberId === myMemberId ? ' · 나' : ''}
              </Text>
              <Text style={styles.muted}>{participantLabel(person)}</Text>
            </View>
          ))}
        </Card>

        <Card>
          <Text style={styles.sectionTitle}>내 가능한 시간</Text>
          {myAvailability.status === 'submitted' ? (
            myAvailability.timeSlots.map(slot => (
              <Text key={`${slot.date}-${slot.startTimeMinutes}`} style={styles.line}>
                {formatDateKo(slot.date)} {formatClock(slot.startTimeMinutes)}~{formatClock(slot.endTimeMinutes)}
              </Text>
            ))
          ) : (
            <Text style={styles.muted}>
              아직 제출하지 않았어요. 제출하기 전에는 불참으로 처리되지 않아요.
            </Text>
          )}
          {!finalResult.finalized && (
            <Button
              title={myAvailability.status === 'submitted' ? '내 시간 수정' : '내 가능한 시간 입력'}
              onPress={() => onEditAvailability(state)}
              disabled={busy}
            />
          )}
        </Card>

        {!finalResult.finalized && (
          <Card>
            <Text style={styles.sectionTitle}>일정 계산</Text>
            <Text style={styles.line}>{runStatusMessage(state)}</Text>
            {isHost && (!run || !runCurrent || ['WAITING_FOR_INPUT', 'NO_FEASIBLE_SCHEDULE', 'FAILED', 'ERROR', 'CANCELLED'].includes(run.status)) && (
              <Button
                title={run ? '다시 계산하기' : '일정 계산하기'}
                disabled={busy || room.eligibleParticipantCount < 2}
                onPress={() =>
                  void act(() =>
                    api.runs.start(roomId, room.agentInputRevision, newRequestKey(`run-${room.agentInputRevision}`)),
                  )
                }
              />
            )}
            {isHost && room.eligibleParticipantCount < 2 && (
              <Text style={styles.muted}>참여자가 2명 이상이어야 계산할 수 있어요.</Text>
            )}
          </Card>
        )}

        {candidates && run && runCurrent && !finalResult.finalized && (
          <Card>
            <Text style={styles.sectionTitle}>추천 후보</Text>
            {candidates.candidates.map(candidate => {
              const attending = candidate.members.filter(m => m.participationStatus === 'ATTENDING').length;
              const chosen = candidate.candidateId === selectedId;
              return (
                <View key={candidate.candidateId} style={[styles.candidate, chosen && styles.chosen]}>
                  <Text style={styles.name}>{formatSeoulRange(candidate.startsAt, candidate.endsAt)}</Text>
                  <Text style={styles.muted}>
                    {candidate.candidateType === 'ALL_AVAILABLE' ? '전원 가능' : '일부만 가능'} · {attending}/{candidate.members.length}명 참석
                    {chosen ? ' · 선택됨' : ''}
                  </Text>
                  {isHost && !approved && !chosen && (
                    <Button
                      title="이 시간으로 정하기"
                      secondary
                      disabled={busy}
                      onPress={() =>
                        void act(() => api.decision.select(roomId, run.runId, candidate.candidateId, decision?.decisionVersion))
                      }
                    />
                  )}
                </View>
              );
            })}
          </Card>
        )}

        {decision && selectedId && run && runCurrent && !finalResult.finalized && (
          <Card>
            <Text style={styles.sectionTitle}>참석 동의</Text>
            {decision.attendees.map(item => (
              <View key={item.roomMemberId} style={styles.row}>
                <Text style={styles.name}>{nameOf(item.roomMemberId)}</Text>
                <Text style={styles.muted}>
                  {item.consentStatus ? CONSENT_LABEL[item.consentStatus] ?? item.consentStatus : '아직 응답 없음'}
                </Text>
              </View>
            ))}
            {iAmAttendee && !approved && (
              <View style={styles.buttons}>
                <Button
                  title="동의하기"
                  disabled={busy || myConsent === 'AGREE'}
                  onPress={() => void act(() => api.decision.consent(roomId, run.runId, 'AGREE'))}
                />
                <Button
                  title="거절하기"
                  secondary
                  disabled={busy || myConsent === 'DISAGREE'}
                  onPress={() => void act(() => api.decision.consent(roomId, run.runId, 'DISAGREE'))}
                />
                {myConsent && (
                  <Button
                    title="응답 취소"
                    secondary
                    disabled={busy}
                    onPress={() => void act(() => api.decision.consent(roomId, run.runId, 'WITHDRAW'))}
                  />
                )}
              </View>
            )}
            {!iAmAttendee && <Text style={styles.muted}>이 후보에 참석자로 포함되지 않아 동의가 필요 없어요.</Text>}
            {isHost && decision.allAgreed && !approved && (
              <Button
                title="승인하기"
                disabled={busy}
                onPress={() => void act(() => api.decision.approve(roomId, run.runId, 'APPROVE'))}
              />
            )}
            {isHost && !decision.allAgreed && !approved && (
              <Text style={styles.muted}>모든 참석자가 동의하면 승인할 수 있어요.</Text>
            )}
            {isHost && approved && (
              <Button
                title="최종 확정하기"
                disabled={busy}
                onPress={() => void act(() => api.decision.finalize(roomId, run.runId))}
              />
            )}
            {!isHost && approved && <Text style={styles.muted}>방장이 승인했어요. 확정을 기다리고 있어요.</Text>}
          </Card>
        )}

        {!isHost && !finalResult.finalized && (
          <Button title="모임 나가기" secondary onPress={leave} disabled={busy} />
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function Header({ title, onBack }: { title: string; onBack: () => void }) {
  return (
    <View style={styles.header}>
      <Pressable accessibilityRole="button" accessibilityLabel="뒤로" onPress={onBack} style={styles.back}>
        <Text style={styles.backText}>‹</Text>
      </Pressable>
      <Text numberOfLines={1} style={styles.headerTitle}>{title}</Text>
    </View>
  );
}

function Card({ children, highlight }: { children: React.ReactNode; highlight?: boolean }) {
  return <View style={[styles.card, highlight && styles.highlight]}>{children}</View>;
}

function Button({
  title,
  onPress,
  secondary,
  disabled,
}: {
  title: string;
  onPress: () => void;
  secondary?: boolean;
  disabled?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      onPress={onPress}
      style={[styles.button, secondary && styles.buttonSecondary, disabled && styles.disabled]}
    >
      <Text style={[styles.buttonText, secondary && styles.buttonTextSecondary]}>{title}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: potatoColors.background },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 10 },
  back: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center' },
  backText: { fontSize: 30, color: potatoColors.brown },
  headerTitle: { flex: 1, fontSize: 18, fontWeight: '700', color: potatoColors.text },
  content: { padding: 16, gap: 12, paddingBottom: 40 },
  card: { backgroundColor: potatoColors.white, borderRadius: 18, padding: 16, gap: 8, borderWidth: 1, borderColor: potatoColors.border },
  highlight: { borderColor: potatoColors.accent, backgroundColor: '#FFF8E1' },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: potatoColors.text },
  line: { fontSize: 15, color: potatoColors.text },
  final: { fontSize: 20, fontWeight: '700', color: potatoColors.brown },
  muted: { fontSize: 13, color: potatoColors.muted, padding: 0 },
  error: { backgroundColor: potatoColors.errorBackground, color: potatoColors.errorText, padding: 12, borderRadius: 12, fontSize: 14 },
  codeRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  code: { fontSize: 26, fontWeight: '800', letterSpacing: 3, color: potatoColors.brown },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 8 },
  name: { fontSize: 15, fontWeight: '600', color: potatoColors.text, flexShrink: 1 },
  candidate: { borderWidth: 1, borderColor: potatoColors.border, borderRadius: 14, padding: 12, gap: 6 },
  chosen: { borderColor: potatoColors.accent, backgroundColor: '#FFF8E1' },
  buttons: { gap: 8 },
  button: { height: 46, borderRadius: 23, alignItems: 'center', justifyContent: 'center', backgroundColor: potatoColors.accentLight, paddingHorizontal: 16 },
  buttonSecondary: { backgroundColor: potatoColors.white, borderWidth: 1, borderColor: potatoColors.border },
  buttonText: { fontSize: 15, fontWeight: '700', color: potatoColors.brown },
  buttonTextSecondary: { color: potatoColors.text },
  disabled: { opacity: 0.5 },
});
