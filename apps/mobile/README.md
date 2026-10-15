# 조건부 OK 모바일

운영 구조·서버 계약·배포·백업·서명 관리와 검증 범위는 [프로젝트 README](../../README.md)를 참고하세요.

이 디렉터리에서 `npm ci`, `npm run typecheck`, `npm test -- --runInBand`를 실행합니다. 개발은 `npm start`와 `npm run android`, 운영 APK는 `./scripts/build-release.ps1`입니다. 최초 서명키가 없는 개발 기기에서만 `-CreateSigningKey`를 사용합니다.

앱은 `CONDITIONAL_OK_API_URL`의 실제 HTTPS API만 사용합니다. 기본값은 `https://oranganman.site/v1`입니다. 운영 실패 시 Mock 데이터로 전환하지 않습니다. 테스트 전용 MockRepository는 운영 진입점에서 사용하지 않습니다.
