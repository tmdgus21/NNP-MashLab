# GUEST-only 방장 삭제 문제 (해결안 · 구현 전)

Q13: 기존 조건부 OK 방은 조회 + **방장만** 삭제. Potato Meet는 계정 로그인(`account_type=USER`) 전제를 강화하는데, 기존 생성 경로는 GUEST 방장을 만든다.

## 현상

- `workflow.py` 생성: `resolve_user_account(...) or ensure_guest_account(...)` → 로그인 없으면 `accounts.account_type='GUEST'`, 그 계정이 OWNER `room_members.account_id`.
- 삭제는 멤버 Bearer(`room_members.token_hash`)로 `host=True` 검사. **멤버 토큰이 있으면** GUEST OWNER도 현재 API로 삭제 가능.
- Potato Meet 정책(Q13 open-questions): 삭제는 `room_role=OWNER` + **현재 계정 인증 가능**할 때만 UI/API 노출. 순수 GUEST OWNER는 로그인 USER 세션과 연결되지 않음 → **USER 전용 삭제 API만 남기면 방장 삭제 불가**, 모임이 soft-delete 없이 잔류.

## 위험

| 시나리오 | 결과 |
|---|---|
| GUEST OWNER만 있는 Q13 방 | USER 로그인 삭제 경로만 허용 시 삭제 불가 |
| 멤버 토큰 분실·앱 재설치 | GUEST 이메일(`@local.invalid`)로는 재로그인 불가 |
| 관리자 강제 삭제만 허용 | 제품 정책(방장만)과 불일치, 운영 부하 |

## 권장 해결안 (택1, 구현은 별도 승인)

1. **레거시 삭제 예외 (권장 단기)**  
   Q13 식별(`schedule_collections` 없음)인 방에 한해, 기존과 같이 **OWNER 멤버 Bearer**로 soft-delete 허용. Potato Meet 신규 방(`schedule_collections` 있음)은 USER 계정 OWNER만 삭제.  
   - 장점: 기존 앱 계약 유지, 스키마 변경 없음.  
   - 단점: Q13 구간에 이중 인증 규칙.

2. **소유권 클레임**  
   동일 닉네임/초대코드 + 일회용 클레임 코드(방 생성 시 발급·로컬 저장)로 USER가 OWNER `account_id`를 승계한 뒤 삭제.  
   - 장점: 이후 USER 단일 경로.  
   - 단점: UX·클레임 저장·보안 설계 필요.

3. **관리자/운영 도구만**  
   GUEST OWNER 방은 사용자 삭제 불가, `admin` soft-delete.  
   - 장점: 구현 단순.  
   - 단점: Q13 "방장만 삭제" 위반에 가깝고 운영 의존.

## 이번 2차 범위

- DB 모델/0005에는 **스키마 변경 없음** (방장 삭제는 서비스 규칙).
- 컷오버 전 API 설계 시 **안 1**을 기본안으로 문서화하고, 앱에 Q13 배지 + 멤버토큰 삭제 유지 여부를 승인받는다.
