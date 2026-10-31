import React, { useState } from 'react';
import {
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { potatoColors } from '../theme/colors';
import {
  errorMessage,
  type PotatoAuthService,
  type VerificationPurpose,
} from '../services/authService';
import { AuthTextInput } from './AuthTextInput';

interface VerificationCodeRowProps {
  code: string;
  email: string;
  onChangeCode: (value: string) => void;
  onError: (message: string) => void;
  purpose: VerificationPurpose;
  service: PotatoAuthService;
}

export function VerificationCodeRow({
  code,
  email,
  onChangeCode,
  onError,
  purpose,
  service,
}: VerificationCodeRowProps) {
  const [sending, setSending] = useState(false);

  const requestCode = async () => {
    onError('');
    if (!email.trim()) {
      onError('아이디를 입력한 뒤 인증코드를 요청해 주세요.');
      return;
    }

    setSending(true);
    try {
      await service.sendVerificationCode(email.trim(), purpose);
    } catch (error) {
      onError(errorMessage(error));
    } finally {
      setSending(false);
    }
  };

  return (
    <View style={styles.row}>
      <Pressable
        accessibilityRole="button"
        disabled={sending}
        onPress={() => void requestCode()}
        style={({ pressed }) => [
          styles.sendButton,
          sending && styles.disabled,
          pressed && styles.pressed,
        ]}
      >
        <View style={styles.googleBadge}>
          <Text style={styles.googleLetter}>G</Text>
        </View>
        <Text numberOfLines={1} style={styles.sendButtonText}>
          {sending ? '요청 중' : '인증코드 보내기'}
        </Text>
      </Pressable>
      <AuthTextInput
        accessibilityLabel="인증코드 입력"
        containerStyle={styles.codeInput}
        keyboardType="number-pad"
        onChangeText={onChangeCode}
        placeholder="인증코드 입력"
        value={code}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  sendButton: {
    height: 52,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingHorizontal: 12,
    borderRadius: 26,
    backgroundColor: potatoColors.accentLight,
  },
  disabled: {
    opacity: 0.65,
  },
  pressed: {
    opacity: 0.8,
  },
  googleBadge: {
    width: 22,
    height: 22,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 11,
    backgroundColor: potatoColors.white,
  },
  googleLetter: {
    color: '#4285F4',
    fontSize: 14,
    fontWeight: '700',
  },
  sendButtonText: {
    color: '#3C1E1E',
    fontSize: 12,
    fontWeight: '700',
  },
  codeInput: {
    flex: 1,
  },
});
