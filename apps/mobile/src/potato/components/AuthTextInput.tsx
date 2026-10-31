import React, { useState } from 'react';
import {
  StyleSheet,
  TextInput,
  type TextInputProps,
  View,
  type ViewStyle,
} from 'react-native';
import { potatoColors } from '../theme/colors';

interface AuthTextInputProps {
  accessibilityLabel: string;
  autoCapitalize?: TextInputProps['autoCapitalize'];
  containerStyle?: ViewStyle;
  keyboardType?: TextInputProps['keyboardType'];
  onChangeText: (value: string) => void;
  placeholder: string;
  returnKeyType?: TextInputProps['returnKeyType'];
  secureTextEntry?: boolean;
  value: string;
}

export function AuthTextInput({
  accessibilityLabel,
  autoCapitalize = 'none',
  containerStyle,
  keyboardType,
  onChangeText,
  placeholder,
  returnKeyType,
  secureTextEntry = false,
  value,
}: AuthTextInputProps) {
  const [focused, setFocused] = useState(false);

  return (
    <View
      style={[
        styles.container,
        focused && styles.focused,
        containerStyle,
      ]}
    >
      <TextInput
        accessibilityLabel={accessibilityLabel}
        autoCapitalize={autoCapitalize}
        keyboardType={keyboardType}
        onBlur={() => setFocused(false)}
        onChangeText={onChangeText}
        onFocus={() => setFocused(true)}
        placeholder={placeholder}
        placeholderTextColor={potatoColors.placeholder}
        returnKeyType={returnKeyType}
        secureTextEntry={secureTextEntry}
        style={styles.input}
        value={value}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    height: 52,
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: potatoColors.border,
    borderRadius: 26,
    backgroundColor: potatoColors.white,
  },
  focused: {
    borderColor: potatoColors.accentLight,
  },
  input: {
    flex: 1,
    paddingHorizontal: 18,
    paddingVertical: 0,
    color: potatoColors.text,
    fontSize: 15,
  },
});
