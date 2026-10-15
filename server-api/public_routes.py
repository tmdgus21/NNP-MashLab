import html
import json
import os
import re
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import select
from database import Room, session

router = APIRouter()


@router.get('/join', response_class=HTMLResponse)
def invitation(code: str):
    code = code.upper()
    if not re.fullmatch(r'[A-Z2-9]{8}', code):
        raise HTTPException(422, '8자리 초대 코드를 확인해 주세요.')
    with session() as db:
        room = db.scalar(select(Room).where(Room.code == code))
        if not room:
            raise HTTPException(404, '존재하지 않는 초대 코드입니다.')
        title = html.escape(room.config['title'])
    return HTMLResponse(f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>조건부 OK 초대</title><style>body{{font:18px system-ui;background:#f3f7f5;color:#173d34;max-width:480px;margin:60px auto;padding:24px}}a{{display:block;padding:18px;margin:20px 0;background:#176e59;color:white;text-align:center;border-radius:14px;text-decoration:none}}code{{font-size:32px;letter-spacing:4px}}</style><h1>{title}</h1><p>조건부 OK 모임에 초대받았어요.</p><code>{code}</code><a href="conditionalok://join?code={code}">앱에서 참여하기</a><a href="/downloads/conditional-ok.apk">Android 앱 다운로드</a><p>설치 후 이 링크를 다시 열거나 앱에 위 코드를 입력해 주세요. 닉네임으로 참여하며 방장 권한은 초대 코드로 부여되지 않습니다.</p></html>''', headers={'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'",'X-Content-Type-Options':'nosniff'})


@router.get('/downloads/conditional-ok.apk')
def download():
    path = Path(os.getenv('APK_PATH','/releases/app-release.apk'))
    if not path.is_file():
        raise HTTPException(404, '앱 배포 파일이 아직 준비되지 않았습니다.')
    return FileResponse(path, media_type='application/vnd.android.package-archive', filename='conditional-ok.apk')


@router.get('/.well-known/assetlinks.json')
def app_links():
    path=Path(os.getenv('ASSETLINKS_PATH','/releases/assetlinks.json'))
    if not path.is_file():
        raise HTTPException(404, '앱 링크 인증이 아직 준비되지 않았습니다.')
    return json.loads(path.read_text())
