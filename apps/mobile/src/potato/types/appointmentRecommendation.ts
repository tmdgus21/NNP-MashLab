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

export type AppointmentRecommendationType =
  | 'ALL_AVAILABLE'
  | 'PARTIAL_ALTERNATIVE';

export interface AppointmentRecommendationCandidate {
  candidateId: string;
  date: string;
  startMinute: number;
  endMinute: number;
  timeZone: string;
  recommendationType: AppointmentRecommendationType;
  attendeeIds: string[];
  unavailableIds: string[];
  verified: boolean;
  sourceRevision: string;
  explanation: {
    agentSummary: string;
    optimizerSummary?: string;
  };
}

export type AppointmentRecommendationAgentStatus =
  | 'WAITING_FOR_INPUT'
  | 'ANALYZING'
  | 'RUNNING_TOOLS'
  | 'ALL_AVAILABLE'
  | 'PARTIAL_ALTERNATIVE'
  | 'NO_FEASIBLE_SCHEDULE'
  | 'AWAITING_APPROVAL'
  | 'STALE'
  | 'ERROR';

export interface AppointmentRecommendationHistoryEntry {
  requestId: string;
  requestText: string;
  status: 'not_sent' | 'sent' | 'completed' | 'failed';
  responseSummary?: string;
}

export interface AppointmentRecommendationAgentSnapshot {
  status: AppointmentRecommendationAgentStatus;
  agentRunId?: string;
  sourceRevision?: string;
  requiredAttendeeIds?: string[];
  allAvailableExhausted?: boolean;
  candidates?: AppointmentRecommendationCandidate[];
  history?: AppointmentRecommendationHistoryEntry[];
  error?: {
    code: string;
    userMessage: string;
    retryable: boolean;
  };
}

export interface AppointmentRecommendationRescheduleCommand {
  agentRunId: string;
  sourceRevision: string;
  requestText: string;
}

export interface AppointmentRecommendationCandidateCommand {
  agentRunId: string;
  sourceRevision: string;
  candidateId: string;
}

export type AppointmentRecommendationApprovalCommand =
  AppointmentRecommendationCandidateCommand;

export interface AppointmentRecommendationRetryCommand {
  agentRunId?: string;
  sourceRevision?: string;
}

export interface AppointmentRecommendationAgentApi {
  requestInitial(
    request: AppointmentAiRecommendationRequest,
  ): Promise<AppointmentRecommendationAgentSnapshot>;
  getStatus(
    agentRunId: string,
  ): Promise<AppointmentRecommendationAgentSnapshot>;
  reschedule(
    command: AppointmentRecommendationRescheduleCommand,
  ): Promise<AppointmentRecommendationAgentSnapshot>;
  selectCandidate(
    command: AppointmentRecommendationCandidateCommand,
  ): Promise<AppointmentRecommendationAgentSnapshot>;
  requestApproval(
    command: AppointmentRecommendationApprovalCommand,
  ): Promise<AppointmentRecommendationAgentSnapshot>;
  retry(
    command: AppointmentRecommendationRetryCommand,
  ): Promise<AppointmentRecommendationAgentSnapshot>;
  cancel(agentRunId: string): Promise<void>;
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
