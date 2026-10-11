import {invitationCode} from '../src/domain/invitation';
test('only trusted invitation links and valid codes are accepted', () => {
  expect(invitationCode('https://oranganman.site/join?code=ABCDEFG2','https://oranganman.site')).toBe('ABCDEFG2');
  expect(invitationCode('conditionalok://join?code=abcdefgh','https://oranganman.site')).toBe('ABCDEFGH');
  for (const url of ['https://evil.test/join?code=ABCDEFG2','https://oranganman.site.evil.test/join?code=ABCDEFG2','https://oranganman.site/join?code=123','not a url']) {
    expect(invitationCode(url,'https://oranganman.site')).toBeNull();
  }
});
