import { create } from 'zustand';
import {
  Conditions,
  Consent,
  CreateMeeting,
  Meeting,
  Preview,
  Session,
} from '../domain/model';
import { repository, mockRepository } from '../data/repositoryInstance';
import { Scenario } from '../data/RepositoryPort';

interface AppState {
  meeting: Meeting | null;
  actorId: string;
  ready: boolean;
  busy: string | null;
  error: string | null;
  restore(): Promise<void>;
  create(input: CreateMeeting): Promise<void>;
  join(code: string, name: string): Promise<void>;
  scenario(s: Scenario): Promise<void>;
  refresh(): Promise<void>;
  switchActor(id: string): Promise<void>;
  preview(c: Conditions): Promise<Preview | undefined>;
  apply(c: Conditions, revision: number): Promise<boolean>;
  calculate(): Promise<void>;
  consent(c: Consent, note?: string): Promise<void>;
  finalize(): Promise<void>;
  leave(): void;
  clearError(): void;
}
export const useApp = create<AppState>((set, get) => {
  const run = async <T>(
    label: string,
    task: () => Promise<T>,
  ): Promise<T | undefined> => {
    if (get().busy) {
      return undefined;
    }
    set({ busy: label, error: null });
    try {
      return await task();
    } catch (e) {
      set({ error: e instanceof Error ? e.message : '요청에 실패했습니다.' });
      return undefined;
    } finally {
      set({ busy: null });
    }
  };
  const session = (s: Session) =>
    set({ meeting: s.meeting, actorId: s.actorId });
  const update = async (
    task: (m: Meeting, actor: string) => Promise<Meeting>,
  ) => {
    const { meeting, actorId } = get();
    if (meeting) {
      set({ meeting: await task(meeting, actorId) });
    }
  };
  return {
    meeting: null,
    actorId: '',
    ready: false,
    busy: null,
    error: null,
    restore: async () => {
      await run('저장된 모임을 불러오는 중', async () => {
        const s = await repository.restore();
        if (s) {
          session(s);
        }
      });
      set({ ready: true });
    },
    create: async input => {
      await run('모임을 만드는 중', async () =>
        session(await repository.create(input)),
      );
    },
    join: async (code, name) => {
      await run('모임에 참가하는 중', async () =>
        session(await repository.join(code, name)),
      );
    },
    scenario: async scenario => {
      await run('데모를 준비하는 중', async () =>
        session(await mockRepository.scenario(scenario)),
      );
    },
    refresh: async () => {
      await run('최신 현황을 불러오는 중', () =>
        update(m => repository.get(m.id)),
      );
    },
    switchActor: async actorId => {
      const m = get().meeting;
      if (m && repository.mode === 'mock') {
        await run('참가자 전환 중', async () => {
          await mockRepository.switchActor(m.id, actorId);
          set({ actorId });
        });
      }
    },
    preview: c =>
      run('변경 영향을 계산하는 중', async () => {
        const { meeting: m, actorId } = get();
        if (!m) {
          throw new Error('모임을 선택해 주세요.');
        }
        return repository.preview(m.id, actorId, c, m.revision);
      }),
    apply: async (c, revision) =>
      (await run('조건을 저장하는 중', async () => {
        await update((m, actor) =>
          repository.updateConditions(m.id, actor, c, revision),
        );
        return true;
      })) ?? false,
    calculate: async () => {
      await run('가능한 담당표를 계산하는 중', () =>
        update((m, actor) => repository.calculate(m.id, actor, m.revision)),
      );
    },
    consent: async (c, note = '') => {
      await run('응답을 저장하는 중', () =>
        update((m, actor) =>
          repository.consent(m.id, actor, c, note, m.round, m.revision),
        ),
      );
    },
    finalize: async () => {
      await run('최종 확정 중', () =>
        update((m, actor) => repository.finalize(m.id, actor, m.revision)),
      );
    },
    leave: () => set({ meeting: null, actorId: '', error: null }),
    clearError: () => set({ error: null }),
  };
});
