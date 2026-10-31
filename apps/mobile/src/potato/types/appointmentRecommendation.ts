import type {
  AppointmentCreationStep1Values,
  AppointmentCreationTimeSlot,
} from './appointmentCreation';
import type {
  AppointmentParticipant,
  ParticipantAvailabilitySubmission,
} from './appointmentParticipants';

export interface AppointmentAiRecommendationRequest {
  appointment: AppointmentCreationStep1Values;
  durationMinutes: number;
  timeZone: string;
  participants: AppointmentParticipant[];
  availabilitySubmissions: ParticipantAvailabilitySubmission[];
  appointmentId?: string;
  clientAppointmentId?: string;
  userRequest?: string;
}

export interface AppointmentRecommendationResponse<TCandidate> {
  status: 'awaiting_user_approval';
  candidates: TCandidate[];
}

export type RecommendationMissingField =
  | 'title'
  | 'category'
  | 'duration'
  | 'location'
  | 'organizerId'
  | 'timeZone'
  | 'timeSlots'
  | 'invitedFriendIds'
  | 'unresolvedFriendNames'
  | 'participantResponses'
  | 'participantAvailability';

export type RecommendationInvalidField =
  | 'duration'
  | 'organizerId'
  | 'timeZone'
  | 'timeSlots'
  | 'invitedFriendIds'
  | 'participants'
  | 'participantAvailability';

export type AppointmentAiRecommendationPreparation =
  | {
      status: 'ready';
      request: AppointmentAiRecommendationRequest;
    }
  | {
      status: 'needs_information';
      missingFields: RecommendationMissingField[];
      invalidFields: RecommendationInvalidField[];
      knownContext: {
        participants: AppointmentParticipant[];
        availabilitySubmissions: ParticipantAvailabilitySubmission[];
      };
    };

export type AppointmentAvailabilityInput = {
  participantId: string;
  timeSlots: readonly AppointmentCreationTimeSlot[];
  timeZone: string;
  submittedAt?: string;
  updatedAt?: string;
};
