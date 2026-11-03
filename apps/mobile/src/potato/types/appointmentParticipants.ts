import type { AppointmentCreationTimeSlot } from './appointmentCreation';

export type InvitationDeliveryStatus = 'not_sent' | 'sent';

export type ParticipationStatus = 'pending' | 'accepted' | 'declined';

/** How the server says a participant entered the room (GET /v2/rooms/{id}/participants). */
export type ParticipantJoinPath = 'organizer' | 'invitation' | 'code';

export type AppointmentParticipant =
  | {
      id: string;
      role: 'organizer';
      invitationStatus: 'not_applicable';
      participationStatus: 'accepted';
      joinPath?: ParticipantJoinPath;
    }
  | {
      /** Host picked this person but no invitation has been sent yet. */
      id: string;
      role: 'invitee';
      invitationStatus: 'not_sent';
      participationStatus: 'pending';
      joinPath?: ParticipantJoinPath;
    }
  | {
      /** Joined with the room code: joining is acceptance, no invitation was sent. */
      id: string;
      role: 'invitee';
      invitationStatus: 'not_sent';
      participationStatus: 'accepted';
      joinPath?: ParticipantJoinPath;
    }
  | {
      id: string;
      role: 'invitee';
      invitationStatus: 'sent';
      participationStatus: ParticipationStatus;
      joinPath?: ParticipantJoinPath;
    };

export type ParticipantAvailabilitySubmission =
  | {
      participantId: string;
      status: 'not_submitted';
    }
  | {
      participantId: string;
      status: 'submitted';
      timeSlots: AppointmentCreationTimeSlot[];
      timeZone: string;
      submittedAt?: string;
      updatedAt?: string;
    };
