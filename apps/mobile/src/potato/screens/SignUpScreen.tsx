import React, { useState } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { AuthErrorMessage } from '../components/AuthErrorMessage';
import { AuthTextInput } from '../components/AuthTextInput';
import { VerificationCodeRow } from '../components/VerificationCodeRow';
import {
  errorMessage,
  type PotatoAuthService,
  unavailableAuthService,
} from '../services/authService';
import { potatoColors } from '../theme/colors';

interface SignUpScreenProps {
  onLoginPress: () => void;
  service?: PotatoAuthService;
}

export function SignUpScreen({
  onLoginPress,
  service = unavailableAuthService,
}: SignUpScreenProps) {
  const [nickname, setNickname] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirmation, setPasswordConfirmation] = useState('');
  const [verificationCode, setVerificationCode] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const signUp = async () => {
    setError('');
    if (!nickname.trim()) {
      setError('닉네임을 입력하지 않았습니다.');
      return;
    }
    if (!email.trim()) {
      setError('아이디를 입력하지 않았습니다.');
      return;
    }
    if (!password) {
      setError('비밀번호를 입력하지 않았습니다.');
      return;
    }
    if (!passwordConfirmation) {
      setError('비밀번호 확인을 입력하지 않았습니다.');
      return;
    }
    if (!verificationCode.trim()) {
      setError('이메일 인증코드를 입력해 주세요.');
      return;
    }
    if (password !== passwordConfirmation) {
      setError('비밀번호가 일치하지 않습니다.');
      return;
    }

    setSubmitting(true);
    try {
      await service.signUp({
        nickname: nickname.trim(),
        email: email.trim(),
        password,
        verificationCode: verificationCode.trim(),
      });
      onLoginPress();
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ScrollView
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
    >
      <Text style={styles.title}>회원가입</Text>
      <View style={styles.form}>
        <AuthTextInput
          accessibilityLabel="사용할 닉네임"
          autoCapitalize="words"
          onChangeText={setNickname}
          placeholder="사용할 닉네임"
          returnKeyType="next"
          value={nickname}
        />
        <AuthTextInput
          accessibilityLabel="아이디 (이메일 형태)"
          keyboardType="email-address"
          onChangeText={setEmail}
          placeholder="아이디 (이메일 형태)"
          returnKeyType="next"
          value={email}
        />
        <AuthTextInput
          accessibilityLabel="비밀번호"
          onChangeText={setPassword}
          placeholder="비밀번호"
          returnKeyType="next"
          secureTextEntry
          value={password}
        />
        <AuthTextInput
          accessibilityLabel="비밀번호 확인"
          onChangeText={setPasswordConfirmation}
          placeholder="비밀번호 확인"
          returnKeyType="done"
          secureTextEntry
          value={passwordConfirmation}
        />
        <VerificationCodeRow
          code={verificationCode}
          email={email}
          onChangeCode={setVerificationCode}
          onError={setError}
          purpose="signup"
          service={service}
        />
        <AuthErrorMessage message={error} />
        <Pressable
          accessibilityRole="button"
          disabled={submitting}
          onPress={() => void signUp()}
          style={({ pressed }) => [
            styles.completeButton,
            submitting && styles.disabled,
            pressed && styles.pressed,
          ]}
        >
          <Text style={styles.completeButtonText}>
            {submitting ? '요청 중' : '회원가입 완료'}
          </Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          onPress={onLoginPress}
          style={styles.backButton}
        >
          <Text style={styles.backButtonText}>돌아가기</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: 30,
    paddingVertical: 24,
  },
  title: {
    color: potatoColors.text,
    fontSize: 22,
    fontWeight: '700',
    textAlign: 'center',
  },
  form: {
    marginTop: 20,
    gap: 10,
  },
  completeButton: {
    height: 52,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 10,
    borderRadius: 26,
    backgroundColor: potatoColors.accentLight,
  },
  completeButtonText: {
    color: '#3C1E1E',
    fontSize: 17,
    fontWeight: '700',
  },
  disabled: {
    opacity: 0.65,
  },
  pressed: {
    opacity: 0.8,
  },
  backButton: {
    alignSelf: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  backButtonText: {
    color: potatoColors.muted,
    fontSize: 14,
  },
});
