import {
  Conditions,
  Consent,
  CreateMeeting,
  Meeting,
  ParseResult,
  Preview,
  Session,
} from '../domain/model';
/** Server owns optimization, revisions and authorization. HTTP actor derives from auth. */
export interface Repository {
  readonly mode: 'mock' | 'http';
  restore(): Promise<Session | null>;
  create(input: CreateMeeting): Promise<Session>;
  join(code: string, name: string): Promise<Session>;
  get(id: string): Promise<Meeting>;
  preview(
    id: string,
    actorId: string,
    conditions: Conditions,
    expectedRevision: number,
  ): Promise<Preview>;
  updateConditions(
    id: string,
    actorId: string,
    conditions: Conditions,
    expectedRevision: number,
  ): Promise<Meeting>;
  calculate(
    id: string,
    actorId: string,
    expectedRevision: number,
  ): Promise<Meeting>;
  consent(
    id: string,
    actorId: string,
    consent: Consent,
    note: string,
    round: number,
    expectedRevision: number,
  ): Promise<Meeting>;
  finalize(
    id: string,
    actorId: string,
    expectedRevision: number,
  ): Promise<Meeting>;
  parseConditions(text: string): Promise<ParseResult>;
}
export type Scenario =
  | 'feasible'
  | 'conflict'
  | 'infeasible'
  | 'changed'
  | 'finalized'
  | 'empty';
export interface Storage {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<unknown>;
}
