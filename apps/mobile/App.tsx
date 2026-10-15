import React, { useEffect, useState } from 'react';
import {
  Linking,
  Pressable,
  StatusBar,
  Text,
  View,
  useWindowDimensions,
} from 'react-native';
import { NavigationContainer, DefaultTheme } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import {
  SafeAreaProvider,
  SafeAreaView,
  useSafeAreaInsets,
} from 'react-native-safe-area-context';
import { useApp } from './src/state/store';
import { WelcomeScreen } from './src/screens/WelcomeScreen';
import { OverviewScreen } from './src/screens/OverviewScreen';
import { ConditionsScreen } from './src/screens/ConditionsScreen';
import { ScheduleScreen } from './src/screens/ScheduleScreen';
import { Button, Loading, StatusCard } from './src/ui/components';
import { colors, ui } from './src/ui/theme';
import { invitationCode } from './src/domain/invitation';
import { INVITE_BASE_URL } from './src/config/runtime.generated';
const Tab = createBottomTabNavigator();
import { NavigationIcon } from './src/ui/NavigationIcon';
import { InvitationSheet } from './src/ui/InvitationSheet';
function Content() {
  const app = useApp();
  const { fontScale } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const [inviting, setInviting] = useState(false);
  useEffect(() => {
    const accept = (url: string) => {
      const code = invitationCode(url, INVITE_BASE_URL);
      if (code) {
        useApp.getState().invite(code);
      }
    };
    void useApp
      .getState()
      .restore()
      .then(() => Linking.getInitialURL())
      .then(url => {
        if (url) {
          accept(url);
        }
      });
    const subscription = Linking.addEventListener('url', ({ url }) =>
      accept(url),
    );
    return () => subscription.remove();
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
        <View style={{ flex: 1, gap: 4, marginRight: 12 }}>
          <Text numberOfLines={1} style={ui.heading}>
            {app.meeting?.title || '조건부 OK'}
          </Text>
          <Text style={ui.small}>
            {app.meeting
              ? app.meeting.status === 'finalized'
                ? '확정 완료'
                : app.meeting.status === 'reviewing'
                ? `${app.meeting.round}차 · 동의 진행 중`
                : '참여자의 조건을 모으는 중'
              : '함께 가능한 순간을 찾아요'}
          </Text>
        </View>
        {app.meeting && (
          <>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="모임 초대"
              onPress={() => setInviting(true)}
              style={[ui.chip, ui.chipSelected]}
            >
              <Text style={{ color: colors.primary, fontWeight: '700' }}>
                초대
              </Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="모임 만들기 및 내 모임 목록"
              onPress={app.leave}
              style={ui.chip}
            >
              <Text style={ui.muted}>모임</Text>
            </Pressable>
          </>
        )}
      </View>
      {inviting && app.meeting && (
        <InvitationSheet
          meeting={app.meeting}
          onClose={() => setInviting(false)}
        />
      )}
      {!!app.busy && <Loading label={app.busy} />}
      {!!app.error && (
        <View accessibilityLiveRegion="assertive" style={{ padding: 12 }}>
          <StatusCard
            kind="error"
            title="요청을 완료하지 못했어요"
            detail={app.error}
          >
            <View style={ui.wrap}>
              <Button
                title="다시 시도"
                secondary
                disabled={!!app.busy}
                onPress={() => {
                  void (app.meeting ? app.refresh() : app.restore());
                }}
              />
              <Button title="닫기" secondary onPress={app.clearError} />
            </View>
          </StatusCard>
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
              tabBarLabelPosition: 'below-icon',
              tabBarStyle: {
                height: 52 + Math.ceil(18 * fontScale) + insets.bottom,
                paddingTop: 8,
                paddingBottom: Math.max(8, insets.bottom),
                borderTopColor: colors.border,
                backgroundColor: colors.white,
              },
              tabBarHideOnKeyboard: true,
              tabBarIcon: ({ color, focused }) => (
                <View
                  style={{
                    paddingHorizontal: 18,
                    paddingVertical: 3,
                    borderRadius: 18,
                    backgroundColor: focused ? colors.pale : 'transparent',
                  }}
                >
                  <NavigationIcon name={route.name} color={color} />
                </View>
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
