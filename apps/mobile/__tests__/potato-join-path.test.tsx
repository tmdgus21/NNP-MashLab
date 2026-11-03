import React from 'react';
import { Text } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import Renderer, { act } from 'react-test-renderer';
import { completeRecommendationPreviewDraft } from '../src/potato/dev/appointmentRecommendationFixtures';
import { CreateAppointmentStep4AdjustScreen } from '../src/potato/screens/CreateAppointmentStep4AdjustScreen';
import { prepareAppointmentAiRecommendation } from '../src/potato/services/appointmentRecommendation';
import type { AppointmentCreationDraft } from '../src/potato/types/appointmentCreation';
import { textContent } from '../test-utils/potato-test-utils';

// What the server reports for someone who joined with the room code:
// invitationStatus "not_sent" + participationStatus "accepted" + joinPath "code".
const codeJoinedDraft: AppointmentCreationDraft = {
  ...completeRecommendationPreviewDraft,
  participants: completeRecommendationPreviewDraft.participants!.map(participant =>
    participant.id === 'friend-preview-1'
      ? {
          id: participant.id,
          role: 'invitee' as const,
          invitationStatus: 'not_sent' as const,
          participationStatus: 'accepted' as const,
          joinPath: 'code' as const,
        }
      : participant,
  ),
};

test('a participant who joined by code with a submission is a valid, ready participant', () => {
  const preparation = prepareAppointmentAiRecommendation(codeJoinedDraft);
  expect(preparation.status).toBe('ready');
});

test('a host-selected friend who was never sent an invitation still cannot hold a submission', () => {
  const pendingNotSent: AppointmentCreationDraft = {
    ...codeJoinedDraft,
    participants: codeJoinedDraft.participants!.map(participant =>
      participant.id === 'friend-preview-1'
        ? {
            id: participant.id,
            role: 'invitee' as const,
            invitationStatus: 'not_sent' as const,
            participationStatus: 'pending' as const,
          }
        : participant,
    ),
  };
  const preparation = prepareAppointmentAiRecommendation(pendingNotSent);
  expect(preparation.status).toBe('needs_information');
  if (preparation.status === 'needs_information') {
    expect(preparation.invalidFields).toContain('participantAvailability');
  }
});

test('step four labels a code joiner by their real state, not as an unsent invitation', async () => {
  let tree!: Renderer.ReactTestRenderer;
  await act(async () => {
    tree = Renderer.create(
      <SafeAreaProvider>
        <CreateAppointmentStep4AdjustScreen
          nickname="방장"
          draft={codeJoinedDraft}
          onBack={jest.fn()}
          onNavigateStep={jest.fn()}
          onRequestAiRecommendation={jest.fn()}
        />
      </SafeAreaProvider>,
    );
  });
  const texts = tree.root
    .findAllByType(Text)
    .map(element => textContent(element.props.children));
  expect(texts).toContain('시간 제출 완료');
  expect(texts).not.toContain('초대 미발송');
});
