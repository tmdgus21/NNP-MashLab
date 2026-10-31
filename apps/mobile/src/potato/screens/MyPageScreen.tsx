import React from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { CustomBottomBar } from '../components/CustomBottomBar';
import { potatoColors } from '../theme/colors';
import type { PotatoTabRoute } from '../types/appointment';

interface MyPageScreenProps {
  nickname: string;
  userId: string;
  onLogoutClick: () => void;
  onTabSelected?: (route: PotatoTabRoute) => void;
}

const menuItems = [
  '내 캘린더',
  '캘린더 연결',
  '알림 설정',
  'AI 설정 (선택 시간, 요일 등)',
  '친구 관리',
  '설정',
  '도움말',
] as const;

export function MyPageScreen({
  nickname,
  userId,
  onLogoutClick,
  onTabSelected,
}: MyPageScreenProps) {
  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={styles.safeArea}>
      <View style={styles.content}>
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          <Text style={styles.title}>마이페이지</Text>

          <View style={styles.profileCard}>
            <View style={styles.avatar}>
              <Text style={styles.avatarText}>{nickname.slice(0, 1)}</Text>
            </View>
            <View style={styles.profileDetails}>
              <Text numberOfLines={1} style={styles.nickname}>
                {nickname}
              </Text>
              <Text numberOfLines={1} style={styles.userId}>
                {userId}
              </Text>
            </View>
            <View
              accessibilityLabel="프로필 수정"
              style={styles.editProfileButton}
            >
              <Text style={styles.editProfileText}>프로필 수정</Text>
            </View>
          </View>

          <View style={styles.menuList}>
            {menuItems.map(item => (
              <View key={item} style={styles.menuCard}>
                <Text style={styles.menuText}>{item}</Text>
                <Text style={styles.menuArrow}>〉</Text>
              </View>
            ))}
          </View>

          <Pressable
            accessibilityRole="button"
            onPress={onLogoutClick}
            style={({ pressed }) => [
              styles.logoutButton,
              pressed && styles.pressed,
            ]}
          >
            <Text style={styles.logoutText}>로그아웃</Text>
          </Pressable>
        </ScrollView>
      </View>
      <CustomBottomBar
        currentRoute="mypage"
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
  scrollContent: {
    padding: 20,
    paddingBottom: 24,
  },
  title: {
    marginBottom: 16,
    color: potatoColors.text,
    fontSize: 22,
    fontWeight: '700',
  },
  profileCard: {
    minHeight: 100,
    flexDirection: 'row',
    alignItems: 'center',
    padding: 20,
    borderRadius: 16,
    backgroundColor: potatoColors.white,
    elevation: 2,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 3,
  },
  avatar: {
    width: 60,
    height: 60,
    flexShrink: 0,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 30,
    backgroundColor: '#D7CCC8',
  },
  avatarText: {
    color: potatoColors.white,
    fontSize: 24,
    fontWeight: '700',
  },
  profileDetails: {
    flex: 1,
    minWidth: 0,
    marginLeft: 16,
    marginRight: 8,
  },
  nickname: {
    color: potatoColors.text,
    fontSize: 18,
    fontWeight: '700',
  },
  userId: {
    marginTop: 2,
    color: '#777777',
    fontSize: 13,
  },
  editProfileButton: {
    flexShrink: 0,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderWidth: 1,
    borderColor: '#BDBDBD',
    borderRadius: 20,
  },
  editProfileText: {
    color: '#555555',
    fontSize: 12,
  },
  menuList: {
    marginTop: 16,
  },
  menuCard: {
    minHeight: 52,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginVertical: 4,
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderRadius: 12,
    backgroundColor: potatoColors.white,
    elevation: 1,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 2,
  },
  menuText: {
    flex: 1,
    color: potatoColors.text,
    fontSize: 15,
  },
  menuArrow: {
    marginLeft: 12,
    color: potatoColors.placeholder,
    fontSize: 14,
  },
  logoutButton: {
    height: 48,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 16,
    borderRadius: 24,
    backgroundColor: '#FFCDD2',
  },
  logoutText: {
    color: '#C62828',
    fontSize: 15,
    fontWeight: '700',
  },
  pressed: {
    opacity: 0.8,
  },
});
