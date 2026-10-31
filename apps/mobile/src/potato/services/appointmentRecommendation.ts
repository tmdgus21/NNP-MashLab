import {
  isValidAppointmentTimeSlot,
  mergeAppointmentTimeSlots,
} from './appointmentTime';
import type { AppointmentCreationDraft } from '../types/appointmentCreation';
import type {
  AppointmentParticipant,
  ParticipantAvailabilitySubmission,
} from '../types/appointmentParticipants';
import type {
  AppointmentAiRecommendationPreparation,
  AppointmentAvailabilityInput,
  RecommendationInvalidField,
  RecommendationMissingField,
} from '../types/appointmentRecommendation';

export type AvailabilitySubmissionResult =
  | {
      valid: true;
      value: ParticipantAvailabilitySubmission;
    }
  | {
      valid: false;
      reason: 'participant_id' | 'time_zone' | 'time_slots' | 'timestamp';
    };

function isValidIsoTimestamp(value: string): boolean {
  return (
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(
      value,
    ) && !Number.isNaN(Date.parse(value))
  );
}

export function parseAppointmentDurationMinutes(
  duration: string,
): number | null {
  const trimmed = duration.trim();
  const hourMatch = /^(\d+(?:\.\d+)?)\s*시간$/.exec(trimmed);
  const minuteMatch = /^(\d+)\s*분$/.exec(trimmed);
  const value = hourMatch
    ? Number(hourMatch[1]) * 60
    : minuteMatch
      ? Number(minuteMatch[1])
      : Number.NaN;

  return Number.isSafeInteger(value) && value > 0 ? value : null;
}

export function createParticipantAvailabilitySubmission(
  input: AppointmentAvailabilityInput,
): AvailabilitySubmissionResult {
  const participantId = input.participantId.trim();
  if (!participantId) {
    return { valid: false, reason: 'participant_id' };
  }
  if (!input.timeZone.trim()) {
    return { valid: false, reason: 'time_zone' };
  }
  if (!input.timeSlots.every(isValidAppointmentTimeSlot)) {
    return { valid: false, reason: 'time_slots' };
  }
  if (
    (input.submittedAt !== undefined &&
      !isValidIsoTimestamp(input.submittedAt)) ||
    (input.updatedAt !== undefined &&
      !isValidIsoTimestamp(input.updatedAt))
  ) {
    return { valid: false, reason: 'timestamp' };
  }

  return {
    valid: true,
    value: {
      participantId,
      status: 'submitted',
      timeSlots: mergeAppointmentTimeSlots(input.timeSlots),
      timeZone: input.timeZone.trim(),
      ...(input.submittedAt ? { submittedAt: input.submittedAt } : {}),
      ...(input.updatedAt ? { updatedAt: input.updatedAt } : {}),
    },
  };
}

