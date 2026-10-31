export interface PotatoAppointment {
  id: string | number;
  title: string;
  category: string;
  duration: string;
  location: string;
  timeInfo: string;
  date: string;
  invitedFriends: string[];
}

export type PotatoTabRoute =
  | 'home'
  | 'create_step1'
  | 'friends'
  | 'mypage';
