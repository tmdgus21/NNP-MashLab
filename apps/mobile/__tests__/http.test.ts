import { HttpRepository } from '../src/data/HttpRepository';
import { fixture } from '../src/data/fixtures';

function serverMeeting() {
  const { roomCode, ...meeting } = fixture('feasible');
  expect(roomCode).toBe('OK2026');
  return { ...meeting, code: 'SERVER42' };
}
test('HTTP boundary validates response and does not trust client actor identity', async () => {
  const fetcher = jest
    .fn()
    .mockResolvedValue({ ok: true, json: async () => serverMeeting() });
  const r = new HttpRepository(
    'https://example.test/v1/',
    async () => 'test-token',
    fetcher,
  );
  const result = await r.consent('a/b', 'untrusted-actor', 'agreed', '', 1, 4);
  expect(result.roomCode).toBe('SERVER42');
  expect(result).not.toHaveProperty('code');
  const [url, options] = fetcher.mock.calls[0];
  expect(url).toBe('https://example.test/v1/meetings/a%2Fb/consent');
  expect(options.headers.Authorization).toBe('Bearer test-token');
  expect(JSON.parse(options.body)).toEqual({
    consent: 'agreed',
    note: '',
    round: 1,
    expectedRevision: 4,
  });
  fetcher.mockResolvedValueOnce({
    ok: true,
    json: async () => ({ wrong: true }),
  });
  await expect(r.get('id')).rejects.toThrow('응답 형식');
});

test('join maps domain roomCode to wire code and nested response back to roomCode', async () => {
  const fetcher = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ meeting: serverMeeting(), actorId: 'p2', token:'test-token-at-least-twenty-chars' }),
  });
  const r = new HttpRepository(
    'https://example.test/v1',
    async () => null,
    fetcher,
  );
  const result = await r.join('SERVER42', '참가자');
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({
    code: 'SERVER42',
    name: '참가자',
  });
  expect(result.meeting.roomCode).toBe('SERVER42');
  expect(result.meeting).not.toHaveProperty('code');
});

test('create maps the server code without changing unrelated fields', async () => {
  const wire = { meeting: serverMeeting(), actorId: 'p1', token:'test-token-at-least-twenty-chars' };
  const fetcher = jest
    .fn()
    .mockResolvedValue({ ok: true, json: async () => wire });
  const r = new HttpRepository(
    'https://example.test/v1',
    async () => null,
    fetcher,
  );
  const result = await r.create({
    title: '모임',
    name: '방장',
    dates: ['2026-10-17'],
    roles: ['진행'],
    duration: 60,
    windowStart: 540,
    windowEnd: 1080,
  });
  const { code, ...rest } = wire.meeting;
  expect(result).toEqual({
    actorId: 'p1',
    meeting: { ...rest, roomCode: code },
  });
  expect(wire.meeting).toHaveProperty('code', 'SERVER42');
});

test('read uses server code even if an extra roomCode is present', async () => {
  const fetcher = jest
    .fn()
    .mockResolvedValue({
      ok: true,
      json: async () => ({ ...serverMeeting(), roomCode: 'WRONG' }),
    });
  const r = new HttpRepository(
    'https://example.test/v1',
    async () => null,
    fetcher,
  );
  expect((await r.get('demo')).roomCode).toBe('SERVER42');
});

test.each([undefined, null, 42])(
  'rejects invalid server code %s instead of falling back to domain roomCode',
  async code => {
    const fetcher = jest
      .fn()
      .mockResolvedValue({
        ok: true,
        json: async () => ({ ...fixture('feasible'), code }),
      });
    const r = new HttpRepository(
      'https://example.test/v1',
      async () => null,
      fetcher,
    );
    await expect(r.get('demo')).rejects.toThrow('응답 형식');
  },
);
test.each([
  [401, '로그인'],
  [403, '권한'],
  [409, '다른 변경'],
  [422, '입력값'],
  [500, '서버 요청'],
])('HTTP %s produces actionable error', async (status, message) => {
  const fetcher = jest.fn().mockResolvedValue({ ok: false, status });
  const r = new HttpRepository(
    'https://example.test',
    async () => null,
    fetcher,
  );
  await expect(r.get('id')).rejects.toThrow(String(message));
});
