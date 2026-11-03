import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { INVITE_BASE_URL } from '../config/runtime.generated';
import { invitationCode } from '../domain/invitation';
import { PotatoAuthFlow } from './PotatoAuthFlow';
import { CreateAppointmentStep1Screen } from './screens/CreateAppointmentStep1Screen';
import { CreateAppointmentStep3TimeScreen } from './screens/CreateAppointmentStep3TimeScreen';
import { HomeScreen } from './screens/HomeScreen';
import { JoinRoomScreen } from './screens/JoinRoomScreen';
import { RoomScreen } from './screens/RoomScreen';
import { createPotatoRuntime, type PotatoRuntime } from './services/potatoRuntime';
import { newRequestKey, PotatoApiError, type RoomSummary } from './services/potatoApi';
import { parseAppointmentDurationMinutes } from './services/appointmentRecommendation';
import { formatSeoulRange, toSeoul } from './services/seoulTime';
import type { RoomState } from './services/roomState';
import type { PotatoSession } from './services/potatoSession';
import { potatoColors } from './theme/colors';
import type { PotatoAppointment, PotatoTabRoute } from './types/appointment';
import type { AppointmentCreationDraft } from './types/appointmentCreation';

type Route =
  | { name: 'boot' }
  | { name: 'auth' }
  | { name: 'home' }
  | { name: 'create1' }
  | { name: 'create3' }
  | { name: 'join' }
  | { name: 'room'; roomId: string }
  | { name: 'availability'; roomId: string; version: number }
  | { name: 'friends' }
  | { name: 'mypage' };

function toAppointment(room: RoomSummary): PotatoAppointment {
  const finalized = room.finalized && room.finalStartsAt && room.finalEndsAt;
  return {
    id: room.roomId,
    title: room.title,
    category: room.activity,
    duration: `${room.durationMinutes}분`,
    location: room.location,
    timeInfo: finalized ? formatSeoulRange(room.finalStartsAt!, room.finalEndsAt!) : '시간 조율 중',
    date: finalized ? toSeoul(room.finalStartsAt!).date : room.dates[0],
    invitedFriends: [],
    confirmed: !!finalized,
  };
}

interface PotatoAppProps {
  runtime?: PotatoRuntime;
  /** Tests pass false so no OS link listener is registered. */
  listenForLinks?: boolean;
}

/**
 * Release root. Every screen talks to the real server through PotatoApi; there is
 * no preview data, no local-only delete and no fake success path.
 */
