import React, { useState } from 'react';
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import {
  SafeAreaInsetsContext,
  useSafeAreaInsets,
} from 'react-native-safe-area-context';
import { CreateAppointmentStep1Screen } from './screens/CreateAppointmentStep1Screen';
import { CreateAppointmentStep2InviteScreen } from './screens/CreateAppointmentStep2InviteScreen';
import { CreateAppointmentStep3TimeScreen } from './screens/CreateAppointmentStep3TimeScreen';
import { CreateAppointmentStep4AdjustScreen } from './screens/CreateAppointmentStep4AdjustScreen';
import { FriendsScreen } from './screens/FriendsScreen';
import { HomeScreen } from './screens/HomeScreen';
import { LoginScreen } from './screens/LoginScreen';
import { MyPageScreen } from './screens/MyPageScreen';
import { SignUpScreen } from './screens/SignUpScreen';
import { potatoColors } from './theme/colors';
import type { PotatoAppointment, PotatoTabRoute } from './types/appointment';
import type { AppointmentCreationDraft } from './types/appointmentCreation';
import { initialPotatoFriends } from './types/friend';
import { getAppointmentRecommendationMessage } from './services/appointmentRecommendation';

type PreviewRoute =
  | 'login'
  | 'signup'
  | 'home'
  | 'friends'
  | 'mypage'
  | 'create_step1'
  | 'create_step2'
  | 'create_step3'
  | 'create_step4';

const previewRoutes: ReadonlyArray<{ route: PreviewRoute; label: string }> = [
  { route: 'login', label: '로그인' },
  { route: 'signup', label: '회원가입' },
  { route: 'home', label: '홈' },
  { route: 'friends', label: '친구' },
  { route: 'mypage', label: '마이페이지' },
  { route: 'create_step1', label: '생성 1' },
  { route: 'create_step2', label: '생성 2' },
  { route: 'create_step3', label: '생성 3' },
  { route: 'create_step4', label: '생성 4' },
];

const previewAppointments: PotatoAppointment[] = [
  {
    id: 'dev-preview-appointment',
    title: '개발 프리뷰 일정',
    category: '화면 확인',
    duration: '1시간',
    location: '샘플 장소',
    timeInfo: '14:00',
    date: '2026-10-31',
    invitedFriends: ['샘플 친구'],
  },
];

type RecommendationPreparation = Parameters<
  React.ComponentProps<
    typeof CreateAppointmentStep4AdjustScreen
  >['onRequestAiRecommendation']
>[0];

function routeForTab(route: PotatoTabRoute): PreviewRoute {
  return route === 'create_step1' ? 'create_step1' : route;
}

