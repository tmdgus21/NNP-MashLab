import * as Keychain from 'react-native-keychain';

export interface PotatoSession {
  token: string;
  accountId: string;
  email: string;
  /** Default room display name. The server stores names per room, not per account. */
  nickname: string;
}

export interface PotatoSessionStore {
  load(): Promise<PotatoSession | null>;
  save(session: PotatoSession): Promise<void>;
  clear(): Promise<void>;
  rememberNickname(email: string, nickname: string): Promise<void>;
  nicknameFor(email: string): Promise<string | null>;
}

const SERVICE = 'com.conditionalok.app.potato.session.v1';

interface Vault {
  session: PotatoSession | null;
  nicknames: Record<string, string>;
}

const normalize = (email: string) => email.trim().toLowerCase();

export function createSessionStore(
  backend: {
    read(): Promise<string | null>;
    write(value: string): Promise<void>;
  },
): PotatoSessionStore {
  const load = async (): Promise<Vault> => {
    const raw = await backend.read();
    if (!raw) {
      return { session: null, nicknames: {} };
    }
    try {
      const parsed = JSON.parse(raw) as Partial<Vault>;
      return { session: parsed.session ?? null, nicknames: parsed.nicknames ?? {} };
    } catch {
      return { session: null, nicknames: {} };
    }
  };
  const persist = (vault: Vault) => backend.write(JSON.stringify(vault));
  return {
    async load() {
      return (await load()).session;
    },
    async save(session) {
      const vault = await load();
      vault.session = session;
      await persist(vault);
    },
    async clear() {
      const vault = await load();
      vault.session = null;
      await persist(vault);
    },
    async rememberNickname(email, nickname) {
      const vault = await load();
      vault.nicknames[normalize(email)] = nickname;
      await persist(vault);
    },
    async nicknameFor(email) {
      return (await load()).nicknames[normalize(email)] ?? null;
    },
  };
}

/** Token storage in the platform keychain (never AsyncStorage / plain files). */
export const keychainSessionStore: PotatoSessionStore = createSessionStore({
  async read() {
    const entry = await Keychain.getGenericPassword({ service: SERVICE });
    return entry ? entry.password : null;
  },
  async write(value) {
    const saved = await Keychain.setGenericPassword('potato-meet', value, {
      service: SERVICE,
      accessible: Keychain.ACCESSIBLE.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
    });
    if (!saved) {
      throw new Error('로그인 정보를 안전하게 저장하지 못했어요.');
    }
  },
});

export function memorySessionStore(): PotatoSessionStore {
  let value: string | null = null;
  return createSessionStore({
    async read() {
      return value;
    },
    async write(next) {
      value = next;
    },
  });
}
