const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const key = path.resolve(__dirname, '../android/app/debug.keystore');
if (!fs.existsSync(key)) {
  const binary = process.platform === 'win32' ? 'keytool.exe' : 'keytool';
  const tool = process.env.JAVA_HOME ? path.join(process.env.JAVA_HOME, 'bin', binary) : binary;
  const result = spawnSync(tool, ['-genkeypair', '-storetype', 'JKS', '-keystore', key, '-storepass', 'android', '-alias', 'androiddebugkey', '-keypass', 'android', '-keyalg', 'RSA', '-keysize', '2048', '-validity', '10000', '-dname', 'CN=Android Debug,O=Android,C=US'], {stdio: 'inherit'});
  if (result.error) throw result.error;
  process.exit(result.status ?? 1);
}
