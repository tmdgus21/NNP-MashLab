export interface LoginCredentials {
  email: string;
  password: string;
  verificationCode: string;
}

export interface SignUpCredentials {
  nickname: string;
  email: string;
  password: string;
  verificationCode: string;
}

export type VerificationPurpose = 'login' | 'signup';

export interface PotatoAuthService {
  sendVerificationCode(
    email: string,
    purpose: VerificationPurpose,
  ): Promise<void>;
  login(credentials: LoginCredentials): Promise<void>;
  signUp(credentials: SignUpCredentials): Promise<void>;
}

export class AuthServiceUnavailableError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'AuthServiceUnavailableError';
  }
}

export const unavailableAuthService: PotatoAuthService = {
  async sendVerificationCode(_email, purpose) {
    const action = purpose === 'login' ? '로그인' : '회원가입';
    throw new AuthServiceUnavailableError(
      `${action} 이메일 인증 API가 아직 연결되지 않았습니다. 인증코드는 발송되지 않았습니다.`,
    );
  },
  async login() {
    throw new AuthServiceUnavailableError(
      '로그인 API가 아직 연결되지 않아 로그인을 완료할 수 없습니다.',
    );
  },
  async signUp() {
    throw new AuthServiceUnavailableError(
      '회원가입 API가 아직 연결되지 않아 계정을 생성할 수 없습니다.',
    );
  },
};

export function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : '요청 중 알 수 없는 오류가 발생했습니다.';
}
