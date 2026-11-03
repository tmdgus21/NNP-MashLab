import { API_BASE_URL } from '../../config/runtime.generated';
import type { PotatoAuthService } from './authService';
import { createHttpAuthService } from './httpAuthService';
import { createPotatoApi, type PotatoApi } from './potatoApi';
import { keychainSessionStore, type PotatoSessionStore } from './potatoSession';

export interface PotatoRuntime {
  api: PotatoApi;
  sessions: PotatoSessionStore;
  auth: PotatoAuthService;
  setToken(token: string | null): void;
  hasToken(): boolean;
}

/** The v2 API lives next to /v1: derive the server origin from the configured API URL. */
export function serverOrigin(apiBaseUrl: string = API_BASE_URL): string {
  return new URL(apiBaseUrl).origin;
}

export function createPotatoRuntime(options?: {
  baseUrl?: string;
  sessions?: PotatoSessionStore;
  fetcher?: typeof fetch;
}): PotatoRuntime {
  let token: string | null = null;
  const sessions = options?.sessions ?? keychainSessionStore;
  const api = createPotatoApi({
    baseUrl: options?.baseUrl ?? serverOrigin(),
    token: async () => token,
    fetcher: options?.fetcher,
  });
  return {
    api,
    sessions,
    auth: createHttpAuthService(api, sessions),
    setToken(next) {
      token = next;
    },
    hasToken() {
      return token !== null;
    },
  };
}
