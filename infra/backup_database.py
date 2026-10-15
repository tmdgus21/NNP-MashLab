"""Private local PostgreSQL backups; optional real restore drill in an isolated DB."""
import argparse
import datetime
import os
from pathlib import Path
import re
import shutil
import subprocess

parser=argparse.ArgumentParser()
parser.add_argument('--verify-restore',action='store_true')
args=parser.parse_args()
root=Path(__file__).resolve().parent.parent
env=dict(line.split('=',1) for line in (root/'.env.database').read_text().splitlines() if '=' in line)
backup_root=Path('/home/linuxuser/conditional-ok-backups/postgres')
backup_root.mkdir(mode=0o700,parents=True,exist_ok=True)
os.chmod(backup_root,0o700)
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
target=backup_root/f'conditional-ok-{stamp}.dump'
base=['docker','exec','mashlab-postgres']
with target.open('xb') as output:
    os.chmod(target,0o600)
    subprocess.run(base+['pg_dump','-U',env['DB_USER'],'-d',env['DB_NAME'],'-Fc','--no-owner','--no-acl'],stdout=output,check=True)
with target.open('rb') as source:
    subprocess.run(['docker','exec','-i','mashlab-postgres','pg_restore','--list'],stdin=source,stdout=subprocess.DEVNULL,check=True)
secret_copy=backup_root/f'conditional-ok-{stamp}.env'
shutil.copyfile(root/'.env.database',secret_copy)
os.chmod(secret_copy,0o600)
if args.verify_restore:
    database='ok_restore_check_'+stamp.lower()
    assert re.fullmatch(r'ok_restore_check_\d{8}t\d{6}z',database)
    subprocess.run(base+['createdb','-U',env['DB_USER'],database],check=True)
    try:
        with target.open('rb') as source:
            subprocess.run(['docker','exec','-i','mashlab-postgres','pg_restore','-U',env['DB_USER'],'-d',database,'--no-owner','--no-acl','--exit-on-error'],stdin=source,check=True)
        subprocess.run(base+['psql','-U',env['DB_USER'],'-d',database,'-v','ON_ERROR_STOP=1','-c','SELECT count(*) AS restored_rooms FROM ok_rooms;'],check=True)
        print('Isolated database restore drill PASS')
    finally:
        subprocess.run(base+['dropdb','-U',env['DB_USER'],database],check=True)
cutoff=datetime.datetime.now(datetime.timezone.utc).timestamp()-14*86400
for old in backup_root.iterdir():
    if old.is_file() and re.fullmatch(r'conditional-ok-\d{8}T\d{6}Z\.(dump|env)',old.name) and old.stat().st_mtime<cutoff:
        old.unlink()
print(f'Backup validated: {target} ({target.stat().st_size} bytes); permissions 0600')
