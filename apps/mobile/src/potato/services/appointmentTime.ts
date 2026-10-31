import type { AppointmentCreationTimeSlot } from '../types/appointmentCreation';

export interface TimeInputParts {
  hour: string;
  minute: string;
}

export interface ParsedTimeRange {
  startTimeMinutes: number;
  endTimeMinutes: number;
}

export type TimeRangeValidation =
  | { valid: true; value: ParsedTimeRange }
  | { valid: false; message: string };

export function formatDateKey(year: number, month: number, day: number): string {
  return `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

export function isValidDateKey(value: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) {
    return false;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (month < 1 || month > 12 || day < 1) {
    return false;
  }
  const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const daysInMonth = [
    31,
    leapYear ? 29 : 28,
    31,
    30,
    31,
    30,
    31,
    31,
    30,
    31,
    30,
    31,
  ][month - 1];
  return day <= daysInMonth;
}

export function splitTimeMinutes(totalMinutes: number): TimeInputParts {
  const normalized = Math.min(24 * 60, Math.max(0, Math.trunc(totalMinutes)));
  return {
    hour: String(Math.floor(normalized / 60)).padStart(2, '0'),
    minute: String(normalized % 60).padStart(2, '0'),
  };
}

export function formatTimeMinutes(totalMinutes: number): string {
  const parts = splitTimeMinutes(totalMinutes);
  return `${parts.hour}:${parts.minute}`;
}

export function parseTimeRange(
  startHour: string,
  startMinute: string,
  endHour: string,
  endMinute: string,
): TimeRangeValidation {
  const values = [startHour, startMinute, endHour, endMinute];
  if (values.some(value => !/^\d{1,2}$/.test(value))) {
    return { valid: false, message: '시작과 종료 시간을 입력해주세요.' };
  }

  const [startHourValue, startMinuteValue, endHourValue, endMinuteValue] =
    values.map(Number);
  if (
    startHourValue > 23 ||
    startMinuteValue > 59 ||
    endHourValue > 24 ||
    endMinuteValue > 59 ||
    (endHourValue === 24 && endMinuteValue !== 0)
  ) {
    return {
      valid: false,
      message: '시간은 00:00부터 24:00 사이로 입력해주세요.',
    };
  }

  const startTimeMinutes = startHourValue * 60 + startMinuteValue;
  const endTimeMinutes = endHourValue * 60 + endMinuteValue;
  if (startTimeMinutes >= endTimeMinutes) {
    return {
      valid: false,
      message: '종료 시간은 시작 시간보다 늦어야 합니다.',
    };
  }

  return {
    valid: true,
    value: { startTimeMinutes, endTimeMinutes },
  };
}

export function mergeAppointmentTimeSlots(
  slots: readonly AppointmentCreationTimeSlot[],
): AppointmentCreationTimeSlot[] {
  const sorted = slots
    .map(slot => ({ ...slot }))
    .sort(
      (left, right) =>
        left.date.localeCompare(right.date) ||
        left.startTimeMinutes - right.startTimeMinutes ||
        left.endTimeMinutes - right.endTimeMinutes,
    );
  const merged: AppointmentCreationTimeSlot[] = [];

  for (const slot of sorted) {
    const previous = merged[merged.length - 1];
    if (
      previous &&
      previous.date === slot.date &&
      previous.endTimeMinutes >= slot.startTimeMinutes
    ) {
      previous.endTimeMinutes = Math.max(
        previous.endTimeMinutes,
        slot.endTimeMinutes,
      );
    } else {
      merged.push(slot);
    }
  }

  return merged;
}
