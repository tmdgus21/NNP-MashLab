import React, { useState } from 'react';
import { Alert, Text, View } from 'react-native';
import { useApp } from '../state/store';
import { Button } from './components';
import { InvitationSheet } from './InvitationSheet';
import { ui } from './theme';

export function MeetingActions() {
  const app = useApp();
  const [inviting, setInviting] = useState(false);
  const m = app.meeting!;
  return (
    <View style={ui.card}>
      <Text style={ui.eyebrow}>모임 초대 코드</Text>
      <Text
        selectable
        accessibilityLabel={`초대 코드 ${m.roomCode}`}
        style={ui.title}
      >
        {m.roomCode}
      </Text>
      <Text style={ui.small}>참여자에게 이 8자리 코드를 알려주세요.</Text>
      <Button
        title="코드 복사 · QR 초대"
        secondary
        onPress={() => setInviting(true)}
      />
      <Button
        title="새 모임 만들기 / 내 모임 목록"
        secondary
        disabled={!!app.busy}
        onPress={app.leave}
      />
      {m.hostId === app.actorId && (
        <Button
          title="모임 삭제"
          secondary
          disabled={!!app.busy}
          onPress={() =>
            Alert.alert(
              '모임을 삭제할까요?',
              `‘${m.title}’의 모든 참여자가 더 이상 모임에 접근할 수 없고 초대 코드도 사용할 수 없어요. 삭제 후 앱에서 되돌릴 수 없어요.`,
              [
                { text: '취소', style: 'cancel' },
                {
                  text: '모임 삭제',
                  style: 'destructive',
                  onPress: () => {
                    void app.deleteMeeting();
                  },
                },
              ],
            )
          }
        />
      )}
      {inviting && (
        <InvitationSheet meeting={m} onClose={() => setInviting(false)} />
      )}
    </View>
  );
}
