import React, { useState } from 'react';
import {
  Modal,
  NativeModules,
  ScrollView,
  Share,
  Text,
  View,
  useWindowDimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import QRCode from 'react-native-qrcode-svg';
import { Meeting } from '../domain/model';
import { INVITE_BASE_URL } from '../config/runtime.generated';
import { Button, StatusCard } from './components';
import { colors, ui } from './theme';

export function InvitationSheet({
  meeting,
  onClose,
}: {
  meeting: Meeting;
  onClose(): void;
}) {
  const { width } = useWindowDimensions();
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');
  const url = `${INVITE_BASE_URL}/join?code=${encodeURIComponent(
    meeting.roomCode,
  )}`;
  const message = `조건부 OK · ${meeting.title}\n초대 코드: ${meeting.roomCode}\n${url}`;
  const share = async (kakao: boolean) => {
    setError('');
    try {
      if (kakao) {
        await NativeModules.ConditionalOKInvitation.shareKakao(message);
      } else {
        await Share.share({ message });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '공유 화면을 열지 못했어요.');
    }
  };
  return (
    <Modal visible transparent animationType="slide" onRequestClose={onClose}>
      <View style={ui.modalBackdrop}>
        <SafeAreaView edges={['bottom']} style={ui.sheet}>
          <ScrollView contentContainerStyle={ui.content}>
            <Text style={ui.eyebrow}>함께 시작하기</Text>
            <Text style={ui.title}>모임에 초대해요</Text>
            <Text style={ui.muted}>
              {meeting.title} · 코드를 입력하거나 QR을 스캔해 주세요.
            </Text>
            <View style={ui.centered}>
              <Text
                selectable
                style={{
                  fontSize: 24,
                  letterSpacing: 2,
                  fontWeight: '800',
                  color: colors.primary,
                }}
              >
                {meeting.roomCode}
              </Text>
              <View
                accessible
                accessibilityLabel={`QR 초대 코드 ${meeting.roomCode}`}
                style={{ padding: 16, backgroundColor: '#FFFFFF' }}
              >
                <QRCode
                  value={url}
                  size={Math.max(100, Math.min(180, width - 144))}
                />
              </View>
            </View>
            <Button
              title={copied ? '코드 복사 완료' : '8자리 코드 복사'}
              secondary
              onPress={() => {
                setCopied(false);
                setError('');
                void NativeModules.ConditionalOKInvitation.copyCode(
                  meeting.roomCode,
                )
                  .then(() => setCopied(true))
                  .catch((e: Error) => setError(e.message));
              }}
            />
            <Text accessibilityLiveRegion="polite" style={ui.small}>
              {copied
                ? '클립보드에 초대 코드를 복사했어요.'
                : '공유 버튼은 공유 화면을 열어요. 메시지 전송은 해당 앱에서 완료해 주세요.'}
            </Text>
            {!!error && (
              <StatusCard
                kind="error"
                title="공유하지 못했어요"
                detail={error}
              />
            )}
            <Button
              title="초대 링크 공유"
              onPress={() => {
                void share(false);
              }}
            />
            <Button
              title="카카오톡으로 초대"
              secondary
              onPress={() => {
                void share(true);
              }}
            />
          </ScrollView>
          <View style={ui.dock}>
            <Button title="닫기" secondary onPress={onClose} />
          </View>
        </SafeAreaView>
      </View>
    </Modal>
  );
}
