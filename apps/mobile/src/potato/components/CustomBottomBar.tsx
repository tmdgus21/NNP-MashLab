import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { potatoColors } from '../theme/colors';
import type { PotatoTabRoute } from '../types/appointment';

interface CustomBottomBarProps {
  currentRoute: PotatoTabRoute;
  onTabSelected: (route: PotatoTabRoute) => void;
}

const items: ReadonlyArray<{
  route: PotatoTabRoute;
  label: string;
  icon: string;
}> = [
  { route: 'home', label: '홈', icon: '🏠' },
  { route: 'create_step1', label: '모임만들기', icon: '➕' },
  { route: 'friends', label: '친구', icon: '👥' },
  { route: 'mypage', label: 'MY', icon: '👤' },
];

export function CustomBottomBar({
  currentRoute,
  onTabSelected,
}: CustomBottomBarProps) {
  return (
    <View style={styles.bar}>
      {items.map(item => {
        const selected =
          currentRoute === item.route ||
          (currentRoute.startsWith('create_') &&
            item.route === 'create_step1');

        return (
          <Pressable
            accessibilityRole="button"
            accessibilityState={{ selected }}
            key={item.route}
            onPress={() => onTabSelected(item.route)}
            style={styles.item}
          >
            <Text
              style={[
                styles.icon,
                { color: selected ? potatoColors.orange : potatoColors.muted },
              ]}
            >
              {item.icon}
            </Text>
            <Text
              style={[
                styles.label,
                selected ? styles.selectedLabel : styles.unselectedLabel,
              ]}
            >
              {item.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    height: 65,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    paddingHorizontal: 12,
    backgroundColor: potatoColors.white,
    elevation: 8,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: -2 },
    shadowOpacity: 0.1,
    shadowRadius: 5,
  },
  item: {
    minWidth: 64,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  icon: {
    fontSize: 18,
  },
  label: {
    marginTop: 2,
    fontSize: 11,
  },
  selectedLabel: {
    color: potatoColors.orange,
    fontWeight: '700',
  },
  unselectedLabel: {
    color: potatoColors.muted,
    fontWeight: '400',
  },
});
