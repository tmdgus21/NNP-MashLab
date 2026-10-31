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
import { BrandLogo } from '../components/BrandLogo';
import { VerificationCodeRow } from '../components/VerificationCodeRow';
import {
  errorMessage,
  type PotatoAuthService,
  unavailableAuthService,
} from '../services/authService';
import { potatoColors } from '../theme/colors';

interface LoginScreenProps {
  onLoginSuccess?: () => void;
  onSignUpPress: () => void;
  service?: PotatoAuthService;
}

export function LoginScreen({
  onLoginSuccess,
  onSignUpPress,
  service = unavailableAuthService,
}: LoginScreenProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [verificationCode, setVerificationCode] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const login = async () => {
    setError('');
    if (!email.trim()) {
      setError('아이디를 입력하지 않았습니다.');
      return;
    }
    if (!password) {
      setError('비밀번호를 입력하지 않았습니다.');
      return;
    }
    if (!verificationCode.trim()) {
      setError('이메일 인증코드를 입력해 주세요.');
      return;
    }

    setSubmitting(true);
    try {
      await service.login({
        email: email.trim(),
        password,
        verificationCode: verificationCode.trim(),
      });
      onLoginSuccess?.();
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
      <BrandLogo />
      <View style={styles.form}>
        <AuthTextInput
          accessibilityLabel="아이디 입력"
          keyboardType="email-address"
          onChangeText={setEmail}
          placeholder="아이디 입력"
          returnKeyType="next"
          value={email}
        />
        <AuthTextInput
          accessibilityLabel="비밀번호 입력"
          onChangeText={setPassword}
          placeholder="비밀번호 입력"
          returnKeyType="done"
          secureTextEntry
          value={password}
        />
        <VerificationCodeRow
          code={verificationCode}
          email={email}
          onChangeCode={setVerificationCode}
          onError={setError}
          purpose="login"
          service={service}
        />
        <AuthErrorMessage message={error} />
        <Pressable
          accessibilityRole="button"
          disabled={submitting}
          onPress={() => void login()}
          style={({ pressed }) => [
            styles.loginButton,
            submitting && styles.disabled,
            pressed && styles.pressed,
          ]}
        >
          <Text style={styles.loginButtonText}>
            {submitting ? '로그인 중' : '로그인하기'}
          </Text>
        </Pressable>
        <View style={styles.signUpPrompt}>
          <Text style={styles.promptText}>계정이 없으신가요?</Text>
          <Pressable
            accessibilityRole="button"
            onPress={onSignUpPress}
            style={styles.signUpLink}
          >
            <Text style={styles.signUpText}>회원가입</Text>
          </Pressable>
        </View>
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
  form: {
    marginTop: 24,
    gap: 10,
  },
  loginButton: {
    height: 52,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 10,
    borderRadius: 26,
    backgroundColor: potatoColors.brown,
  },
  loginButtonText: {
    color: potatoColors.white,
    fontSize: 17,
    fontWeight: '700',
  },
  disabled: {
    opacity: 0.65,
  },
  pressed: {
    opacity: 0.8,
  },
  signUpPrompt: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    marginTop: 10,
  },
  promptText: {
    color: '#999999',
    fontSize: 14,
  },
  signUpLink: {
    paddingVertical: 4,
  },
  signUpText: {
    color: potatoColors.accent,
    fontSize: 14,
    fontWeight: '700',
  },
});
