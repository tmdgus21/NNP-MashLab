import {
  getSelectedFriendIds,
  resolveLegacyFriendSelection,
  updateInvitedFriendSelection,
} from '../src/potato/services/appointmentParticipants';
import {
  createParticipantAvailabilitySubmission,
  parseAppointmentDurationMinutes,
  prepareAppointmentAiRecommendation,
} from '../src/potato/services/appointmentRecommendation';
import type { AppointmentCreationDraft } from '../src/potato/types/appointmentCreation';
import type { PotatoFriend } from '../src/potato/types/friend';
import type { AppointmentRecommendationResponse } from '../src/potato/types/appointmentRecommendation';

const friends: PotatoFriend[] = [
  { id: 'friend-1', name: '민수' },
  { id: 'friend-2', name: '민수' },
  { id: 'friend-3', name: '지훈' },
];

const baseDraft: AppointmentCreationDraft = {
  title: '저녁 약속',
  category: '식사',
  duration: '90분',
  location: '서울',
  organizerId: 'organizer-1',
  timeZone: 'Asia/Seoul',
  timeSlots: [
    {
      id: 'host-slot',
      date: '2027-02-28',
      startTimeMinutes: 9 * 60,
      endTimeMinutes: 10 * 60,
    },
  ],
};

test('legacy names resolve only when exactly one friend matches', () => {
  expect(resolveLegacyFriendSelection(['민수', '알 수 없음'], friends)).toEqual({
    friendIds: [],
    unresolvedNames: ['알 수 없음'],
    ambiguousNames: ['민수'],
  });
  expect(resolveLegacyFriendSelection(['지훈'], friends)).toEqual({
    friendIds: ['friend-3'],
    unresolvedNames: [],
    ambiguousNames: [],
  });
});

test('canonical IDs remain authoritative for same-named friends', () => {
  expect(
    getSelectedFriendIds(
      { invitedFriends: ['민수'], invitedFriendIds: ['friend-2'] },
      friends,
    ),
  ).toEqual(['friend-2']);

  const updated = updateInvitedFriendSelection(
    { ...baseDraft, invitedFriends: ['민수'] },
    ['friend-1'],
    friends,
  );
  expect(updated.invitedFriendIds).toEqual(['friend-1']);
  expect(updated.invitedFriendNameById).toEqual({ 'friend-1': '민수' });
  expect(updated.unresolvedInvitedFriendNames).toEqual(['민수']);
  expect(updated.title).toBe(baseDraft.title);
  expect(updated.timeSlots).toEqual(baseDraft.timeSlots);
});

test('friend selection sync keeps delivery, response, and availability separate', () => {
  const updated = updateInvitedFriendSelection(
    baseDraft,
    ['friend-1', 'friend-3'],
    friends,
  );
  expect(updated.participants).toEqual([
    {
      id: 'organizer-1',
      role: 'organizer',
      invitationStatus: 'not_applicable',
      participationStatus: 'accepted',
    },
    {
      id: 'friend-1',
      role: 'invitee',
      invitationStatus: 'not_sent',
      participationStatus: 'pending',
    },
    {
      id: 'friend-3',
      role: 'invitee',
      invitationStatus: 'not_sent',
      participationStatus: 'pending',
    },
  ]);
  expect(updated.availabilitySubmissions).toEqual([
    { participantId: 'friend-1', status: 'not_submitted' },
    { participantId: 'friend-3', status: 'not_submitted' },
  ]);
});

test('duration conversion accepts whole-minute values and rejects invalid input', () => {
  expect(parseAppointmentDurationMinutes(' 2시간 ')).toBe(120);
  expect(parseAppointmentDurationMinutes('1.5시간')).toBe(90);
  expect(parseAppointmentDurationMinutes('90분')).toBe(90);
  expect(parseAppointmentDurationMinutes('0분')).toBeNull();
  expect(parseAppointmentDurationMinutes('약 1시간')).toBeNull();
  expect(parseAppointmentDurationMinutes('0.01시간')).toBeNull();
});

