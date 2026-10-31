import React, { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import {
  SafeAreaView,
  useSafeAreaInsets,
} from 'react-native-safe-area-context';
import { LoginScreen } from './screens/LoginScreen';
import { SignUpScreen } from './screens/SignUpScreen';
import {
  type PotatoAuthService,
  unavailableAuthService,
} from './services/authService';
import { potatoColors } from './theme/colors';

interface PotatoAuthFlowProps {
  onLoginSuccess?: () => void;
  service?: PotatoAuthService;
}

export function PotatoAuthFlow({
  onLoginSuccess,
  service = unavailableAuthService,
}: PotatoAuthFlowProps) {
  const [screen, setScreen] = useState<'login' | 'signup'>('login');
  const insets = useSafeAreaInsets();

  return (
    <SafeAreaView
      edges={['top', 'left', 'right']}
      style={[styles.safeArea, { paddingBottom: insets.bottom }]}
    >
      <View style={styles.content}>
        {screen === 'login' ? (
          <LoginScreen
            onLoginSuccess={onLoginSuccess}
            onSignUpPress={() => setScreen('signup')}
            service={service}
          />
        ) : (
          <SignUpScreen
            onLoginPress={() => setScreen('login')}
            service={service}
          />
        )}
      </View>
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
});