export function prepareAppointmentAiRecommendation(
  draft: AppointmentCreationDraft,
): AppointmentAiRecommendationPreparation {
  const missingFields = new Set<RecommendationMissingField>();
  const invalidFields = new Set<RecommendationInvalidField>();
  const title = draft.title?.trim();
  const category = draft.category?.trim();
  const duration = draft.duration?.trim();
  const location = draft.location?.trim();

  if (!title) {
    missingFields.add('title');
  }
  if (!category) {
    missingFields.add('category');
  }
  if (!duration) {
    missingFields.add('duration');
  }
  if (!location) {
    missingFields.add('location');
  }
  const durationMinutes = duration
    ? parseAppointmentDurationMinutes(duration)
    : null;
  if (duration && durationMinutes === null) {
    invalidFields.add('duration');
  }

  const savedOrganizerIds = (draft.participants ?? [])
    .filter(
      (participant): participant is Extract<
        AppointmentParticipant,
        { role: 'organizer' }
      > => participant.role === 'organizer',
    )
    .map(participant => participant.id.trim());
  if (new Set(savedOrganizerIds).size > 1 || savedOrganizerIds.includes('')) {
    invalidFields.add('participants');
  }
  const organizerId =
    draft.organizerId?.trim() ||
    (savedOrganizerIds.length === 1 ? savedOrganizerIds[0] : undefined);
  if (!organizerId) {
    missingFields.add('organizerId');
  }
  if (
    draft.organizerId !== undefined &&
    !draft.organizerId.trim()
  ) {
    invalidFields.add('organizerId');
  }
  const timeZone = draft.timeZone?.trim();
  if (!timeZone) {
    missingFields.add('timeZone');
  }
  if (draft.timeZone !== undefined && !timeZone) {
    invalidFields.add('timeZone');
  }

  const rawSlots = draft.timeSlots ?? [];
  if (rawSlots.length === 0) {
    missingFields.add('timeSlots');
  } else if (!rawSlots.every(isValidAppointmentTimeSlot)) {
    invalidFields.add('timeSlots');
  }

  const savedInviteeIds = (draft.participants ?? [])
    .filter(
      (participant): participant is Extract<
        AppointmentParticipant,
        { role: 'invitee' }
      > => participant.role === 'invitee',
    )
    .map(participant => participant.id);
  const friendIds =
    draft.invitedFriendIds !== undefined
      ? [...new Set(draft.invitedFriendIds)]
      : (draft.invitedFriends?.length ?? 0) === 0
        ? [...new Set(savedInviteeIds)]
        : [];
  if (
    draft.invitedFriendIds === undefined &&
    (draft.invitedFriends?.length ?? 0) > 0
  ) {
    missingFields.add('invitedFriendIds');
  }
  if (friendIds.some(id => !id.trim())) {
    invalidFields.add('invitedFriendIds');
  }
  if ((draft.unresolvedInvitedFriendNames?.length ?? 0) > 0) {
    missingFields.add('unresolvedFriendNames');
  }
  const mappedLegacyNames = friendIds.map(
    id => draft.invitedFriendNameById?.[id],
  );
  if ((draft.invitedFriends?.length ?? 0) > 0) {
    const allSelectedNamesKnown = mappedLegacyNames.every(
      (name): name is string => name !== undefined,
    );
    if (
      !allSelectedNamesKnown ||
      JSON.stringify(draft.invitedFriends) !==
        JSON.stringify([
          ...(draft.unresolvedInvitedFriendNames ?? []),
          ...mappedLegacyNames,
        ])
    ) {
      missingFields.add('unresolvedFriendNames');
    }
  }

  const participantById = new Map<string, AppointmentParticipant>();
  for (const participant of draft.participants ?? []) {
    if (
      !participant.id.trim() ||
      participantById.has(participant.id) ||
      (participant.role === 'organizer' &&
        participant.id !== organizerId) ||
      (participant.role === 'invitee' && !friendIds.includes(participant.id)) ||
      (participant.role === 'invitee' &&
        participant.id === organizerId)
    ) {
      invalidFields.add('participants');
    } else {
      participantById.set(participant.id, participant);
    }
  }

  const participants: AppointmentParticipant[] = [];
  if (organizerId) {
    participants.push({
      id: organizerId,
      role: 'organizer',
      invitationStatus: 'not_applicable',
      participationStatus: 'accepted',
    });
  }
  for (const id of friendIds) {
    const savedParticipant = participantById.get(id);
    const participant: AppointmentParticipant =
      savedParticipant?.role === 'invitee'
        ? savedParticipant
        : {
            id,
            role: 'invitee',
            invitationStatus: 'not_sent',
            participationStatus: 'pending',
          };
    participants.push(participant);
    if (participant.participationStatus === 'pending') {
      missingFields.add('participantResponses');
    }
  }

  const submissionsById = new Map<
    string,
    ParticipantAvailabilitySubmission
  >();
  for (const submission of draft.availabilitySubmissions ?? []) {
    if (
      submissionsById.has(submission.participantId) ||
      (submission.participantId !== organizerId &&
        !friendIds.includes(submission.participantId))
    ) {
      invalidFields.add('participantAvailability');
    } else {
      submissionsById.set(submission.participantId, submission);
    }
  }
  for (const participant of participants) {
    if (
      participant.role === 'invitee' &&
      participant.invitationStatus === 'not_sent' &&
      submissionsById.get(participant.id)?.status === 'submitted'
    ) {
      invalidFields.add('participantAvailability');
    }
  }

  const availabilitySubmissions: ParticipantAvailabilitySubmission[] = [];
  if (
    organizerId &&
    timeZone &&
    rawSlots.length > 0 &&
    rawSlots.every(isValidAppointmentTimeSlot)
  ) {
    availabilitySubmissions.push({
      participantId: organizerId,
      status: 'submitted',
      timeSlots: mergeAppointmentTimeSlots(rawSlots),
      timeZone,
    });
  }

  for (const participant of participants) {
    if (participant.role !== 'invitee') {
      continue;
    }
    const savedSubmission = submissionsById.get(participant.id);
    let submission: ParticipantAvailabilitySubmission =
      savedSubmission ?? {
        participantId: participant.id,
        status: 'not_submitted',
      };
    if (submission.status === 'submitted') {
      const validation = createParticipantAvailabilitySubmission({
        participantId: submission.participantId,
        timeSlots: submission.timeSlots,
        timeZone: submission.timeZone,
        submittedAt: submission.submittedAt,
        updatedAt: submission.updatedAt,
      });
      if (validation.valid) {
        submission = validation.value;
      } else {
        invalidFields.add('participantAvailability');
      }
    }

    if (participant.participationStatus === 'accepted') {
      if (submission.status === 'not_submitted') {
        missingFields.add('participantAvailability');
      } else {
        availabilitySubmissions.push(submission);
      }
    } else {
      availabilitySubmissions.push(submission);
    }
  }

  if (missingFields.size > 0 || invalidFields.size > 0) {
    return {
      status: 'needs_information',
      missingFields: [...missingFields],
      invalidFields: [...invalidFields],
      knownContext: {
        participants,
        availabilitySubmissions,
      },
    };
  }

  if (
    !title ||
    !category ||
    !duration ||
    !location ||
    durationMinutes === null ||
    !organizerId ||
    !timeZone
  ) {
    return {
      status: 'needs_information',
      missingFields: [],
      invalidFields: [],
      knownContext: {
        participants,
        availabilitySubmissions,
      },
    };
  }

  return {
    status: 'ready',
    request: {
      appointment: {
        title,
        category,
        duration,
        location,
      },
      durationMinutes,
      timeZone,
      participants,
      availabilitySubmissions,
      ...(draft.appointmentId?.trim()
        ? { appointmentId: draft.appointmentId.trim() }
        : {}),
      ...(draft.clientAppointmentId?.trim()
        ? { clientAppointmentId: draft.clientAppointmentId.trim() }
        : {}),
      ...(draft.userRequest?.trim()
        ? { userRequest: draft.userRequest.trim() }
        : {}),
    },
  };
}