test('availability submission validates dates and merges per participant only', () => {
  const firstParticipant = createParticipantAvailabilitySubmission({
    participantId: 'friend-1',
    timeZone: 'Asia/Seoul',
    timeSlots: [
      {
        id: 'a',
        date: '2027-02-28',
        startTimeMinutes: 9 * 60,
        endTimeMinutes: 10 * 60,
      },
      {
        id: 'b',
        date: '2027-02-28',
        startTimeMinutes: 10 * 60,
        endTimeMinutes: 11 * 60,
      },
      {
        id: 'c',
        date: '2027-03-01',
        startTimeMinutes: 12 * 60,
        endTimeMinutes: 13 * 60,
      },
    ],
  });
  const secondParticipant = createParticipantAvailabilitySubmission({
    participantId: 'friend-2',
    timeZone: 'Asia/Seoul',
    timeSlots: [
      {
        id: 'd',
        date: '2027-02-28',
        startTimeMinutes: 14 * 60,
        endTimeMinutes: 15 * 60,
      },
    ],
  });

  expect(firstParticipant.valid).toBe(true);
  expect(secondParticipant.valid).toBe(true);
  if (firstParticipant.valid && secondParticipant.valid) {
    if (
      firstParticipant.value.status !== 'submitted' ||
      secondParticipant.value.status !== 'submitted'
    ) {
      throw new Error('Expected availability values to be submitted.');
    }
    expect(firstParticipant.value.timeSlots).toEqual([
      {
        id: 'a',
        date: '2027-02-28',
        startTimeMinutes: 9 * 60,
        endTimeMinutes: 11 * 60,
      },
      {
        id: 'c',
        date: '2027-03-01',
        startTimeMinutes: 12 * 60,
        endTimeMinutes: 13 * 60,
      },
    ]);
    expect(secondParticipant.value.timeSlots).toHaveLength(1);
    expect(firstParticipant.value.participantId).not.toBe(
      secondParticipant.value.participantId,
    );
  }

  expect(
    createParticipantAvailabilitySubmission({
      participantId: 'friend-1',
      timeZone: 'Asia/Seoul',
      timeSlots: [
        {
          id: 'invalid',
          date: '2027-02-29',
          startTimeMinutes: 10,
          endTimeMinutes: 20,
        },
      ],
    }),
  ).toEqual({ valid: false, reason: 'time_slots' });
});

test('recommendation readiness requires accepted participants to submit availability', () => {
  const pending = prepareAppointmentAiRecommendation({
    ...baseDraft,
    invitedFriendIds: ['friend-1'],
  });
  expect(pending.status).toBe('needs_information');
  if (pending.status === 'needs_information') {
    expect(pending.missingFields).toContain('participantResponses');
    expect(pending.knownContext.participants).toContainEqual({
      id: 'friend-1',
      role: 'invitee',
      invitationStatus: 'not_sent',
      participationStatus: 'pending',
    });
    expect(pending.knownContext.availabilitySubmissions).toContainEqual({
      participantId: 'friend-1',
      status: 'not_submitted',
    });
  }

  const acceptedButUnsubmitted = prepareAppointmentAiRecommendation({
    ...baseDraft,
    invitedFriendIds: ['friend-1'],
    participants: [
      {
        id: 'friend-1',
        role: 'invitee',
        invitationStatus: 'sent',
        participationStatus: 'accepted',
      },
    ],
  });
  expect(acceptedButUnsubmitted.status).toBe('needs_information');
  if (acceptedButUnsubmitted.status === 'needs_information') {
    expect(acceptedButUnsubmitted.missingFields).toContain(
      'participantAvailability',
    );
  }
});

