import type { AppointmentCreationTimeSlot } from './appointmentCreation';

export type InvitationDeliveryStatus = 'not_sent' | 'sent';

export type ParticipationStatus = 'pending' | 'accepted' | 'declined';

export type AppointmentParticipant =
  | {
      id: string;
      role: 'organizer';
      invitationStatus: 'not_applicable';
      participationStatus: 'accepted';
    }
  | {
      id: string;
      role: 'invitee';
      invitationStatus: 'not_sent';
      participationStatus: 'pending';
    }
  | {
      id: string;
      role: 'invitee';
      invitationStatus: 'sent';
      participationStatus: ParticipationStatus;
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
