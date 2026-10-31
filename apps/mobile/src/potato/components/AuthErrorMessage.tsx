import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { potatoColors } from '../theme/colors';

interface AuthErrorMessageProps {
  message: string;
}

export function AuthErrorMessage({ message }: AuthErrorMessageProps) {
  if (!message) {
    return null;
  }

  return (
    <View
      accessibilityLiveRegion="assertive"
      style={styles.container}
    >
      <Text style={styles.text}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 12,
    borderRadius: 12,
    backgroundColor: potatoColors.errorBackground,
  },
  text: {
    color: potatoColors.errorText,
    fontSize: 13,
    lineHeight: 19,
  },
});
