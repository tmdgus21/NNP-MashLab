import React, { useEffect } from 'react';
import { Pressable, StatusBar, Text, View } from 'react-native';
import { NavigationContainer, DefaultTheme } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { useApp } from './src/state/store';
import { WelcomeScreen } from './src/screens/WelcomeScreen';
import { OverviewScreen } from './src/screens/OverviewScreen';
import { ConditionsScreen } from './src/screens/ConditionsScreen';
import { ScheduleScreen } from './src/screens/ScheduleScreen';
import { Loading } from './src/ui/components';
import { colors, ui } from './src/ui/theme';
import { repository } from './src/data/repositoryInstance';
const Tab = createBottomTabNavigator();
const icons: Record<string, string> = {
  현황: '▥',
  '내 조건': '▦',
  담당표: '✓',
};
function Content() {
  const app = useApp();
  useEffect(() => {
    void useApp.getState().restore();
  }, []);
  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={ui.page}>
      <View
        style={[
          ui.row,
          {
            paddingHorizontal: 20,
            paddingVertical: 12,
            justifyContent: 'space-between',
            backgroundColor: colors.white,
          },
        ]}
      >
        <Text
          style={{ fontSize: 21, fontWeight: '900', color: colors.primary }}
        >
          조건부 OK
          <Text style={{ fontSize: 10, color: colors.muted }}>
            {repository.mode === 'mock' ? '   DEMO' : ''}
          </Text>
        </Text>
        {app.meeting && (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="모임 나가기"
            onPress={app.leave}
            style={{ padding: 10 }}
          >
            <Text style={ui.small}>모임 전환</Text>
          </Pressable>
        )}
      </View>
      {!!app.busy && <Loading label={app.busy} />}
      {!!app.error && (
        <View
          accessibilityLiveRegion="assertive"
          style={{ padding: 16, backgroundColor: '#FFF0EB', gap: 8 }}
        >
          <Text style={{ color: colors.danger, fontSize: 14 }}>
            {app.error}
          </Text>
          <View style={ui.row}>
            <Pressable
              onPress={() => {
                void (app.meeting ? app.refresh() : app.restore());
              }}
              style={{ padding: 8 }}
            >
              <Text style={{ color: colors.danger }}>다시 시도</Text>
            </Pressable>
            <Pressable onPress={app.clearError} style={{ padding: 8 }}>
              <Text style={ui.muted}>닫기</Text>
            </Pressable>
          </View>
        </View>
      )}
      {!app.ready ? (
        <View style={ui.flex} />
      ) : !app.meeting ? (
        <WelcomeScreen />
      ) : (
        <NavigationContainer
          theme={{
            ...DefaultTheme,
            colors: {
              ...DefaultTheme.colors,
              background: colors.bg,
              primary: colors.primary,
            },
          }}
        >
          <Tab.Navigator
            screenOptions={({ route }) => ({
              headerShown: false,
              tabBarActiveTintColor: colors.primary,
              tabBarInactiveTintColor: colors.muted,
              tabBarLabelStyle: { fontSize: 12, fontWeight: '700' },
              tabBarStyle: { paddingTop: 6 },
              tabBarIcon: ({ color }) => (
                <Text style={{ color, fontSize: 23 }}>{icons[route.name]}</Text>
              ),
            })}
          >
            <Tab.Screen name="현황" component={OverviewScreen} />
            <Tab.Screen name="내 조건" component={ConditionsScreen} />
            <Tab.Screen name="담당표" component={ScheduleScreen} />
          </Tab.Navigator>
        </NavigationContainer>
      )}
    </SafeAreaView>
  );
}
export default function App() {
  return (
    <GestureHandlerRootView style={ui.flex}>
      <SafeAreaProvider>
        <StatusBar barStyle="dark-content" />
        <Content />
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
