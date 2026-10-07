import React from 'react';
import {
  ActivityIndicator,
  Pressable,
  Text,
  TextInput,
  TextInputProps,
  View,
} from 'react-native';
import { colors, ui } from './theme';
export function Button({
  title,
  onPress,
  disabled,
  secondary = false,
  testID,
}: {
  title: string;
  onPress(): void;
  disabled?: boolean;
  secondary?: boolean;
  testID?: string;
}) {
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={title}
      accessibilityState={{ disabled: !!disabled }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        ui.button,
        secondary && { backgroundColor: colors.pale },
        { opacity: disabled ? 0.4 : pressed ? 0.7 : 1 },
      ]}
    >
      <Text style={[ui.buttonText, secondary && { color: colors.primary }]}>
        {title}
      </Text>
    </Pressable>
  );
}
export function Chip({
  title,
  selected,
  onPress,
}: {
  title: string;
  selected?: boolean;
  onPress(): void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={title}
      accessibilityState={{ selected: !!selected }}
      onPress={onPress}
      style={[ui.chip, selected && ui.chipSelected]}
    >
      <Text
        style={[
          ui.text,
          selected && { color: colors.primary, fontWeight: '700' },
        ]}
      >
        {title}
      </Text>
    </Pressable>
  );
}
export function Field({ label, ...props }: TextInputProps & { label: string }) {
  return (
    <View style={{ gap: 6 }}>
      <Text style={ui.muted}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        placeholderTextColor={colors.muted}
        style={ui.input}
        {...props}
      />
    </View>
  );
}
export function StatusCard({
  title,
  detail,
  kind = 'info',
  children,
}: {
  title: string;
  detail: string;
  kind?: 'info' | 'warning' | 'error';
  children?: React.ReactNode;
}) {
  const color =
    kind === 'error'
      ? colors.danger
      : kind === 'warning'
      ? colors.warn
      : colors.primary;
  return (
    <View style={[ui.card, { borderLeftWidth: 4, borderLeftColor: color }]}>
      <Text style={[ui.heading, { color }]}>{title}</Text>
      <Text style={ui.muted}>{detail}</Text>
      {children}
    </View>
  );
}
export function Loading({ label }: { label: string }) {
  return (
    <View
      accessibilityLiveRegion="polite"
      style={[ui.row, { padding: 14, backgroundColor: colors.pale }]}
    >
      <ActivityIndicator color={colors.primary} />
      <Text style={ui.text}>{label}</Text>
    </View>
  );
}
