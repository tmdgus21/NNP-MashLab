import type { AppointmentCreationDraft } from '../types/appointmentCreation';
import type {
  AppointmentParticipant,
  ParticipantAvailabilitySubmission,
} from '../types/appointmentParticipants';
import type { PotatoFriend } from '../types/friend';

export interface LegacyFriendSelectionResolution {
  friendIds: string[];
  unresolvedNames: string[];
  ambiguousNames: string[];
}

export function resolveLegacyFriendSelection(
  names: readonly string[],
  friends: readonly PotatoFriend[],
): LegacyFriendSelectionResolution {
  const friendIds = new Set<string>();
  const unresolvedNames: string[] = [];
  const ambiguousNames: string[] = [];

  for (const name of names) {
    const matches = friends.filter(friend => friend.name === name);
    if (matches.length === 1) {
      friendIds.add(matches[0].id);
    } else if (matches.length > 1) {
      ambiguousNames.push(name);
    } else {
      unresolvedNames.push(name);
    }
  }

  return {
    friendIds: [...friendIds],
    unresolvedNames,
    ambiguousNames,
  };
}

export function getSelectedFriendIds(
  draft: AppointmentCreationDraft,
  friends: readonly PotatoFriend[],
): string[] {
  if (draft.invitedFriendIds !== undefined) {
    return [...new Set(draft.invitedFriendIds)];
  }
  const resolvedLegacyIds = resolveLegacyFriendSelection(
    draft.invitedFriends ?? [],
    friends,
  ).friendIds;
  const participantIds = (draft.participants ?? [])
    .filter(
      (participant): participant is Extract<
        AppointmentParticipant,
        { role: 'invitee' }
      > => participant.role === 'invitee',
    )
    .map(participant => participant.id);
  return [...new Set([...resolvedLegacyIds, ...participantIds])];
}

export function updateInvitedFriendSelection(
  draft: AppointmentCreationDraft,
  selectedFriendIds: readonly string[],
  friends: readonly PotatoFriend[],
): AppointmentCreationDraft {
  const friendIds = [...new Set(selectedFriendIds)];
  const selectedSet = new Set(friendIds);
  const legacyResolution =
    draft.invitedFriendIds === undefined
      ? resolveLegacyFriendSelection(draft.invitedFriends ?? [], friends)
      : {
          unresolvedNames: draft.unresolvedInvitedFriendNames ?? [],
          ambiguousNames: [],
        };
  const unresolvedNames = [
    ...legacyResolution.unresolvedNames,
    ...legacyResolution.ambiguousNames,
  ];
  const legacyNames = [...unresolvedNames];
  const nameById = Object.fromEntries(
    Object.entries(draft.invitedFriendNameById ?? {}).filter(([id]) =>
      selectedSet.has(id),
    ),
  );

  for (const friend of friends) {
    if (selectedSet.has(friend.id)) {
      nameById[friend.id] = friend.name;
    }
  }
  for (const id of friendIds) {
    const name = nameById[id];
    if (name !== undefined) {
      legacyNames.push(name);
    }
  }

  const participants: AppointmentParticipant[] = [
    ...(draft.participants ?? []).filter(
      participant =>
        participant.role === 'organizer' ||
        selectedSet.has(participant.id),
    ),
  ];
  const participantIds = new Set(participants.map(participant => participant.id));
  const existingOrganizerIds = new Set(
    participants
      .filter(
        (participant): participant is Extract<
          AppointmentParticipant,
          { role: 'organizer' }
        > => participant.role === 'organizer',
      )
      .map(participant => participant.id),
  );
  if (draft.organizerId && !participantIds.has(draft.organizerId)) {
    participants.push({
      id: draft.organizerId,
      role: 'organizer',
      invitationStatus: 'not_applicable',
      participationStatus: 'accepted',
    });
    participantIds.add(draft.organizerId);
    existingOrganizerIds.add(draft.organizerId);
  }
  for (const id of friendIds) {
    if (!participantIds.has(id)) {
      participants.push({
        id,
        role: 'invitee',
        invitationStatus: 'not_sent',
        participationStatus: 'pending',
      });
    }
  }

  const availabilitySubmissions: ParticipantAvailabilitySubmission[] = [
    ...(draft.availabilitySubmissions ?? []).filter(
      submission =>
        existingOrganizerIds.has(submission.participantId) ||
        selectedSet.has(submission.participantId),
    ),
  ];
  const submissionIds = new Set(
    availabilitySubmissions.map(submission => submission.participantId),
  );
  for (const id of friendIds) {
    if (!submissionIds.has(id)) {
      availabilitySubmissions.push({
        participantId: id,
        status: 'not_submitted',
      });
    }
  }

  return {
    ...draft,
    invitedFriendIds: friendIds,
    invitedFriendNameById: nameById,
    unresolvedInvitedFriendNames: unresolvedNames,
    invitedFriends: legacyNames,
    participants,
    availabilitySubmissions,
  };
}
