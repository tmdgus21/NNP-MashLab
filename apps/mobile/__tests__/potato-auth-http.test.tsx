import React from 'react';
import { TextInput } from 'react-native';
import Renderer, { act } from 'react-test-renderer';
import { LoginScreen } from '../src/potato/screens/LoginScreen';
import { SignUpScreen } from '../src/potato/screens/SignUpScreen';
import {
  AuthServiceUnavailableError,
  unavailableAuthService,
  type PotatoAuthService,
} from '../src/potato/services/authService';
import { createHttpAuthService } from '../src/potato/services/httpAuthService';
import { createPotatoApi } from '../src/potato/services/potatoApi';
import { memorySessionStore } from '../src/potato/services/potatoSession';
import { findButton, hasText } from '../test-utils/potato-test-utils';

// The fetcher below replaces ONLY the network with the server's documented
// /v1/auth responses; the client, session store and screens are the real code.
function serverFetcher(calls: string[]): typeof fetch {
  return (async (url: string, init: { body?: string }) => {
    calls.push(String(url));
    const body = init.body ? JSON.parse(init.body) : {};
    if (String(url).endsWith('/v1/auth/login')) {
      if (body.password !== 'correct-password-1') {
        return new Response(JSON.stringify({ detail: '이메일 또는 비밀번호를 확인하세요.' }), { status: 401 });
      }
      return new Response(JSON.stringify({ accountId: 'acc-1', email: body.email, token: 't'.repeat(48) }), { status: 200 });
    }
    return new Response(JSON.stringify({ accountId: 'acc-2', email: body.email, token: 'u'.repeat(48) }), { status: 201 });
  }) as unknown as typeof fetch;
}

function build() {
  const calls: string[] = [];
  const sessions = memorySessionStore();
  const api = createPotatoApi({
    baseUrl: 'http://server.test',
    token: async () => null,
    fetcher: serverFetcher(calls),
  });
  return { calls, sessions, service: createHttpAuthService(api, sessions) };
}

test('login stores a real session and the nickname chosen at sign-up', async () => {
  const { service, sessions } = build();
  await service.signUp({
    nickname: '민수', email: 'Minsu@Example.test', password: 'correct-password-1', verificationCode: '',
  });
  await service.login({ email: 'minsu@example.test', password: 'correct-password-1', verificationCode: '' });
  expect(await sessions.load()).toMatchObject({ accountId: 'acc-1', nickname: '민수', email: 'minsu@example.test' });
});

test('a wrong password shows the server message and stores nothing', async () => {
  const { service, sessions } = build();
  await expect(
    service.login({ email: 'a@example.test', password: 'wrong-password-12', verificationCode: '' }),
  ).rejects.toThrow('이메일 또는 비밀번호를 확인하세요.');
  expect(await sessions.load()).toBeNull();
});

test('a short password is refused before any request is made', async () => {
  const { service, calls } = build();
  await expect(
    service.signUp({ nickname: 'x', email: 'a@example.test', password: 'short', verificationCode: '' }),
  ).rejects.toThrow('12자');
  expect(calls).toEqual([]);
});

test('requesting a verification code fails honestly and never reports a send', async () => {
  const { service } = build();
  await expect(service.sendVerificationCode('a@example.test', 'login')).rejects.toBeInstanceOf(
    AuthServiceUnavailableError,
  );
  await expect(service.sendVerificationCode('a@example.test', 'login')).rejects.toThrow('발송되지 않았습니다');
});

async function render(element: React.ReactElement) {
  let tree!: Renderer.ReactTestRenderer;
  await act(async () => {
    tree = Renderer.create(element);
  });
  return tree;
}

function type(tree: Renderer.ReactTestRenderer, label: string, value: string) {
  const input = tree.root.findAllByType(TextInput).find(item => item.props.accessibilityLabel === label);
  if (!input) {
    throw new Error(`no input ${label}`);
  }
  act(() => input.props.onChangeText(value));
}

test('login screen without email verification hides the code field and logs in without one', async () => {
  const login = jest.fn(async () => undefined);
  const service: PotatoAuthService = { ...unavailableAuthService, emailVerification: 'unsupported', login };
  const onLoginSuccess = jest.fn();
  const tree = await render(<LoginScreen onSignUpPress={jest.fn()} onLoginSuccess={onLoginSuccess} service={service} />);
  expect(hasText(tree, '인증코드 보내기')).toBe(false);
  expect(hasText(tree, '이메일 인증은 아직 지원하지 않아요. 비밀번호로만 확인해요.')).toBe(true);
  type(tree, '아이디 입력', 'a@example.test');
  type(tree, '비밀번호 입력', 'correct-password-1');
  await act(async () => {
    findButton(tree, '로그인하기').props.onPress();
  });
  expect(login).toHaveBeenCalledWith({ email: 'a@example.test', password: 'correct-password-1', verificationCode: '' });
  expect(onLoginSuccess).toHaveBeenCalled();
});

test('the default service still demands a verification code and does not pretend to log in', async () => {
  const login = jest.fn();
  const tree = await render(
    <LoginScreen onSignUpPress={jest.fn()} service={{ ...unavailableAuthService, login }} />,
  );
  expect(hasText(tree, '인증코드 보내기')).toBe(true);
  type(tree, '아이디 입력', 'a@example.test');
  type(tree, '비밀번호 입력', 'correct-password-1');
  await act(async () => {
    findButton(tree, '로그인하기').props.onPress();
  });
  expect(login).not.toHaveBeenCalled();
  expect(hasText(tree, '이메일 인증코드를 입력해 주세요.')).toBe(true);
});

test('sign-up screen without email verification registers and moves on to login', async () => {
  const signUp = jest.fn(async () => undefined);
  const onLoginPress = jest.fn();
  const service: PotatoAuthService = { ...unavailableAuthService, emailVerification: 'unsupported', signUp };
  const tree = await render(<SignUpScreen onLoginPress={onLoginPress} service={service} />);
  expect(hasText(tree, '인증코드 보내기')).toBe(false);
  type(tree, '사용할 닉네임', '민수');
  type(tree, '아이디 (이메일 형태)', 'a@example.test');
  type(tree, '비밀번호', 'correct-password-1');
  type(tree, '비밀번호 확인', 'correct-password-1');
  await act(async () => {
    findButton(tree, '회원가입 완료').props.onPress();
  });
  expect(signUp).toHaveBeenCalledWith(expect.objectContaining({ nickname: '민수', email: 'a@example.test' }));
  expect(onLoginPress).toHaveBeenCalled();
});
