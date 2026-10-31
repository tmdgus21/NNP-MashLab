import React, { useRef, useState } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { AuthTextInput } from '../components/AuthTextInput';
import { CustomBottomBar } from '../components/CustomBottomBar';
import { potatoColors } from '../theme/colors';
import type { PotatoTabRoute } from '../types/appointment';
import {
  initialPotatoFriends,
  type PotatoFriend,
} from '../types/friend';

interface FriendsScreenProps {
  initialFriends?: readonly PotatoFriend[];
  onSelectionChange?: (selectedFriends: PotatoFriend[]) => void;
  onTabSelected?: (route: PotatoTabRoute) => void;
}

export function FriendsScreen({
  initialFriends = initialPotatoFriends,
  onSelectionChange,
  onTabSelected,
}: FriendsScreenProps) {
  const [friends, setFriends] = useState<PotatoFriend[]>(() =>
    initialFriends.map(friend => ({ ...friend })),
  );
  const [selectedIds, setSelectedIds] = useState<ReadonlySet<string>>(
    () => new Set(),
  );
  const [newFriendName, setNewFriendName] = useState('');
  const [error, setError] = useState('');
  const nextId = useRef(1);

  const changeSelection = (friend: PotatoFriend) => {
    const nextSelectedIds = new Set(selectedIds);
    if (nextSelectedIds.has(friend.id)) {
      nextSelectedIds.delete(friend.id);
    } else {
      nextSelectedIds.add(friend.id);
    }
    setSelectedIds(nextSelectedIds);
    onSelectionChange?.(
      friends.filter(item => nextSelectedIds.has(item.id)),
    );
  };

  const addFriend = () => {
    const name = newFriendName.trim();
    if (!name) {
      setError('추가할 친구 이름을 입력해 주세요.');
      return;
    }
    if (friends.some(friend => friend.name === name)) {
      setError('이미 친구 목록에 있는 이름입니다.');
      return;
    }

    const friend = {
      id: `local-${nextId.current++}`,
      name,
    };
    setFriends(current => [...current, friend]);
    setNewFriendName('');
    setError('');
  };

  const removeFriend = (friend: PotatoFriend) => {
    const nextFriends = friends.filter(item => item.id !== friend.id);
    const nextSelectedIds = new Set(selectedIds);
    nextSelectedIds.delete(friend.id);
    setFriends(nextFriends);
    setSelectedIds(nextSelectedIds);
    onSelectionChange?.(
      nextFriends.filter(item => nextSelectedIds.has(item.id)),
    );
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={styles.safeArea}>
      <View style={styles.content}>
        <ScrollView
          contentContainerStyle={styles.listContent}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <Text style={styles.title}>친구 목록</Text>
          <View style={styles.addFriendRow}>
            <AuthTextInput
              accessibilityLabel="친구 이름"
              autoCapitalize="words"
              containerStyle={styles.nameInput}
              onChangeText={value => {
                setNewFriendName(value);
                if (error) {
                  setError('');
                }
              }}
              placeholder="추가할 친구 이름"
              returnKeyType="done"
              value={newFriendName}
            />
            <Pressable
              accessibilityRole="button"
              onPress={addFriend}
              style={({ pressed }) => [
                styles.addButton,
                pressed && styles.pressed,
              ]}
            >
              <Text style={styles.addButtonText}>추가</Text>
            </Pressable>
          </View>
          {!!error && (
            <Text accessibilityLiveRegion="polite" style={styles.error}>
              {error}
            </Text>
          )}

          {friends.length === 0 ? (
            <View style={styles.emptyState}>
              <Text style={styles.emptyText}>등록된 친구가 없습니다.</Text>
            </View>
          ) : (
            <View style={styles.friendList}>
              {friends.map(friend => {
                const selected = selectedIds.has(friend.id);
                return (
                  <View key={friend.id} style={styles.friendCard}>
                    <Pressable
                      accessibilityRole="checkbox"
                      accessibilityState={{ checked: selected }}
                      onPress={() => changeSelection(friend)}
                      style={styles.friendMain}
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
                          styles.selectionBox,
                          selected && styles.selectionBoxSelected,
                        ]}
                      >
                        {selected && (
                          <Text style={styles.selectionCheck}>✓</Text>
                        )}
                      </View>
                    </Pressable>
                    <Pressable
                      accessibilityLabel={`${friend.name} 삭제`}
                      accessibilityRole="button"
                      onPress={() => removeFriend(friend)}
                      style={styles.deleteButton}
                    >
                      <Text style={styles.deleteButtonText}>삭제</Text>
                    </Pressable>
                    <View style={styles.friendBadge}>
                      <Text style={styles.friendBadgeText}>친구</Text>
                    </View>
                  </View>
                );
              })}
            </View>
          )}
        </ScrollView>
      </View>
      <CustomBottomBar
        currentRoute="friends"
        onTabSelected={route => onTabSelected?.(route)}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: potatoColors.background,
  },
  content: {
    flex: 1,
  },
  listContent: {
    padding: 20,
    flexGrow: 1,
  },
  title: {
    marginBottom: 16,
    color: potatoColors.text,
    fontSize: 22,
    fontWeight: '700',
  },
  addFriendRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  nameInput: {
    flex: 1,
  },
  addButton: {
    height: 48,
    minWidth: 64,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 14,
    borderRadius: 12,
    backgroundColor: potatoColors.accentLight,
  },
  addButtonText: {
    color: '#3C1E1E',
    fontSize: 14,
    fontWeight: '700',
  },
  pressed: {
    opacity: 0.8,
  },
  error: {
    marginBottom: 8,
    color: '#B33D46',
    fontSize: 13,
  },
  friendList: {
    marginTop: 8,
  },
  friendCard: {
    minHeight: 72,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginVertical: 6,
    padding: 16,
    borderRadius: 12,
    backgroundColor: potatoColors.white,
    elevation: 1,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 2,
  },
  friendMain: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginRight: 12,
  },
  friendIdentity: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  avatar: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 20,
    backgroundColor: '#E0E0E0',
  },
  avatarText: {
    color: '#424242',
    fontWeight: '700',
  },
  friendName: {
    marginLeft: 12,
    color: potatoColors.text,
    fontSize: 16,
    fontWeight: '700',
  },
  selectionBox: {
    width: 22,
    height: 22,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#BDBDBD',
    borderRadius: 4,
    backgroundColor: potatoColors.white,
  },
  selectionBoxSelected: {
    borderColor: potatoColors.accentLight,
    backgroundColor: potatoColors.accentLight,
  },
  selectionCheck: {
    color: '#3C1E1E',
    fontSize: 15,
    fontWeight: '700',
  },
  friendBadge: {
    borderRadius: 8,
    backgroundColor: '#FFF3E0',
  },
  deleteButton: {
    paddingHorizontal: 8,
    paddingVertical: 6,
  },
  deleteButtonText: {
    color: '#B33D46',
    fontSize: 12,
    fontWeight: '700',
  },
  friendBadgeText: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    color: '#FF8F00',
    fontSize: 12,
  },
  emptyState: {
    minHeight: 120,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 12,
    backgroundColor: potatoColors.white,
  },
  emptyText: {
    color: potatoColors.placeholder,
    fontSize: 14,
  },
});