export function getAppointmentRecommendationMessage(
  preparation: AppointmentAiRecommendationPreparation,
): string {
  if (preparation.status === 'ready') {
    return '';
  }

  const missing = new Set(preparation.missingFields);
  const invalid = new Set(preparation.invalidFields);
  const messages: string[] = [];
  const meetingFields = ['title', 'category', 'duration', 'location'] as const;

  if (meetingFields.some(field => missing.has(field))) {
    messages.push('모임 이름, 활동, 소요 시간, 장소를 확인해주세요.');
  }
  if (missing.has('timeSlots')) {
    messages.push('이전 단계에서 모임 가능한 시간을 추가해주세요.');
  }
  if (
    missing.has('organizerId') ||
    missing.has('timeZone') ||
    missing.has('invitedFriendIds') ||
    missing.has('unresolvedFriendNames')
  ) {
    messages.push('참여자 정보와 시간대 설정을 확인해주세요.');
  }
  if (missing.has('participantResponses')) {
    messages.push('초대된 참여자의 응답이 필요해요.');
  }
  if (missing.has('participantAvailability')) {
    messages.push('참여자의 가능한 시간 제출이 필요해요.');
  }
  if (invalid.has('duration')) {
    messages.push('소요 시간은 “1시간” 또는 “30분” 형식으로 입력해주세요.');
  }
  if (
    invalid.has('timeSlots') ||
    invalid.has('timeZone') ||
    invalid.has('participantAvailability')
  ) {
    messages.push('날짜와 가능한 시간 정보를 확인해주세요.');
  }
  if (invalid.has('organizerId') || invalid.has('participants')) {
    messages.push('참여자 정보를 확인해주세요.');
  }
  if (invalid.has('invitedFriendIds')) {
    messages.push('초대 친구 정보를 확인해주세요.');
  }

  return messages.length > 0
    ? messages.join('\n')
    : '일정을 추천하려면 모임 참여자와 가능한 시간 정보가 더 필요해요.';
}