export function PotatoMeetDevPreview() {
  const [route, setRoute] = useState<PreviewRoute>('login');
  const [draft, setDraft] = useState<AppointmentCreationDraft>({});
  const [toolsExpanded, setToolsExpanded] = useState(true);
  const insets = useSafeAreaInsets();

  const handleAiPreparation = (preparation: RecommendationPreparation) => {
    if (preparation.status === 'ready') {
      Alert.alert(
        '개발 프리뷰',
        '추천 요청에 필요한 정보가 준비됐습니다. 실제 AI 호출이나 추천 결과는 제공하지 않습니다.',
      );
      return;
    }

    if (__DEV__) {
      console.info('AI recommendation preparation needs information', {
        missingFields: preparation.missingFields,
        invalidFields: preparation.invalidFields,
      });
    }
    Alert.alert(
      '추가 정보 필요',
      getAppointmentRecommendationMessage(preparation),
    );
  };

  const renderScreen = () => {
    switch (route) {
      case 'login':
        return (
          <LoginScreen
            onSignUpPress={() => setRoute('signup')}
          />
        );
      case 'signup':
        return <SignUpScreen onLoginPress={() => setRoute('login')} />;
      case 'home':
        return (
          <HomeScreen
            nickname="개발 프리뷰"
            initialAppointments={previewAppointments}
            onCreateAppointmentPress={() => setRoute('create_step1')}
            onTabSelected={selectedRoute =>
              setRoute(routeForTab(selectedRoute))
            }
          />
        );
      case 'friends':
        return (
          <FriendsScreen
            initialFriends={initialPotatoFriends}
            onTabSelected={selectedRoute =>
              setRoute(routeForTab(selectedRoute))
            }
          />
        );
      case 'mypage':
        return (
          <MyPageScreen
            nickname="개발 프리뷰"
            userId="개발용 샘플 계정"
            onLogoutClick={() => setRoute('login')}
            onTabSelected={selectedRoute =>
              setRoute(routeForTab(selectedRoute))
            }
          />
        );
      case 'create_step1':
        return (
          <CreateAppointmentStep1Screen
            draft={draft}
            onDraftChange={setDraft}
            onCancelClick={() => setRoute('home')}
            onBackClick={() => setRoute('home')}
            onRequestStep2={values => {
              setDraft(current => ({ ...current, ...values }));
              setRoute('create_step2');
            }}
          />
        );
      case 'create_step2':
        return (
          <CreateAppointmentStep2InviteScreen
            friends={initialPotatoFriends}
            draft={draft}
            onBack={() => setRoute('create_step1')}
            onDraftChange={setDraft}
            onRequestStep3={() => setRoute('create_step3')}
          />
        );
      case 'create_step3':
        return (
          <CreateAppointmentStep3TimeScreen
            draft={draft}
            onDraftChange={setDraft}
            onBack={() => setRoute('create_step2')}
            onRequestStep4={nextDraft => {
              setDraft(nextDraft);
              setRoute('create_step4');
            }}
          />
        );
      case 'create_step4':
        return (
          <CreateAppointmentStep4AdjustScreen
            nickname="개발 프리뷰"
            draft={draft}
            onBack={() => setRoute('create_step3')}
            onNavigateStep={step => setRoute(`create_step${step}`)}
            onRequestAiRecommendation={handleAiPreparation}
          />
        );
    }
  };

  return (
    <View style={styles.root}>
      <View
        style={[
          styles.previewPanel,
          { paddingTop: insets.top + (toolsExpanded ? 8 : 4) },
        ]}
      >
        <View style={styles.panelHeader}>
          <Text
            numberOfLines={1}
            style={styles.previewTitle}
          >
            개발 프리뷰 · {previewRoutes.find(item => item.route === route)?.label}
          </Text>
          <Pressable
            accessibilityRole="button"
            accessibilityState={{ expanded: toolsExpanded }}
            onPress={() => setToolsExpanded(expanded => !expanded)}
            style={styles.panelToggle}
          >
            <Text style={styles.panelToggleText}>
              {toolsExpanded ? '도구 접기' : '도구 열기'}
            </Text>
          </Pressable>
        </View>
        {toolsExpanded && (
          <>
            <Text style={styles.previewDescription}>
              인증/API 미연결 · 화면의 일정과 프로필은 개발용 샘플입니다.
            </Text>
            <ScrollView
              horizontal
              contentContainerStyle={styles.routeList}
              showsHorizontalScrollIndicator={false}
            >
              {previewRoutes.map(item => {
                const selected = route === item.route;
                return (
                  <Pressable
                    accessibilityRole="button"
                    accessibilityState={{ selected }}
                    key={item.route}
                    onPress={() => setRoute(item.route)}
                    testID={`dev-preview-route-${item.route}`}
                    style={[
                      styles.routeButton,
                      selected && styles.selectedRouteButton,
                    ]}
                  >
                    <Text
                      style={[
                        styles.routeLabel,
                        selected && styles.selectedRouteLabel,
                      ]}
                    >
                      {item.label}
                    </Text>
                  </Pressable>
                );
              })}
            </ScrollView>
          </>
        )}
      </View>
      <SafeAreaInsetsContext.Provider value={{ ...insets, top: 0 }}>
        <View style={styles.screen}>{renderScreen()}</View>
      </SafeAreaInsetsContext.Provider>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: potatoColors.background,
  },
  previewPanel: {
    paddingBottom: 6,
    borderBottomWidth: 1,
    borderBottomColor: potatoColors.border,
    backgroundColor: '#FFF3D6',
  },
  panelHeader: {
    minHeight: 28,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
    paddingHorizontal: 12,
  },
  previewTitle: {
    flex: 1,
    color: potatoColors.brown,
    fontSize: 12,
    fontWeight: '800',
  },
  panelToggle: {
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: 12,
    backgroundColor: potatoColors.white,
  },
  panelToggleText: {
    color: potatoColors.brown,
    fontSize: 10,
    fontWeight: '700',
  },
  previewDescription: {
    paddingHorizontal: 12,
    paddingTop: 2,
    color: potatoColors.muted,
    fontSize: 10,
  },
  routeList: {
    gap: 6,
    paddingHorizontal: 10,
    paddingTop: 8,
  },
  routeButton: {
    minHeight: 30,
    justifyContent: 'center',
    paddingHorizontal: 10,
    borderWidth: 1,
    borderColor: potatoColors.border,
    borderRadius: 16,
    backgroundColor: potatoColors.white,
  },
  selectedRouteButton: {
    borderColor: potatoColors.orange,
    backgroundColor: potatoColors.accentLight,
  },
  routeLabel: {
    color: potatoColors.muted,
    fontSize: 11,
    fontWeight: '600',
  },
  selectedRouteLabel: {
    color: potatoColors.brown,
    fontWeight: '800',
  },
  screen: {
    flex: 1,
  },
});
