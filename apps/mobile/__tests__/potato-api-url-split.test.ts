/**
 * Release contract: the app talks to ONE origin, with auth on /v1/auth/* and everything
 * else on /v2/*. A stub fetcher records the URLs; no network is used.
 */
import { API_BASE_URL } from '../src/config/runtime.generated';
import { createPotatoApi } from '../src/potato/services/potatoApi';
import { createPotatoRuntime, serverOrigin } from '../src/potato/services/potatoRuntime';

function recorder() {
  const urls: string[] = [];
  const fetcher = (async (url: string) => {
    urls.push(String(url));
    return { ok: false, status: 404, text: async () => '{}' } as unknown as Response;
  }) as unknown as typeof fetch;
  return { urls, fetcher };
}

const swallow = (p: Promise<unknown>) => p.catch(() => undefined);

describe('API URL split (/v1/auth vs /v2)', () => {
  it('production build points at the https origin and derives it from API_BASE_URL', () => {
    expect(API_BASE_URL).toBe('https://oranganman.site/v1');
    expect(serverOrigin()).toBe('https://oranganman.site');
    expect(serverOrigin('https://oranganman.site/v1/')).toBe('https://oranganman.site');
  });

  it('auth calls use /v1/auth/*, every other call uses /v2/*', async () => {
    const { urls, fetcher } = recorder();
    const runtime = createPotatoRuntime({ fetcher, baseUrl: serverOrigin() });
    const { api } = runtime;
    await swallow(api.auth.register('a@example.test', 'pw-12345678'));
    await swallow(api.auth.login('a@example.test', 'pw-12345678'));
    await swallow(api.auth.me());
    await swallow(api.auth.logout());
    const authCount = urls.length;
    await swallow(api.rooms.list());
    await swallow(api.rooms.join('abc123', '닉'));
    await swallow(api.rooms.get('r1'));
    await swallow(api.availability.get('r1'));
    await swallow(api.runs.start('r1', 1, 'k'));
    await swallow(api.runs.latest('r1'));
    await swallow(api.decision.finalResult('r1'));

    const auth = urls.slice(0, authCount);
    const rest = urls.slice(authCount);
    expect(auth).toHaveLength(4);
    auth.forEach(u => expect(u).toMatch(/^https:\/\/oranganman\.site\/v1\/auth\/(register|login|me|logout)$/));
    expect(rest).toHaveLength(7);
    rest.forEach(u => expect(u).toMatch(/^https:\/\/oranganman\.site\/v2\/rooms/));
    urls.forEach(u => {
      expect(u).not.toContain('/v1/v');
      expect(u).not.toContain('/v2/auth');
      expect(u).not.toContain('/v1/meetings');
      expect(u.startsWith('http://')).toBe(false);
    });
  });

  it('a /v1 suffix on the configured base is never doubled', async () => {
    const { urls, fetcher } = recorder();
    const api = createPotatoApi({ baseUrl: `${serverOrigin()}/`, token: async () => null, fetcher });
    await swallow(api.rooms.list());
    expect(urls).toEqual(['https://oranganman.site/v2/rooms']);
  });
});
