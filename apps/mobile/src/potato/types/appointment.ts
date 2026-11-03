export interface PotatoAppointment {
  id: string | number;
  title: string;
  category: string;
  duration: string;
  location: string;
  timeInfo: string;
  date: string;
  invitedFriends: string[];
  /** false while the time is still being coordinated (default: shown as confirmed). */
  confirmed?: boolean;
}

export type PotatoTabRoute =
  | 'home'
  | 'create_step1'
  | 'friends'
  | 'mypage';