export function PotatoApp({ runtime: injected, listenForLinks = true }: PotatoAppProps) {
  const runtime = useRef(injected ?? createPotatoRuntime()).current;
  const { api, sessions } = runtime;
  const [route, setRoute] = useState<Route>({ name: 'boot' });
  const [session, setSession] = useState<PotatoSession | null>(null);
  const [rooms, setRooms] = useState<RoomSummary[]>([]);
  const [homeVersion, setHomeVersion] = useState(0);
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<AppointmentCreationDraft>({});
  const creationKey = useRef<string | null>(null);
  const pendingCode = useRef('');
  const [joinCode, setJoinCode] = useState('');

  const signOut = useCallback(async () => {
    try {
      await api.auth.logout();
    } catch {
      // the local session is removed either way
    }
    await sessions.clear();
    runtime.setToken(null);
    setSession(null);
    setRooms([]);
    setRoute({ name: 'auth' });
  }, [api, sessions, runtime]);

  const adopt = useCallback(async () => {
    const stored = await sessions.load();
    runtime.setToken(stored?.token ?? null);
    setSession(stored);
    if (!stored) {
      setRoute({ name: 'auth' });
    } else if (pendingCode.current) {
      setJoinCode(pendingCode.current);
      pendingCode.current = '';
      setRoute({ name: 'join' });
    } else {
      setRoute({ name: 'home' });
    }
  }, [sessions, runtime]);

  useEffect(() => {
    void adopt();
  }, [adopt]);

  useEffect(() => {
    if (!listenForLinks) {
      return undefined;
    }
    const accept = (url: string | null | undefined) => {
      const code = url ? invitationCode(url, INVITE_BASE_URL) : null;
      if (!code) {
        return;
      }
      pendingCode.current = code;
      if (runtime.hasToken()) {
        setJoinCode(code);
        pendingCode.current = '';
        setRoute({ name: 'join' });
      }
    };
    void Linking.getInitialURL().then(accept);
    const subscription = Linking.addEventListener('url', ({ url }) => accept(url));
    return () => subscription.remove();
  }, [listenForLinks, runtime]);

  const route_ = route.name;
  useEffect(() => {
    if (route_ !== 'home') {
      return;
    }
    let live = true;
    api.rooms
      .list()
      .then(result => {
        if (live) {
          setRooms(result.rooms);
          setHomeVersion(version => version + 1);
          setNotice('');
        }
      })
      .catch(failure => {
        if (!live) {
          return;
        }
        if (failure instanceof PotatoApiError && failure.status === 401) {
          void signOut();
        } else {
          setNotice(failure instanceof PotatoApiError ? failure.message : '모임을 불러오지 못했어요.');
        }
      });
    return () => {
      live = false;
    };
  }, [route_, api, signOut]);

  const startCreation = () => {
    creationKey.current = newRequestKey('create');
    setDraft({});
    setNotice('');
    setRoute({ name: 'create1' });
  };

  const goTab = (tab: PotatoTabRoute) => {
    if (tab === 'create_step1') {
      startCreation();
    } else {
      setRoute(
        tab === 'home'
          ? { name: 'home' }
          : tab === 'friends'
            ? { name: 'friends' }
            : { name: 'mypage' },
      );
    }
  };

  const createRoom = async (finalDraft: AppointmentCreationDraft) => {
    const minutes = parseAppointmentDurationMinutes(finalDraft.duration ?? '');
    const slots = finalDraft.timeSlots ?? [];
    if (!finalDraft.title || !finalDraft.category || !finalDraft.location || minutes === null) {
      setNotice('모임 이름, 활동, 장소, 소요 시간(예: 1시간, 30분)을 확인해 주세요.');
      setRoute({ name: 'create1' });
      return;
    }
    if (slots.length === 0) {
      setNotice('가능한 시간을 하나 이상 추가해 주세요.');
      return;
    }
    setBusy(true);
    setNotice('');
    let roomId = '';
    try {
      const dates = [...new Set(slots.map(slot => slot.date))].sort();
      const created = await api.rooms.create(
        {
          title: finalDraft.title,
          activity: finalDraft.category,
          location: finalDraft.location,
          durationMinutes: minutes,
          dates,
          minimumAttendeeCount: 2,
          nickname: session?.nickname ?? '방장',
        },
        creationKey.current ?? newRequestKey('create'),
      );
      roomId = created.roomId;
      await api.availability.put(
        roomId,
        slots.map(slot => ({ date: slot.date, startTimeMinutes: slot.startTimeMinutes, endTimeMinutes: slot.endTimeMinutes })),
      );
      setRoute({ name: 'room', roomId });
    } catch (failure) {
      const message = failure instanceof PotatoApiError ? failure.message : '모임을 만들지 못했어요.';
      if (roomId) {
        // The room exists; only the host's times failed. Open it so they can retry there.
        setNotice(`모임은 만들어졌지만 내 시간을 저장하지 못했어요. ${message}`);
        setRoute({ name: 'room', roomId });
      } else {
        setNotice(message);
      }
    } finally {
      setBusy(false);
    }
  };

  const saveAvailability = async (roomId: string, version: number, finalDraft: AppointmentCreationDraft) => {
    const slots = finalDraft.timeSlots ?? [];
    if (slots.length === 0) {
      setNotice('가능한 시간을 하나 이상 추가해 주세요. 시간이 없다면 제출하지 말고 방장에게 알려 주세요.');
      return;
    }
    setBusy(true);
    setNotice('');
    try {
      await api.availability.put(
        roomId,
        slots.map(slot => ({ date: slot.date, startTimeMinutes: slot.startTimeMinutes, endTimeMinutes: slot.endTimeMinutes })),
        version,
      );
      setRoute({ name: 'room', roomId });
    } catch (failure) {
      setNotice(failure instanceof PotatoApiError ? failure.message : '시간을 저장하지 못했어요.');
    } finally {
      setBusy(false);
    }
  };

  const openAvailabilityEditor = (state: RoomState) => {
    setDraft({
      timeSlots: state.myAvailability.timeSlots.map((slot, index) => ({
        id: `mine-${index}`,
        date: slot.date,
        startTimeMinutes: slot.startTimeMinutes,
        endTimeMinutes: slot.endTimeMinutes,
      })),
    });
    setNotice('');
    setRoute({ name: 'availability', roomId: state.room.roomId, version: state.myAvailability.version });
  };

  const banner = !!notice && (
    <Text accessibilityLiveRegion="assertive" style={styles.notice}>{notice}</Text>
  );
  const overlay = busy && (
    <View style={styles.overlay} pointerEvents="auto">
      <Text style={styles.overlayText}>저장 중…</Text>
    </View>
  );

  let screen: React.ReactNode = <View style={styles.flex} />;
  switch (route.name) {
    case 'auth':
      screen = <PotatoAuthFlow service={runtime.auth} onLoginSuccess={() => void adopt()} />;
      break;
    case 'home':
      screen = (
        <View style={styles.flex}>
          <HomeScreen
            key={homeVersion}
            nickname={session?.nickname ?? ''}
            initialAppointments={rooms.map(toAppointment)}
            allowDelete={false}
            initiallyShowAll
            editLabel="모임 열기"
            onLogoutPress={() => void signOut()}
            onCreateAppointmentPress={startCreation}
            onEditAppointmentPress={appointment => setRoute({ name: 'room', roomId: String(appointment.id) })}
            onTabSelected={goTab}
          />
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="초대 코드로 참가"
            onPress={() => {
              setJoinCode('');
              setNotice('');
              setRoute({ name: 'join' });
            }}
            style={styles.joinFab}
          >
            <Text style={styles.joinFabText}>초대 코드로 참가</Text>
          </Pressable>
          {banner}
        </View>
      );
      break;
    case 'create1':
      screen = (
        <View style={styles.flex}>
          <CreateAppointmentStep1Screen
            draft={draft}
            onDraftChange={setDraft}
            onCancelClick={() => setRoute({ name: 'home' })}
            onBackClick={() => setRoute({ name: 'home' })}
            onRequestStep2={values => {
              setDraft(current => ({ ...current, ...values }));
              setRoute({ name: 'create3' });
            }}
          />
          {banner}
        </View>
      );
      break;
    case 'create3':
      screen = (
        <View style={styles.flex}>
          <CreateAppointmentStep3TimeScreen
            draft={draft}
            onDraftChange={setDraft}
            onBack={() => setRoute({ name: 'create1' })}
            onRequestStep4={finalDraft => void createRoom(finalDraft)}
          />
          {banner}
        </View>
      );
      break;
    case 'availability': {
      const { roomId, version } = route;
      screen = (
        <View style={styles.flex}>
          <CreateAppointmentStep3TimeScreen
            draft={draft}
            onDraftChange={setDraft}
            onBack={() => setRoute({ name: 'room', roomId })}
            onRequestStep4={finalDraft => void saveAvailability(roomId, version, finalDraft)}
          />
          {banner}
        </View>
      );
      break;
    }
    case 'join':
      screen = (
        <JoinRoomScreen
          api={api}
          defaultNickname={session?.nickname ?? ''}
          initialCode={joinCode}
          onBack={() => setRoute({ name: 'home' })}
          onJoined={room => {
            setDraft({});
            setRoute({ name: 'availability', roomId: room.roomId, version: 0 });
          }}
        />
      );
      break;
    case 'room':
      screen = (
        <View style={styles.flex}>
          <RoomScreen
            api={api}
            roomId={route.roomId}
            onBack={() => setRoute({ name: 'home' })}
            onEditAvailability={openAvailabilityEditor}
            onLeft={() => setRoute({ name: 'home' })}
          />
          {banner}
        </View>
      );
      break;
    case 'friends':
      screen = (
        <SimplePage title="친구" onTab={goTab} active="friends">
          <Text style={styles.pageText}>
            친구 기능은 아직 준비 중이에요. 지금은 모임을 만든 뒤 초대 코드를 공유해 주세요.
          </Text>
        </SimplePage>
      );
      break;
    case 'mypage':
      screen = (
        <SimplePage title="MY" onTab={goTab} active="mypage">
          <Text style={styles.pageName}>{session?.nickname}</Text>
          <Text style={styles.pageText}>{session?.email}</Text>
          <Pressable accessibilityRole="button" onPress={() => void signOut()} style={styles.logout}>
            <Text style={styles.logoutText}>로그아웃</Text>
          </Pressable>
        </SimplePage>
      );
      break;
    default:
      break;
  }

  return (
    <View style={styles.flex}>
      {screen}
      {overlay}
    </View>
  );
}

