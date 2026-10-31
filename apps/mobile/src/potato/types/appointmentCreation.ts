import type { PotatoAppointment } from './appointment';

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
  invitedFriends?: string[];
  timeSlots?: AppointmentCreationTimeSlot[];
  selectedCalendarDate?: string;
  timeInput?: AppointmentCreationTimeInput;
  editingTimeSlotId?: string;
  selectedAiRecommendationTime?: string;
}
