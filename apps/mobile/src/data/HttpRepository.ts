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

const sessionSchema = z.object({ meeting: meetingSchema, actorId: z.string() });
export class HttpRepository implements Repository {
  readonly mode = 'http' as const;
  constructor(
    private baseUrl: string,
    private token: () => Promise<string | null>,
    private fetcher: typeof fetch = fetch,
  ) {}
  private async request<T>(
    path: string,
    method: string,
    schema: z.ZodType<T>,
    body?: unknown,
  ): Promise<T> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
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
        throw new Error(
          messages[response.status] ?? `서버 요청 실패 (${response.status})`,
        );
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
  // Wire secure auth/session restoration here when the backend is available.
  async restore() {
    return null;
  }
  create(input: CreateMeeting) {
    return this.request('/meetings', 'POST', sessionSchema, input);
  }
  join(code: string, name: string) {
    return this.request('/meetings/join', 'POST', sessionSchema, {
      code,
      name,
    });
  }
  get(id: string) {
    return this.request(
      `/meetings/${encodeURIComponent(id)}`,
      'GET',
      meetingSchema,
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
      meetingSchema,
      { conditions, expectedRevision },
    );
  }
  calculate(id: string, _actor: string, expectedRevision: number) {
    return this.request(
      `/meetings/${encodeURIComponent(id)}/calculations`,
      'POST',
      meetingSchema,
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
      meetingSchema,
      { consent, note, round, expectedRevision },
    );
  }
  finalize(id: string, _actor: string, expectedRevision: number) {
    return this.request(
      `/meetings/${encodeURIComponent(id)}/finalize`,
      'POST',
      meetingSchema,
      { expectedRevision },
    );
  }
  parseConditions(text: string) {
    return this.request('/conditions/parse', 'POST', parseSchema, {
      text,
      timezone: 'Asia/Seoul',
    });
  }
}
