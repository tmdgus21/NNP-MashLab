export interface StoredSession {
  meetingId: string;
  actorId: string;
  token: string;
  title: string;
  name: string;
}
export interface SessionVault {
  read(): Promise<StoredSession | null>;
  save(value: StoredSession): Promise<void>;
  requestKey?(fingerprint:string): Promise<string>;
  completeRequest?(fingerprint:string): Promise<void>;
}
