import React from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  getSelectedFriendIds,
  updateInvitedFriendSelection,
} from '../services/appointmentParticipants';
import { potatoColors } from '../theme/colors';
import type { AppointmentCreationDraft } from '../types/appointmentCreation';
import type { PotatoFriend } from '../types/friend';

interface CreateAppointmentStep2InviteScreenProps {
  friends: readonly PotatoFriend[];
  draft: AppointmentCreationDraft;
  onBack: () => void;
  onDraftChange: (draft: AppointmentCreationDraft) => void;
  onRequestStep3: () => void;
}

const steps = [
  { number: '1', title: '모임 정보' },
  { number: '2', title: '친구 초대' },
  { number: '3', title: '나의 시간' },
  { number: '4', title: '시간 조율' },
] as const;

export function CreateAppointmentStep2InviteScreen({
  friends,
  draft,
  onBack,
  onDraftChange,
  onRequestStep3,
}: CreateAppointmentStep2InviteScreenProps) {
  const selectedFriendIds = getSelectedFriendIds(draft, friends);

  const toggleFriend = (friend: PotatoFriend) => {
    const nextSelectedFriendIds = new Set(selectedFriendIds);
    if (nextSelectedFriendIds.has(friend.id)) {
      nextSelectedFriendIds.delete(friend.id);
    } else {
      nextSelectedFriendIds.add(friend.id);
    }
    onDraftChange(
      updateInvitedFriendSelection(
        draft,
        [...nextSelectedFriendIds],
        friends,
      ),
    );
  };

  const requestStep3 = () => {
    if (draft.invitedFriendIds === undefined) {
      onDraftChange(
        updateInvitedFriendSelection(draft, selectedFriendIds, friends),
      );
    }
    onRequestStep3();
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right', 'bottom']} style={styles.safeArea}>
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
            const active = step.number === '2';
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

        <View style={styles.inviteCard}>
          <Text style={styles.cardTitle}>누구와 만날까요?</Text>
          <View
            accessibilityLabel="친구 검색하기"
            style={styles.searchField}
          >
            <Text style={styles.searchPlaceholder}>친구 검색하기</Text>
          </View>
          <ScrollView
            nestedScrollEnabled
            style={styles.friendList}
            showsVerticalScrollIndicator
          >
            {friends.map(friend => {
              const selected = selectedFriendIds.includes(friend.id);
              return (
                <Pressable
                  accessibilityLabel={`${friend.name} 선택`}
                  accessibilityRole="checkbox"
                  accessibilityState={{ checked: selected }}
                  key={friend.id}
                  onPress={() => toggleFriend(friend)}
                  style={styles.friendRow}
                  testID={`friend-option-${friend.id}`}
                >
                  <View style={styles.friendIdentity}>
                    <View style={styles.avatar}>
                      <Text style={styles.avatarText}>
                        {friend.name.slice(0, 1)}
                      </Text>
                    </View>
                    <Text style={styles.friendName}>{friend.name}</Text>
                  </View>
                  <View
                    style={[
                      styles.checkbox,
                      selected && styles.checkboxSelected,
                    ]}
                  >
                    {selected && (
                      <Text style={styles.checkboxCheck}>✓</Text>
                    )}
                  </View>
                </Pressable>
              );
            })}
          </ScrollView>
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
          onPress={requestStep3}
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
  inviteCard: {
    padding: 20,
    borderRadius: 20,
    backgroundColor: potatoColors.white,
    elevation: 2,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 3,
  },
  cardTitle: {
    marginBottom: 14,
    color: potatoColors.text,
    fontSize: 18,
    fontWeight: '700',
  },
  searchField: {
    height: 48,
    justifyContent: 'center',
    marginBottom: 14,
    paddingHorizontal: 14,
    borderWidth: 1,
    borderColor: potatoColors.border,
    borderRadius: 12,
    backgroundColor: potatoColors.white,
  },
  searchPlaceholder: {
    color: potatoColors.placeholder,
    fontSize: 15,
  },
  friendList: {
    maxHeight: 300,
  },
  friendRow: {
    minHeight: 52,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 8,
  },
  friendIdentity: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  avatar: {
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 18,
    backgroundColor: '#E0E0E0',
  },
  avatarText: {
    color: '#424242',
    fontSize: 12,
    fontWeight: '700',
  },
  friendName: {
    marginLeft: 12,
    color: potatoColors.text,
    fontSize: 15,
  },
  checkbox: {
    width: 22,
    height: 22,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#BDBDBD',
    borderRadius: 4,
    backgroundColor: potatoColors.white,
  },
  checkboxSelected: {
    borderColor: potatoColors.accentLight,
    backgroundColor: potatoColors.accentLight,
  },
  checkboxCheck: {
    color: '#3C1E1E',
    fontSize: 15,
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
  pressed: {
    opacity: 0.8,
  },
});
