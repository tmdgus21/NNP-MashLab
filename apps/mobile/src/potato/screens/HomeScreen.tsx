import React, { useMemo, useState } from 'react';
import {
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { AppointmentDetailModal } from '../components/AppointmentDetailModal';
import { CustomBottomBar } from '../components/CustomBottomBar';
import { SwipableCalendarWidget } from '../components/SwipableCalendarWidget';
import { potatoColors } from '../theme/colors';
import type {
  PotatoAppointment,
  PotatoTabRoute,
} from '../types/appointment';

interface HomeScreenProps {
  nickname?: string;
  initialAppointments?: PotatoAppointment[];
  onLogoutPress?: () => void;
  onCreateAppointmentPress?: () => void;
  onEditAppointmentPress?: (appointment: PotatoAppointment) => void;
  onTabSelected?: (route: PotatoTabRoute) => void;
}

function dateKey(year: number, month: number, day: number): string {
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

function parseAppointmentDate(value: string): string | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) {
    return null;
  }
  const [, yearText, monthText, dayText] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const parsed = new Date(year, month - 1, day);
  if (
    parsed.getFullYear() !== year ||
    parsed.getMonth() + 1 !== month ||
    parsed.getDate() !== day
  ) {
    return null;
  }
  return dateKey(year, month, day);
}

