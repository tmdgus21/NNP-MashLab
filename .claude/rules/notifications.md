---
paths:
  - "server-api/schedule/notifications.py"
  - "server-api/schedule/service.py"
  - "apps/android/app/src/main/java/**/push/**"
  - "apps/android/app/src/main/java/**/notificationsettings/**"
  - "apps/android/app/src/main/AndroidManifest.xml"
---
# 푸시 알림 규칙 (R9)

- 종류는 START(시작)·REMIND(임박)·EXTEND(연장) 3개뿐. `docs/potato-meet/coordination-algorithm.md` 9절 표에 없는 알림을 만들지 않는다.
- 발송 전 `notification_settings` 확인, 꺼진 종류는 SKIPPED로 기록만.
- **DB 커밋 이후에만** 발송. 발송 실패가 조율·마감·확정 트랜잭션을 되돌리면 안 된다.
- 중복 방지는 `notification_log` UNIQUE로. 주기 작업 재실행·재시도에도 한 사람에게 한 번.
- REMIND는 미완료자(미입력·미투표)에게만, 이미 마감됐으면 보내지 않는다.
- 본문·로그에 이메일·토큰 원문 금지. 토큰은 끝 6자리만 로그.
- FCM 키: 서버는 `FCM_CREDENTIALS_FILE` 경로로만 읽는다. 키 내용·`google-services.json`을 만들거나 출력하지 않는다. 키가 없으면 알림만 끄고 나머지는 정상.
- 앱: Android 13+ `POST_NOTIFICATIONS` 런타임 권한, 처음 모임 생성/참여 때 요청. 토큰 갱신(`onNewToken`) 시 재등록, 로그아웃 시 해제.
- 테스트는 가짜 발송기. 실제 FCM 호출 테스트를 만들지 않는다.
