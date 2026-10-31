import type { PotatoAppointment } from './appointment';
import type {
  AppointmentParticipant,
  ParticipantAvailabilitySubmission,
} from './appointmentParticipants';

export type AppointmentCreationStep1Values = Pick<
  PotatoAppointment,
  'title' | 'category' | 'duration' | 'location'
>;

export interface AppointmentCreationTimeSlot {
  id: string;
  date: string;
  startTimeMinutes: number;
  endTimeMinutes: number;
}

export interface AppointmentCreationTimeInput {
  startHour: string;
  startMinute: string;
  endHour: string;
  endMinute: string;
}

export interface AppointmentCreationDraft
  extends Partial<AppointmentCreationStep1Values> {
  /** Legacy display-name selection. Use invitedFriendIds for identity. */
  invitedFriends?: string[];
  invitedFriendIds?: string[];
  invitedFriendNameById?: Record<string, string>;
  unresolvedInvitedFriendNames?: string[];
  participants?: AppointmentParticipant[];
  availabilitySubmissions?: ParticipantAvailabilitySubmission[];
  timeSlots?: AppointmentCreationTimeSlot[];
  selectedCalendarDate?: string;
  timeInput?: AppointmentCreationTimeInput;
  editingTimeSlotId?: string;
  selectedAiRecommendationTime?: string;
  organizerId?: string;
  timeZone?: string;
  appointmentId?: string;
  clientAppointmentId?: string;
  userRequest?: string;
}
