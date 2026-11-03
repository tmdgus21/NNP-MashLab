import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { AuthErrorMessage } from '../components/AuthErrorMessage';
import { AuthTextInput } from '../components/AuthTextInput';
import { PotatoApiError, type PotatoApi, type RoomView } from '../services/potatoApi';
import { potatoColors } from '../theme/colors';

interface JoinRoomScreenProps {
  api: PotatoApi;
  defaultNickname: string;
  onBack: () => void;
  onJoined: (room: RoomView) => void;
  initialCode?: string;
}

/** Joining with the room code is acceptance; nothing is sent until the user taps. */
export function JoinRoomScreen({ api, defaultNickname, onBack, onJoined, initialCode = '' }: JoinRoomScreenProps) {
  const [code, setCode] = useState(initialCode);
  const [nickname, setNickname] = useState(defaultNickname);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const join = async () => {
    setError('');
    if (!/^[A-Za-z2-9]{8}$/.test(code.trim())) {
      setError('초대 코드는 영문·숫자 8자리예요.');
      return;
    }
    if (!nickname.trim()) {
      setError('이 모임에서 쓸 이름을 입력해 주세요.');
      return;
    }
    setSubmitting(true);
    try {
      onJoined(await api.rooms.join(code, nickname.trim()));
    } catch (failure) {
      setError(failure instanceof PotatoApiError ? failure.message : '참가하지 못했어요.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={styles.safe}>
      <Pressable accessibilityRole="button" accessibilityLabel="뒤로" onPress={onBack} style={styles.back}>
        <Text style={styles.backText}>‹</Text>
      </Pressable>
      <View style={styles.form}>
        <Text style={styles.title}>초대 코드로 참가</Text>
        <AuthTextInput
          accessibilityLabel="초대 코드 입력"
          autoCapitalize="characters"
          onChangeText={setCode}
          placeholder="초대 코드 8자리"
          value={code}
        />
        <AuthTextInput
          accessibilityLabel="이 모임에서 쓸 이름"
          onChangeText={setNickname}
          placeholder="이 모임에서 쓸 이름"
          value={nickname}
        />
        <Text style={styles.hint}>참가하면 이 모임에 참석한다는 뜻이에요. 시간은 다음 화면에서 입력해요.</Text>
        <AuthErrorMessage message={error} />
        <Pressable
          accessibilityRole="button"
          disabled={submitting}
          onPress={() => void join()}
          style={[styles.button, submitting && styles.disabled]}
        >
          <Text style={styles.buttonText}>{submitting ? '참가 중' : '참가하기'}</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: potatoColors.background },
  back: { width: 48, height: 48, alignItems: 'center', justifyContent: 'center' },
  backText: { fontSize: 30, color: potatoColors.brown },
  form: { padding: 24, gap: 12 },
  title: { fontSize: 22, fontWeight: '700', color: potatoColors.text, marginBottom: 8 },
  hint: { fontSize: 13, color: potatoColors.muted },
  button: { height: 52, borderRadius: 26, alignItems: 'center', justifyContent: 'center', backgroundColor: potatoColors.brown, marginTop: 8 },
  buttonText: { color: potatoColors.white, fontSize: 17, fontWeight: '700' },
  disabled: { opacity: 0.6 },
});
