import {
  AuthServiceUnavailableError,
  type PotatoAuthService,
} from './authService';
import type { PotatoApi } from './potatoApi';
import type { PotatoSessionStore } from './potatoSession';

const MIN_PASSWORD_LENGTH = 12; // the server's own rule (POST /v1/auth/register)

/**
 * Real account login against /v1/auth. The server has NO email verification, so
 * this service says so (emailVerification: 'unsupported'): the screens hide the
 * code field and requesting a code fails honestly instead of pretending to send one.
 */
export function createHttpAuthService(
  api: PotatoApi,
  sessions: PotatoSessionStore,
): PotatoAuthService {
  return {
    emailVerification: 'unsupported',
    async sendVerificationCode() {
      throw new AuthServiceUnavailableError(
        '이메일 인증코드는 아직 지원되지 않아요. 인증코드는 발송되지 않았습니다.',
      );
    },
    async login({ email, password }) {
      const result = await api.auth.login(email.trim(), password);
      const remembered = await sessions.nicknameFor(result.email);
      await sessions.save({
        token: result.token,
        accountId: result.accountId,
        email: result.email,
        nickname: remembered ?? result.email.split('@')[0],
      });
    },
    async signUp({ nickname, email, password }) {
      if (password.length < MIN_PASSWORD_LENGTH) {
        throw new Error(`비밀번호는 ${MIN_PASSWORD_LENGTH}자 이상이어야 해요.`);
      }
      await api.auth.register(email.trim(), password);
      await sessions.rememberNickname(email, nickname);
    },
  };
}
