import {invitationCode} from '../src/domain/invitation';
test('only trusted invitation links and valid codes are accepted', () => {
  expect(invitationCode('https://oranganman.site/join?code=ABCDEFG2','https://oranganman.site')).toBe('ABCDEFG2');
  expect(invitationCode('conditionalok://join?code=abcdefgh','https://oranganman.site')).toBe('ABCDEFGH');
  for (const url of ['https://evil.test/join?code=ABCDEFG2','https://oranganman.site.evil.test/join?code=ABCDEFG2','https://oranganman.site/join?code=123','conditionalok://join?code=ABCDEFG2&code=ABCDEFG3','conditionalok://join/evil?code=ABCDEFG2','conditionalok://join?code=%broken','not a url']) {
    expect(invitationCode(url,'https://oranganman.site')).toBeNull();
  }
});
