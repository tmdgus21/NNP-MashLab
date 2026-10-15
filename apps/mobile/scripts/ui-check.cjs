// Android UI verification helper. Reads actual UI hierarchy before every tap.
const {execFileSync} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const adb = path.join(process.env.ANDROID_HOME, 'platform-tools', process.platform === 'win32' ? 'adb.exe' : 'adb');
const out = path.resolve(__dirname, '../.artifacts');
const serial = process.env.ANDROID_SERIAL || 'emulator-5554';
const run = (...args) => execFileSync(adb, ['-s', serial, ...args], {encoding: 'utf8', timeout: 30000});
const decode = s => s.replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&#10;/g, '\n').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
function dump() {
  run('shell', 'uiautomator', 'dump', '/sdcard/conditionalok-ui.xml');
  const xml = run('shell', 'cat', '/sdcard/conditionalok-ui.xml');
  fs.writeFileSync(path.join(out, 'ui-current.xml'), xml);
  return [...xml.matchAll(/<node\s+([^>]+)>?/g)].map(m => {
    const attributes = Object.fromEntries([...m[1].matchAll(/([\w-]+)="([^"]*)"/g)].map(a => [a[1], decode(a[2])]));
    attributes.rect = (attributes.bounds?.match(/\d+/g) || []).map(Number);
    return attributes;
  });
}
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
async function main() {
  const [command, value] = process.argv.slice(2);
  let nodes = dump();
  if (command === 'tap' || command === 'find-tap') {
    let target;
    for (let attempt = 0; attempt < (command === 'find-tap' ? 10 : 1); attempt++) {
      target = nodes.find(n => (n.text === value || n['content-desc'] === value) && n.rect[3] > n.rect[1] && n.rect[1] >= 180 && n.rect[3] < 2280);
      if (target) break;
      run('shell', 'input', 'swipe', '980', '1920', '980', '600', '500'); await wait(800); nodes = dump();
    }
    if (!target) throw new Error(`Visible control not found: ${value}`);
    const [x1,y1,x2,y2] = target.rect;
    run('shell', 'input', 'tap', String(Math.round((x1+x2)/2)), String(Math.round((y1+y2)/2))); await wait(1600); nodes = dump();
  }
  if (command === 'capture') {
    run('shell', 'screencap', '-p', '/sdcard/conditionalok-screen.png');
    run('pull', '/sdcard/conditionalok-screen.png', path.join(out, `${value}.png`));
    fs.copyFileSync(path.join(out, 'ui-current.xml'), path.join(out, `${value}.xml`));
  }
  if (command === 'assert' && !nodes.some(n => `${n.text} ${n['content-desc']}`.includes(value))) throw new Error(`UI assertion failed: ${value}`);
  console.log(nodes.filter(n => n.text || n['content-desc']).map(n => `${n.text || n['content-desc']} ${n.bounds}`).join('\n'));
}
main().catch(e => {console.error(e.message); process.exitCode = 1;});
