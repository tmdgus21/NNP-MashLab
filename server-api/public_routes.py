import html
import json
import os
import re
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import select
from database import Room, session

router = APIRouter()

_APK_PATH = Path(os.getenv("APK_PATH", "/releases/app-release.apk"))
_ASSETLINKS_PATH = Path(os.getenv("ASSETLINKS_PATH", "/releases/assetlinks.json"))
_INVITE_HOST = "oranganman.site"
_APK_DOWNLOAD_URL = f"https://{_INVITE_HOST}/downloads/potato-meet.apk"
_POTATO_MEET_PACKAGE = "com.potatomeet.app"


def _apk_available() -> bool:
    return _APK_PATH.is_file()


def _invite_title(room: Room) -> str:
    """Potato Meet stores title on rooms.title; legacy may keep it in meeting_settings."""
    settings = room.config if isinstance(room.config, dict) else {}
    column = (room.title or "").strip()
    nested = str(settings.get("title") or "").strip()
    return column or nested or "Potato Meet 모임"


def _open_app_intent_href(code: str) -> str:
    """Android intent:// that opens /join?code=… in Potato Meet, else APK download."""
    fallback = quote(_APK_DOWNLOAD_URL, safe="")
    return (
        f"intent://{_INVITE_HOST}/join?code={code}#Intent;"
        f"scheme=https;package={_POTATO_MEET_PACKAGE};"
        f"S.browser_fallback_url={fallback};end"
    )


@router.get("/join", response_class=HTMLResponse)
def invitation(code: str):
    code = code.upper()
    if not re.fullmatch(r"[A-Z2-9]{8}", code):
        raise HTTPException(422, "8자리 초대 코드를 확인해 주세요.")
    with session() as db:
        room = db.scalar(select(Room).where(Room.code == code))
        if not room:
            raise HTTPException(404, "존재하지 않는 초대 코드입니다.")
        title = html.escape(_invite_title(room))
    open_href = html.escape(_open_app_intent_href(code))
    apk_block = ""
    if _apk_available():
        apk_block = (
            '<a href="/downloads/potato-meet.apk">Android 앱 다운로드</a>'
            "<p>설치 후 이 링크를 다시 열거나, 앱의 「초대 코드로 참여」에 위 코드를 입력해 주세요.</p>"
        )
    else:
        apk_block = (
            "<p>앱이 없다면 위 초대 코드를 복사한 뒤, Potato Meet 앱의 「초대 코드로 참여」에서 입력해 주세요.</p>"
        )
    return HTMLResponse(
        f"""<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Potato Meet 초대</title>
<style>
body{{font:18px system-ui;background:#fffaf0;color:#3c1e1e;max-width:480px;margin:60px auto;padding:24px}}
a{{display:block;padding:18px;margin:20px 0;background:#ffb300;color:#3c1e1e;text-align:center;border-radius:14px;text-decoration:none;font-weight:700}}
code{{display:block;font-size:32px;letter-spacing:4px;margin:16px 0;color:#e65100;font-weight:700}}
.hint{{font-size:14px;color:#6d4c41;line-height:1.5}}
</style>
<h1>{title}</h1>
<p>Potato Meet 모임에 초대받았어요.</p>
<p class="hint">초대 코드</p>
<code>{code}</code>
<p class="hint">앱이 설치되어 있다면 아래 버튼으로 앱을 열어 초대를 확인하세요. 참여는 앱에서 직접 확인해 주세요.</p>
<a href="{open_href}">앱에서 초대 열기</a>
{apk_block}
</html>""",
        headers={
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/downloads/potato-meet.apk")
def download_potato_meet():
    if not _apk_available():
        raise HTTPException(404, "앱 배포 파일이 아직 준비되지 않았습니다.")
    return FileResponse(
        _APK_PATH,
        media_type="application/vnd.android.package-archive",
        filename="potato-meet.apk",
    )


@router.get("/.well-known/assetlinks.json")
def app_links():
    if not _ASSETLINKS_PATH.is_file():
        raise HTTPException(404, "앱 링크 인증이 아직 준비되지 않았습니다.")
    return json.loads(_ASSETLINKS_PATH.read_text())
