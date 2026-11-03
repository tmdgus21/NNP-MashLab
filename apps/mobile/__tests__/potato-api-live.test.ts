/**
 * Contract test of the real mobile API client against a RUNNING server.
 * Skipped unless POTATO_LIVE_API_URL is set (e.g. http://127.0.0.1:8765 with a
 * local API + Worker). It never talks to the production host.
 */
import {
  createPotatoApi,
  newRequestKey,
  PotatoApiError,
  type PotatoApi,
} from '../src/potato/services/potatoApi';

const baseUrl = (
  globalThis as { process?: { env?: Record<string, string | undefined> } }
).process?.env?.POTATO_LIVE_API_URL;
const live = baseUrl ? describe : describe.skip;

if (baseUrl && /oranganman/i.test(baseUrl)) {
  throw new Error('Refusing to run the live contract test against production.');
}

function seoulDate(offsetDays: number): string {
  const seoul = new Date(Date.now() + 9 * 3600 * 1000 + offsetDays * 86400 * 1000);
  return seoul.toISOString().slice(0, 10);
}

interface Player {
  name: string;
  nickname: string;
  token: string | null;
  accountId: string;
  api: PotatoApi;
}

function player(name: string, nickname: string): Player {
  const state: Player = { name, nickname, token: null, accountId: '', api: undefined as never };
  state.api = createPotatoApi({
    baseUrl: baseUrl ?? 'http://skipped.invalid', // never used: the suite is skipped without a URL
    token: async () => state.token,
    fetcher: (globalThis as { fetch: typeof fetch }).fetch,
  });
  return state;
}

live('Potato API client against a live server (4 players)', () => {
  const suffix = Date.now().toString(36);
  const players = {
    host: player('host', '방장'),
    a: player('a', '민수'),
    b: player('b', '지훈'),
    c: player('c', '영희'),
  };
  const windows: Record<keyof typeof players, [number, number]> = {
    host: [540, 720],
    a: [600, 780],
    b: [630, 800],
    c: [660, 900],
  };

  test('register, login and me work with a real token (no verification code)', async () => {
    for (const p of Object.values(players)) {
      const email = `${p.name}-${suffix}@example.test`;
      const step = async <T>(label: string, work: () => Promise<T>): Promise<T> => {
        try {
          return await work();
        } catch (error) {
          throw new Error(`${p.name} ${label}: ${(error as Error).message}`);
        }
      };
      await step('register', () => p.api.auth.register(email, 'mobile-pass-123456'));
      const session = await step('login', () => p.api.auth.login(email, 'mobile-pass-123456'));
      p.token = session.token;
      p.accountId = session.accountId;
      expect((await step('me', () => p.api.auth.me())).accountId).toBe(p.accountId);
    }
    await expect(
      players.host.api.auth.login(`host-${suffix}@example.test`, 'wrong-password-123'),
    ).rejects.toMatchObject({ status: 401 });
  });

  test('create, join by code, submit availability, run, decide, finalize', async () => {
    const { host, a, b, c } = players;
    const d1 = seoulDate(3);
    const room = await host.api.rooms.create(
      {
        title: '모바일 계약 테스트',
        activity: '식사',
        location: '강남역',
        durationMinutes: 60,
        dates: [d1, seoulDate(4)],
        minimumAttendeeCount: 2,
        nickname: host.nickname,
      },
      newRequestKey('create'),
    );
    expect(room.me?.role).toBe('organizer');
    for (const p of [a, b, c]) {
      const joined = await p.api.rooms.join(room.code.toLowerCase(), p.nickname);
      expect(joined.me?.role).toBe('invitee');
    }

    const people = (await host.api.rooms.participants(room.roomId)).participants;
    expect(people.map(x => x.displayName).sort()).toEqual(['민수', '방장', '영희', '지훈']);
    const codeJoiners = people.filter(x => x.joinPath === 'code');
    expect(codeJoiners).toHaveLength(3);
    for (const person of codeJoiners) {
      expect([person.invitationStatus, person.participationStatus]).toEqual(['not_sent', 'accepted']);
      expect(person.availability.status).toBe('not_submitted'); // not an absence
    }

    await expect(a.api.availability.put(room.roomId, [])).rejects.toMatchObject({
      status: 422,
      code: 'AVAILABILITY_EMPTY',
    });
    for (const [key, p] of Object.entries(players) as [keyof typeof players, Player][]) {
      const [start, end] = windows[key];
      const saved = await p.api.availability.put(room.roomId, [
        { date: d1, startTimeMinutes: start, endTimeMinutes: end },
      ]);
      expect(saved.version).toBe(1);
    }

    const fresh = await host.api.rooms.get(room.roomId);
    const accepted = await host.api.runs.start(
      room.roomId,
      fresh.agentInputRevision,
      newRequestKey('run'),
    );
    let status = accepted.status;
    for (let i = 0; i < 80 && (status === 'QUEUED' || status === 'RUNNING'); i += 1) {
      await new Promise<void>(resolve => setTimeout(resolve, 500));
      status = (await host.api.runs.get(room.roomId, accepted.runId)).status;
    }
    expect(status).toBe('ALL_AVAILABLE'); // computed by the separate Worker process

    const { candidates } = await host.api.runs.candidates(room.roomId, accepted.runId);
    expect(candidates[0].members).toHaveLength(4);
    const candidateId = candidates[0].candidateId;

    await expect(
      a.api.decision.select(room.roomId, accepted.runId, candidateId),
    ).rejects.toBeInstanceOf(PotatoApiError);
    const selected = await host.api.decision.select(room.roomId, accepted.runId, candidateId, 0);
    expect(selected.selectedCandidateId).toBe(candidateId);
    for (const p of Object.values(players)) {
      await p.api.decision.consent(room.roomId, accepted.runId, 'AGREE');
    }
    const ready = await host.api.decision.get(room.roomId, accepted.runId);
    expect(ready.allAgreed).toBe(true);
    await host.api.decision.approve(room.roomId, accepted.runId, 'APPROVE');
    const done = await host.api.decision.finalize(room.roomId, accepted.runId);
    expect(done.finalized).toBe(true);

    const results = await Promise.all(
      Object.values(players).map(p => p.api.decision.finalResult(room.roomId)),
    );
    expect(results.every(r => r.finalized)).toBe(true);
    expect(new Set(results.map(r => r.startsAt)).size).toBe(1);

    const home = await b.api.rooms.list();
    expect(home.rooms[0]).toMatchObject({ roomId: room.roomId, finalized: true, myNickname: '지훈' });
  }, 60000);

  test('network failure and bad tokens are typed errors, not silent successes', async () => {
    const offline = createPotatoApi({
      baseUrl: 'http://127.0.0.1:1',
      token: async () => null,
      fetcher: (globalThis as { fetch: typeof fetch }).fetch,
    });
    await expect(offline.rooms.list()).rejects.toMatchObject({ status: 0, code: 'NETWORK' });
    const anonymous = createPotatoApi({
      baseUrl: baseUrl as string,
      token: async () => 'not-a-real-token',
      fetcher: (globalThis as { fetch: typeof fetch }).fetch,
    });
    await expect(anonymous.rooms.list()).rejects.toMatchObject({ status: 401 });
  });
});