export function HomeScreen({
  nickname = '',
  initialAppointments = [],
  onLogoutPress,
  onCreateAppointmentPress,
  onEditAppointmentPress,
  onTabSelected,
}: HomeScreenProps) {
  const today = new Date();
  const [appointments, setAppointments] = useState(initialAppointments);
  const [selectedDate, setSelectedDate] = useState({
    year: today.getFullYear(),
    month: today.getMonth() + 1,
    day: today.getDate(),
  });
  const [selectedAppointment, setSelectedAppointment] =
    useState<PotatoAppointment | null>(null);
  const [showAllAppointments, setShowAllAppointments] = useState(false);

  const markedDates = useMemo(
    () =>
      new Set(
        appointments
          .map(appointment => parseAppointmentDate(appointment.date))
          .filter((date): date is string => date !== null),
      ),
    [appointments],
  );

  const selectedDateKey = dateKey(
    selectedDate.year,
    selectedDate.month,
    selectedDate.day,
  );
  const visibleAppointments = useMemo(
    () =>
      appointments
        .filter(appointment => {
          if (showAllAppointments) {
            return true;
          }
          return parseAppointmentDate(appointment.date) === selectedDateKey;
        })
        .sort((left, right) => left.date.localeCompare(right.date)),
    [appointments, selectedDateKey, showAllAppointments],
  );

  const changeMonth = (year: number, month: number) => {
    const lastDay = new Date(year, month, 0).getDate();
    setSelectedDate(current => ({
      year,
      month,
      day: Math.min(current.day, lastDay),
    }));
    setShowAllAppointments(false);
  };

  const selectDay = (year: number, month: number, day: number) => {
    setSelectedDate({ year, month, day });
    setShowAllAppointments(false);
  };

  const deleteAppointment = (appointment: PotatoAppointment) => {
    setAppointments(current =>
      current.filter(item => item.id !== appointment.id),
    );
    setSelectedAppointment(null);
  };

  const editAppointment = (appointment: PotatoAppointment) => {
    setSelectedAppointment(null);
    onEditAppointmentPress?.(appointment);
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.header}>
        <Text style={styles.wordmark}>
          <Text style={styles.potato}>potato </Text>
          <Text style={styles.meet}>meet</Text>
        </Text>
        <Pressable
          accessibilityRole="button"
          onPress={onLogoutPress}
          style={styles.logoutButton}
        >
          <Text style={styles.logoutText}>로그아웃</Text>
        </Pressable>
      </View>

      <View style={styles.main}>
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.greeting}>
            <Text style={styles.greetingTitle}>
              안녕하세요
              {nickname.trim() ? (
                <>
                  ,{' '}
                  <Text
                    style={
                      nickname.trim() === '관리자'
                        ? styles.adminNickname
                        : styles.nickname
                    }
                  >
                    {nickname.trim()}
                  </Text>
                  님!
                </>
              ) : (
                '!'
              )}{' '}
              👋
            </Text>
            <Text style={styles.greetingSubtitle}>오늘도 좋은 하루 보내세요!</Text>
          </View>

          <View style={styles.calendarCard}>
            <SwipableCalendarWidget
              year={selectedDate.year}
              month={selectedDate.month}
              selectedDay={selectedDate.day}
              markedDates={markedDates}
              onMonthChange={changeMonth}
              onDayChange={selectDay}
            />
          </View>

          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>다가오는 모임</Text>
            <Pressable
              accessibilityRole="button"
              onPress={() => setShowAllAppointments(current => !current)}
              style={styles.viewAllButton}
            >
              <Text style={styles.viewAllText}>
                {showAllAppointments ? '선택 날짜 보기' : '전체보기 >'}
              </Text>
            </Pressable>
          </View>

          {visibleAppointments.length === 0 ? (
            <View style={styles.emptyState}>
              <Text style={styles.emptyText}>
                {appointments.length === 0
                  ? '모임이 없습니다.'
                  : '선택한 날짜에 모임이 없습니다.'}
              </Text>
            </View>
          ) : (
            <View style={styles.appointmentList}>
              {visibleAppointments.map(appointment => (
                <Pressable
                  accessibilityRole="button"
                  key={appointment.id}
                  onPress={() => setSelectedAppointment(appointment)}
                  style={({ pressed }) => [
                    styles.appointmentCard,
                    pressed && styles.pressedCard,
                  ]}
                >
                  <View style={styles.appointmentTitleRow}>
                    <Text style={styles.appointmentTitle}>
                      {appointment.title}
                    </Text>
                    <View style={styles.confirmedBadge}>
                      <Text style={styles.confirmedText}>확정</Text>
                    </View>
                  </View>
                  <Text style={styles.appointmentMeta}>
                    📅 {appointment.timeInfo}
                  </Text>
                  <Text style={styles.appointmentMeta}>
                    📍 {appointment.location} ({appointment.category})
                  </Text>
                </Pressable>
              ))}
            </View>
          )}
          <View style={styles.bottomSpacer} />
        </ScrollView>

        <Pressable
          accessibilityRole="button"
          onPress={onCreateAppointmentPress}
          style={({ pressed }) => [
            styles.createButton,
            pressed && styles.createButtonPressed,
          ]}
        >
          <Text style={styles.createButtonText}>+ 모임 만들기</Text>
        </Pressable>
      </View>

      <CustomBottomBar
        currentRoute="home"
        onTabSelected={route => onTabSelected?.(route)}
      />
      <AppointmentDetailModal
        appointment={selectedAppointment}
        onClose={() => setSelectedAppointment(null)}
        onDelete={deleteAppointment}
        onEdit={editAppointment}
      />
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
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 12,
    backgroundColor: potatoColors.background,
  },
  wordmark: {
    fontSize: 24,
    fontWeight: '800',
  },
  potato: {
    color: potatoColors.brown,
  },
  meet: {
    color: potatoColors.orange,
  },
  logoutButton: {
    paddingHorizontal: 6,
    paddingVertical: 4,
  },
  logoutText: {
    color: potatoColors.placeholder,
    fontSize: 11,
  },
  main: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingBottom: 80,
  },
  greeting: {
    marginTop: 16,
  },
  greetingTitle: {
    color: potatoColors.text,
    fontSize: 20,
    fontWeight: '700',
  },
  nickname: {
    color: potatoColors.text,
    fontWeight: '700',
  },
  adminNickname: {
    color: '#2196F3',
    fontWeight: '700',
  },
  greetingSubtitle: {
    marginTop: 2,
    color: '#777777',
    fontSize: 13,
  },
  calendarCard: {
    marginTop: 26,
    padding: 16,
    borderRadius: 18,
    backgroundColor: potatoColors.white,
    elevation: 2,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 3,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 20,
    marginBottom: 10,
  },
  sectionTitle: {
    color: potatoColors.text,
    fontSize: 16,
    fontWeight: '700',
  },
  viewAllButton: {
    paddingVertical: 4,
  },
  viewAllText: {
    color: potatoColors.muted,
    fontSize: 13,
  },
  emptyState: {
    height: 90,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 16,
    backgroundColor: potatoColors.white,
  },
  emptyText: {
    color: potatoColors.placeholder,
    fontSize: 14,
  },
  appointmentList: {
    gap: 10,
  },
  appointmentCard: {
    padding: 16,
    borderRadius: 16,
    backgroundColor: potatoColors.white,
    elevation: 1,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 2,
  },
  pressedCard: {
    opacity: 0.8,
  },
  appointmentTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
    marginBottom: 6,
  },
  appointmentTitle: {
    flex: 1,
    color: potatoColors.text,
    fontSize: 15,
    fontWeight: '700',
  },
  confirmedBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
    backgroundColor: '#E8F5E9',
  },
  confirmedText: {
    color: '#2E7D32',
    fontSize: 11,
    fontWeight: '700',
  },
  appointmentMeta: {
    marginTop: 2,
    color: '#666666',
    fontSize: 13,
  },
  bottomSpacer: {
    height: 20,
  },
  createButton: {
    position: 'absolute',
    right: 20,
    bottom: 20,
    width: 130,
    height: 38,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 19,
    backgroundColor: potatoColors.accentLight,
    elevation: 6,
  },
  createButtonPressed: {
    opacity: 0.8,
  },
  createButtonText: {
    color: '#3C1E1E',
    fontSize: 13,
    fontWeight: '700',
  },
});
