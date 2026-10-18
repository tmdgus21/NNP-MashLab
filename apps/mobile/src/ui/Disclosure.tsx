import React, { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { ui } from './theme';

export function Disclosure({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <View style={ui.section}>
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        onPress={() => setOpen(!open)}
        style={ui.chip}
      >
        <Text style={ui.text}>
          {title} {open ? '접기 −' : '펼치기 ＋'}
        </Text>
      </Pressable>
      <View
        style={{ display: open ? 'flex' : 'none', gap: 12 }}
        accessibilityElementsHidden={!open}
        importantForAccessibility={open ? 'auto' : 'no-hide-descendants'}
      >
        {children}
      </View>
    </View>
  );
}
