import argparse, getpass, re
from sqlalchemy import select
from database import session
from admin.models import Account
from admin.security import PASSWORDS, log, revoke

def main():
    parser=argparse.ArgumentParser(description='Operator-only administrator provisioning. No public signup.')
    parser.add_argument('command',choices=['create','unfreeze'])
    parser.add_argument('email')
    parser.add_argument('--role',choices=['SUPER_ADMIN','OPERATOR','VIEWER'],default='VIEWER')
    parser.add_argument('--reason',required=True)
    args=parser.parse_args()
    email=args.email.strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(args.reason)<5: parser.error('Valid email and reason required')
    with session() as db,db.begin():
        account=db.scalar(select(Account).where(Account.email==email).with_for_update())
        if args.command=='create':
            if account: parser.error('Account already exists')
            password=getpass.getpass('Password (at least 12 characters): ')
            if len(password)<12 or password!=getpass.getpass('Confirm password: '): parser.error('Password confirmation failed')
            account=Account(email=email,password_hash=PASSWORDS.hash(password),role=args.role)
            db.add(account);db.flush()
        else:
            if not account: parser.error('Account does not exist')
            account.frozen=False;account.revision+=1;revoke(db,account.id)
        log(db,'server-operator','account.'+args.command,account.id,args.reason)
    print('Administrator updated; no password or OTP printed.')
if __name__=='__main__': main()