test('sent, accepted, and declined invitations retain distinct participation states', () => {
  const sentPending = prepareAppointmentAiRecommendation({
    ...baseDraft,
    invitedFriendIds: ['friend-1'],
    participants: [
      {
        id: 'friend-1',
        role: 'invitee',
        invitationStatus: 'sent',
        participationStatus: 'pending',
      },
    ],
  });
  expect(sentPending.status).toBe('needs_information');
  if (sentPending.status === 'needs_information') {
    expect(sentPending.missingFields).toContain('participantResponses');
    expect(sentPending.knownContext.participants).toContainEqual({
      id: 'friend-1',
      role: 'invitee',
      invitationStatus: 'sent',
      participationStatus: 'pending',
    });
  }

  const declined = prepareAppointmentAiRecommendation({
    ...baseDraft,
    invitedFriendIds: ['friend-1'],
    participants: [
      {
        id: 'friend-1',
        role: 'invitee',
        invitationStatus: 'sent',
        participationStatus: 'declined',
      },
    ],
  });
  expect(declined.status).toBe('ready');
  if (declined.status === 'ready') {
    expect(declined.request.participants).toContainEqual({
      id: 'friend-1',
      role: 'invitee',
      invitationStatus: 'sent',
      participationStatus: 'declined',
    });
    expect(declined.request.availabilitySubmissions).toContainEqual({
      participantId: 'friend-1',
      status: 'not_submitted',
    });
  }
});

test('recommendation contract preserves participants, slots, and STEP 1 data', () => {
  const availability = createParticipantAvailabilitySubmission({
    participantId: 'friend-1',
    timeZone: 'Asia/Seoul',
    submittedAt: '2027-02-01T10:00:00.000Z',
    timeSlots: [
      {
        id: 'friend-slot',
        date: '2027-02-28',
        startTimeMinutes: 13 * 60,
        endTimeMinutes: 14 * 60,
      },
    ],
  });
  expect(availability.valid).toBe(true);
  if (!availability.valid) {
    return;
  }
  if (availability.value.status !== 'submitted') {
    throw new Error('Expected availability value to be submitted.');
  }

  const draft: AppointmentCreationDraft = {
    ...baseDraft,
    clientAppointmentId: 'draft-1',
    userRequest: '저녁 시간대 우선',
    invitedFriendIds: ['friend-1'],
    invitedFriendNameById: { 'friend-1': '민수' },
    participants: [
      {
        id: 'friend-1',
        role: 'invitee',
        invitationStatus: 'sent',
        participationStatus: 'accepted',
      },
    ],
    availabilitySubmissions: [availability.value],
  };
  const preparation = prepareAppointmentAiRecommendation(draft);

  expect(preparation).toEqual({
    status: 'ready',
    request: {
      appointment: {
        title: '저녁 약속',
        category: '식사',
        duration: '90분',
        location: '서울',
      },
      durationMinutes: 90,
      timeZone: 'Asia/Seoul',
      participants: [
        {
          id: 'organizer-1',
          role: 'organizer',
          invitationStatus: 'not_applicable',
          participationStatus: 'accepted',
        },
        {
          id: 'friend-1',
          role: 'invitee',
          invitationStatus: 'sent',
          participationStatus: 'accepted',
        },
      ],
      availabilitySubmissions: [
        {
          participantId: 'organizer-1',
          status: 'submitted',
          timeSlots: baseDraft.timeSlots,
          timeZone: 'Asia/Seoul',
        },
        availability.value,
      ],
      clientAppointmentId: 'draft-1',
      userRequest: '저녁 시간대 우선',
    },
  });
});

test('legacy names and incomplete context produce explicit missing information', () => {
  const result = prepareAppointmentAiRecommendation({
    ...baseDraft,
    organizerId: undefined,
    timeZone: undefined,
    invitedFriends: ['민수'],
  });
  expect(result.status).toBe('needs_information');
  if (result.status === 'needs_information') {
    expect(result.missingFields).toEqual(
      expect.arrayContaining([
        'organizerId',
        'timeZone',
        'invitedFriendIds',
      ]),
    );
  }

  expect(
    prepareAppointmentAiRecommendation({
      ...baseDraft,
      duration: '한 시간 정도',
    }),
  ).toMatchObject({
    status: 'needs_information',
    invalidFields: ['duration'],
  });
});

test('recommendation candidates remain pending user approval', () => {
  const response: AppointmentRecommendationResponse<{ id: string }> = {
    status: 'awaiting_user_approval',
    candidates: [{ id: 'candidate-1' }],
  };
  expect(response.status).toBe('awaiting_user_approval');
});
