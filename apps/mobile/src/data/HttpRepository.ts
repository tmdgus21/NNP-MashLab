import { z } from 'zod';
import {
  Conditions,
  Consent,
  CreateMeeting,
  meetingSchema,
  parseSchema,
  previewSchema,
} from '../domain/model';
import { Repository } from './RepositoryPort';
import { SessionVault } from './sessionTypes';

// Wire DTOs use `code`; the app and Mock use `roomCode` exclusively.
// Validate the server field before mapping: never accept a Mock-shaped response
// as proof that the server contract is correct.
const serverMeetingSchema = meetingSchema
  .omit({ roomCode: true })
  .extend({ code: z.string() })
  .transform(({ code, ...meeting }) => ({ ...meeting, roomCode: code }));
const sessionSchema = z.object({
  meeting: serverMeetingSchema,
  actorId: z.string(),
});
const authenticatedSessionSchema = sessionSchema.extend({token:z.string().min(20)});
export class HttpRepository implements Repository {
  readonly mode = 'http' as const;
  constructor(
    private baseUrl: string,
    private token: () => Promise<string | null>,
    private fetcher: typeof fetch = fetch,
    private vault?: SessionVault,
  ) {}
  private async request<T>(
    path: string,
    method: string,
    schema: z.ZodType<T>,
    body?: unknown,
    timeoutMs = 20000,
    requestKey?: string,
  ): Promise<T> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const token = await this.token();
      const response = await this.fetcher(
        `${this.baseUrl.replace(/\/$/, '')}${path}`,
        {
          method,
          signal: controller.signal,
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(requestKey ? {'Idempotency-Key':requestKey} : {}),
          },
          ...(body === undefined ? {} : { body: JSON.stringify(body) }),
        },
      );
      if (!response.ok) {
        const messages: Record<number, string> = {
          401: '로그인이 필요합니다.',
          403: '이 작업을 할 권한이 없습니다.',
          404: '모임을 찾을 수 없습니다.',
          409: '다른 변경이 있습니다. 새로고침 후 다시 시도해 주세요.',
          422: '조건 입력값을 확인해 주세요.',
        };
        let detail: unknown;
        try { detail = (await response.json()).detail; } catch {}
        throw new Error(typeof detail === 'string' ? detail : messages[response.status] ?? `서버 요청 실패 (${response.status})`);
      }
      const parsed = schema.safeParse(await response.json());
      if (!parsed.success) {
        throw new Error('서버 응답 형식이 계약과 다릅니다.');
      }
      return parsed.data;
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') {
        throw new Error('서버 응답 시간이 초과됐습니다. 다시 시도해 주세요.');
      }
      throw e;
    } finally {
      clearTimeout(timeout);
    }
  }
  async restore() {
    if (!this.vault || !(await this.vault.read())) {return null;}
    return this.request('/session', 'GET', sessionSchema);
  }
  private async remember(result:z.infer<typeof authenticatedSessionSchema>) {
    await this.vault?.save({meetingId:result.meeting.id, actorId:result.actorId, token:result.token, title:result.meeting.title, name:result.meeting.participants.find(p=>p.id===result.actorId)?.name ?? ''});
    return {meeting:result.meeting, actorId:result.actorId};
  }
  async create(input: CreateMeeting) {
    return this.enter('/meetings',input);
  }
  private async enter(path:string, body:unknown) {
    const fingerprint=path+JSON.stringify(body);
    const key=await this.vault?.requestKey?.(fingerprint);
    const result=await this.remember(await this.request(path,'POST',authenticatedSessionSchema,body,20000,key));
    await this.vault?.completeRequest?.(fingerprint);
    return result;
  }
  async join(roomCode: string, name: string) {
    return this.enter('/meetings/join', {
      code: roomCode.trim().toUpperCase(),
      name,
    });
  }
  get(id: string) {
    return this.request(
      `/meetings/${encodeURIComponent(id)}`,
      'GET',
      serverMeetingSchema,
    );
  }
  preview(
    id: string,
    _actor: string,
    conditions: Conditions,
    expectedRevision: number,
  ) {
    return this.request(
      `/meetings/${encodeURIComponent(id)}/conditions/preview`,
      'POST',
      previewSchema,
      { conditions, expectedRevision },
    );
  }
  updateConditions(
    id: string,
    _actor: string,
    conditions: Conditions,
    expectedRevision: number,
  ) {
    return this.request(
      `/meetings/${encodeURIComponent(id)}/conditions`,
      'PUT',
      serverMeetingSchema,
      { conditions, expectedRevision },
    );
  }
  calculate(id: string, _actor: string, expectedRevision: number) {
    return this.request(
      `/meetings/${encodeURIComponent(id)}/calculations`,
      'POST',
      serverMeetingSchema,
      { expectedRevision },
    );
  }
  consent(
    id: string,
    _actor: string,
    consent: Consent,
    note: string,
    round: number,
    expectedRevision: number,
  ) {
    return this.request(
      `/meetings/${encodeURIComponent(id)}/consent`,
      'PUT',
      serverMeetingSchema,
      { consent, note, round, expectedRevision },
    );
  }
  finalize(id: string, _actor: string, expectedRevision: number) {
    return this.request(
      `/meetings/${encodeURIComponent(id)}/finalize`,
      'POST',
      serverMeetingSchema,
      { expectedRevision },
    );
  }
  parseConditions(text: string, context?: {meetingId:string; date:string}) {
    if (!context) {return Promise.reject(new Error('모임과 후보 날짜를 선택해 주세요.'));}
    return this.request(`/meetings/${encodeURIComponent(context.meetingId)}/conditions/parse`, 'POST', parseSchema, {text,meeting_date:context.date}, 75000);
  }
}
