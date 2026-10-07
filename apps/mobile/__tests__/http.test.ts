import { HttpRepository } from '../src/data/HttpRepository';
import { fixture } from '../src/data/fixtures';
test('HTTP boundary validates response and does not trust client actor identity', async () => {
  const fetcher = jest
    .fn()
    .mockResolvedValue({ ok: true, json: async () => fixture('feasible') });
  const r = new HttpRepository(
    'https://example.test/v1/',
    async () => 'test-token',
    fetcher,
  );
  await r.consent('a/b', 'untrusted-actor', 'agreed', '', 1, 4);
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