function SimplePage({
  title,
  active,
  onTab,
  children,
}: {
  title: string;
  active: PotatoTabRoute;
  onTab: (tab: PotatoTabRoute) => void;
  children: React.ReactNode;
}) {
  const tabs: Array<[PotatoTabRoute, string]> = [['home', '홈'], ['create_step1', '모임만들기'], ['friends', '친구'], ['mypage', 'MY']];
  return (
    <SafeAreaView style={styles.page}>
      <View style={styles.pageBody}>
        <Text style={styles.pageTitle}>{title}</Text>
        {children}
      </View>
      <View style={styles.tabs}>
        {tabs.map(([tab, label]) => (
          <Pressable key={tab} accessibilityRole="button" onPress={() => onTab(tab)} style={styles.tab}>
            <Text style={[styles.tabText, tab === active && styles.tabActive]}>{label}</Text>
          </Pressable>
        ))}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: potatoColors.background },
  page: { flex: 1, backgroundColor: potatoColors.background },
  pageBody: { flex: 1, padding: 24, gap: 12 },
  pageTitle: { fontSize: 22, fontWeight: '700', color: potatoColors.text },
  pageName: { fontSize: 20, fontWeight: '700', color: potatoColors.text },
  pageText: { fontSize: 15, color: potatoColors.muted },
  logout: { height: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: potatoColors.border, marginTop: 12 },
  logoutText: { fontSize: 15, fontWeight: '700', color: potatoColors.text },
  tabs: { flexDirection: 'row', borderTopWidth: 1, borderTopColor: potatoColors.border, backgroundColor: potatoColors.white },
  tab: { flex: 1, alignItems: 'center', paddingVertical: 14 },
  tabText: { fontSize: 13, color: potatoColors.muted },
  tabActive: { color: potatoColors.brown, fontWeight: '700' },
  notice: { position: 'absolute', left: 16, right: 16, top: 8, backgroundColor: potatoColors.errorBackground, color: potatoColors.errorText, padding: 12, borderRadius: 12, fontSize: 14 },
  overlay: { ...StyleSheet.absoluteFill, backgroundColor: 'rgba(255,252,243,0.8)', alignItems: 'center', justifyContent: 'center' },
  overlayText: { fontSize: 16, fontWeight: '700', color: potatoColors.brown },
  joinFab: { position: 'absolute', right: 16, bottom: 96, backgroundColor: potatoColors.brown, paddingHorizontal: 16, paddingVertical: 12, borderRadius: 24 },
  joinFabText: { color: potatoColors.white, fontSize: 14, fontWeight: '700' },
});
