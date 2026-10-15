import { z } from 'zod';

export const intervalSchema = z
  .object({
    date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
    start: z.number().int().min(0).max(1410).multipleOf(30),
    end: z.number().int().min(30).max(1440).multipleOf(30),
  })
  .refine(v => v.start < v.end, '종료는 시작 이후여야 합니다.');
export const conditionsSchema = z.object({
  roles: z.array(z.string()),
  availability: z.array(intervalSchema),
  preference: z.enum(['balanced', 'early', 'late']),
  companionId: z.string().nullable(),
  note: z.string().max(1000),
  unavailable: z.array(intervalSchema).optional(),
  requiredRoles: z.array(z.string()).optional(),
  roleUnavailable: z.array(z.string()).optional(),
  rolePreferences: z.array(z.string()).optional(),
  timePreferences: z.array(z.object({date: z.string(), start: z.number().int().multipleOf(30), end: z.number().int().multipleOf(30), kind: z.enum(['available', 'unavailable'])})).optional(),
  companionRequirements: z.array(z.object({participantId: z.string(), relation: z.enum(['together', 'apart']), strength: z.enum(['required', 'preferred'])})).optional(),
  aiDraftId: z.string().nullable().optional(),
  ambiguitiesResolved: z.boolean().optional(),
});
export const participantSchema = z.object({
  id: z.string(),
  name: z.string(),
  conditions: conditionsSchema,
  consent: z.enum(['pending', 'agreed', 'review']),
  consentRound: z.number().int(),
  reviewNote: z.string(),
  submitted: z.boolean().optional(),
  conditionVersion: z.number().int().optional(),
});
export const assignmentSchema = z.object({
  id: z.string(),
  role: z.string(),
  participantId: z.string(),
  interval: intervalSchema,
  status: z.enum(['proposed', 'confirmed']),
});
export const noticeSchema = z.object({
  id: z.string(),
  kind: z.enum(['info', 'warning', 'error']),
  title: z.string(),
  detail: z.string(),
});
export const planSchema = z.object({
  round: z.number().int(),
  status: z.enum(['idle', 'calculating', 'feasible', 'infeasible', 'unknown']),
  solverStatus: z.enum(['OPTIMAL', 'FEASIBLE', 'INFEASIBLE', 'UNKNOWN']).optional(),
  assignments: z.array(assignmentSchema),
  notices: z.array(noticeSchema),
});
export const meetingSchema = z.object({
  id: z.string(),
  roomCode: z.string(),
  title: z.string(),
  hostId: z.string(),
  timezone: z.literal('Asia/Seoul'),
  dates: z.array(z.string()).min(1),
  roles: z.array(z.string()).min(1),
  roleNeeds: z.record(z.string(), z.number().int().positive()).optional(),
  duration: z.number().int().positive().multipleOf(30),
  windowStart: z.number().int(),
  windowEnd: z.number().int(),
  revision: z.number().int(),
  round: z.number().int(),
  status: z.enum(['collecting', 'reviewing', 'finalized']),
  participants: z.array(participantSchema),
  plan: planSchema,
  previousPlan: planSchema.nullable(),
  history: z.array(z.string()),
});
export const previewSchema = z.object({
  revision: z.number(),
  before: planSchema,
  after: planSchema,
  changes: z.array(z.string()),
});
export const parseSchema = z.object({
  draft: conditionsSchema.partial(),
  questions: z.array(z.string()),
  source: z.enum(['mock', 'server']),
  parseId: z.string().optional(),
  raw: z.unknown().optional(),
});
export type Interval = z.infer<typeof intervalSchema>;
export type Conditions = z.infer<typeof conditionsSchema>;
export type Participant = z.infer<typeof participantSchema>;
export type Assignment = z.infer<typeof assignmentSchema>;
export type Plan = z.infer<typeof planSchema>;
export type Meeting = z.infer<typeof meetingSchema>;
export type Preview = z.infer<typeof previewSchema>;
export type ParseResult = z.infer<typeof parseSchema>;
export type Consent = Participant['consent'];
export interface CreateMeeting {
  title: string;
  name: string;
  dates: string[];
  roles: string[];
  roleNeeds?: Record<string, number>;
  duration: number;
  windowStart: number;
  windowEnd: number;
}
export interface Session {
  meeting: Meeting;
  actorId: string;
}
export const emptyConditions = (): Conditions => ({
  roles: [],
  availability: [],
  preference: 'balanced',
  companionId: null,
  note: '',
});
export const consentLabel: Record<Consent, string> = {
  pending: '동의 대기',
  agreed: '동의 완료',
  review: '검토 요청',
};
export const planLabel: Record<Plan['status'], string> = {
  idle: '조건 수집 중',
  calculating: '계산 중',
  feasible: '배정 가능',
  infeasible: '배정 불가',
  unknown: '계산 시간 초과 · 해 여부 미확인',
};
