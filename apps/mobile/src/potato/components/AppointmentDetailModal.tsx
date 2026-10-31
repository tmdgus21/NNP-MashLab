import React from 'react';
import {
  Alert,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { potatoColors } from '../theme/colors';
import type { PotatoAppointment } from '../types/appointment';

interface AppointmentDetailModalProps {
  appointment: PotatoAppointment | null;
  onClose: () => void;
  onDelete: (appointment: PotatoAppointment) => void;
  onEdit: (appointment: PotatoAppointment) => void;
}

export function AppointmentDetailModal({
  appointment,
  onClose,
  onDelete,
  onEdit,
}: AppointmentDetailModalProps) {
  if (!appointment) {
    return null;
  }

  const confirmDelete = () => {
    Alert.alert('모임 삭제', '정말 모임을 삭제하시겠습니까?', [
      { text: '취소', style: 'cancel' },
      {
        text: '삭제',
        style: 'destructive',
        onPress: () => onDelete(appointment),
      },
    ]);
  };

  return (
    <Modal
      animationType="fade"
      onRequestClose={onClose}
      transparent
      visible
    >
      <View style={styles.backdrop}>
        <View style={styles.dialog}>
          <View style={styles.titleRow}>
            <Text style={styles.title}>모임 상세 정보</Text>
            <Pressable
              accessibilityRole="button"
              onPress={confirmDelete}
              style={styles.deleteButton}
            >
              <Text style={styles.deleteText}>🗑️ 삭제</Text>
            </Pressable>
          </View>
          <ScrollView contentContainerStyle={styles.details}>
            <Text style={styles.detail}>📌 모임 이름: {appointment.title}</Text>
            <Text style={styles.detail}>🏷️ 카테고리: {appointment.category}</Text>
            <Text style={styles.detail}>⏱️ 소요 시간: {appointment.duration}</Text>
            <Text style={styles.detail}>📍 장소: {appointment.location}</Text>
            <Text style={styles.detail}>📅 시간: {appointment.timeInfo}</Text>
            {appointment.invitedFriends.length > 0 && (
              <Text style={styles.detail}>
                👥 초대된 친구: {appointment.invitedFriends.join(', ')}
              </Text>
            )}
          </ScrollView>
          <View style={styles.actions}>
            <Pressable
              accessibilityRole="button"
              onPress={onClose}
              style={styles.closeButton}
            >
              <Text style={styles.closeText}>닫기</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={() => onEdit(appointment)}
              style={styles.editButton}
            >
              <Text style={styles.editText}>수정</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    justifyContent: 'center',
    padding: 24,
    backgroundColor: '#00000066',
  },
  dialog: {
    maxHeight: '80%',
    padding: 20,
    borderRadius: 20,
    backgroundColor: potatoColors.white,
    elevation: 8,
  },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  title: {
    flex: 1,
    color: potatoColors.text,
    fontSize: 18,
    fontWeight: '700',
  },
  deleteButton: {
    padding: 6,
  },
  deleteText: {
    color: '#D32F2F',
    fontSize: 13,
    fontWeight: '700',
  },
  details: {
    gap: 12,
    paddingVertical: 20,
  },
  detail: {
    color: '#666666',
    fontSize: 14,
    lineHeight: 21,
  },
  actions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 10,
  },
  closeButton: {
    justifyContent: 'center',
    paddingHorizontal: 16,
    paddingVertical: 11,
  },
  closeText: {
    color: potatoColors.muted,
    fontWeight: '700',
  },
  editButton: {
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: 76,
    paddingHorizontal: 16,
    paddingVertical: 11,
    borderRadius: 10,
    backgroundColor: potatoColors.accentLight,
  },
  editText: {
    color: '#3C1E1E',
    fontWeight: '700',
  },
});
