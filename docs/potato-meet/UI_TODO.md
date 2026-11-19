# Potato Meet UI 후속 작업 (배포와 분리)

> 작성: 2026-11-19 · 브랜치 `feature/schedule-coordination`  
> 원칙: **기존 face UI·범위 밖 화면 유지**. 이 문서는 미완성 항목만 추적한다.  
> 화면↔API 매핑 요약은 `apps/android/UI_MAPPING.md` 참고.

## 우선순위 범례

| 등급 | 의미 |
|---|---|
| P0 | 핵심 플로우(입력·투표·확정) 품질에 직접 영향. 배포 후 빠른 후속 권장 |
| P1 | PRD 명시·운영 편의. 다음 스프린트 |
| P2 | 범위 밖이거나 선택적. 유지·보류 |

## 현재 구현 상태 요약

| 영역 | 상태 | 비고 |
|---|---|---|
| P1 로그인·회원가입 | 완료 | `/v1/auth` |
| P2 목록·초대코드 참여 | 완료(최소) | face Home 유지 |
| P3 모임 생성 | 완료(최소) | 닉네임·날짜 필드 추가. category/duration/location 미전송 |
| P4 상세·공유·삭제 | 부분 | Home 다이얼로그 수준. 전용 상세 화면 없음 |
| P5 30분 불가 격자 | **미완** | face 시간대 추가 UX로 우회 연동 |
| P6 후보·AI 요약 | 부분 | AiRecommendationScreen + API. slotCounts UI 없음 |
| P7 복수 투표 | 부분 | 후보 카드 다중 선택 |
| P8 확정 결과 | 완료(최소) | ResultScreen 신규(톤만 face 맞춤) |
| P9 알림 설정 | **미착수** | |
| SSE | 완료(앱) | 화면 STARTED 생명주기 세분화는 후속 |
| FCM | **미착수** | |
| 딥링크 `/join` | Manifest만 | 자동 참여 플로우 미완 |
| Friends / MyPage | 범위 밖 · 유지 | 서버 연동 없음 |

---

## P0 — 배포 후 빠른 후속

### 1. P5 24시간 × 30분 불가능 시간 격자
- **PRD**: 기본 전부 가능, 안 되는 칸만 표시 → 완료
- **현재**: Create step3이 “가능 시간대 추가” face UX. 제출 시 해당 구간만 `available`로 전송(빈 목록이면 서버가 전체 가능 처리)
- **할 일**: Etta 스타일 한 화면 격자, 30분 슬롯 토글(불가), 날짜 범위·마감·유예 표시. **face 레이아웃 톤 유지·전면 리디자인 금지**
- **API**: `GET …/collection`, `PUT …/collections/{id}/response`

### 2. 입력 중 `slotCounts` 시각화
- **PRD**: 칸별 가능 **인원 수**만(멤버 식별 금지)
- **현재**: DTO `CollectionResponse.slotCounts` 파싱만. UI 미표시
- **할 일**: 격자에 count 오버레이/색 단계. nearMisses 힌트(재조정) 최소 표시

### 3. P4 모임 상세 전용 흐름 보강
- **현재**: Home 카드 다이얼로그 + 상태별 화면 점프
- **할 일**: 멤버 목록·입력 ✓·초대 링크·상태·“내 시간 입력/고치기”를 face 톤으로 한 화면에 모으기(새 디자인 시스템 도입 금지)

---

## P1 — 다음 스프린트

### 4. App Link / 딥링크 자동 참여
- **현재**: `AndroidManifest`에 `https://oranganman.site/join` pathPrefix. 코드에서 `code` 파싱 → 로그인 → `POST /meetings/join` 미연결
- **할 일**: MainActivity intent 처리, 미로그인 시 로그인 후 재개, 참여 불가(409) 안내

### 5. FCM 푸시 (R9)
- **현재**: 미구현. `google-services.json`은 사용자 배치
- **할 일**: 토큰 `PUT/DELETE /v1/devices/me`, 알림 탭 → `potatomeet://meetings/{id}`
- **의존**: 서버 FCM 키·승인된 compose 마운트(별도 승인)

### 6. P9 알림 설정 시트
- **PRD**: P2 상단 🔔 하단 시트 (`start`/`remind`/`extend`)
- **현재**: UI·API 클라이언트 없음
- **할 일**: face Home에 최소 시트 추가(전체 리디자인 금지)

### 7. SSE 생명주기·revision 가드
- **현재**: MeetingViewModel이 활성 모임에 SSE 연결, 이벤트 시 REST 재조회
- **할 일**: `repeatOnLifecycle(STARTED)`로 화면 가시 시에만 연결, 응답 `revision`이 낮으면 무시

### 8. 가용시간 제출 UX와 PRD 정합
- face “가능 슬롯 추가” vs PRD “불가 칸 표시” 차이 문서화·격자 전환 시 마이그레이션 가이드

---

## P2 — 유지·보류

| 항목 | 상태 | 조치 |
|---|---|---|
| FriendsScreen | 범위 밖 | **삭제·재디자인 금지**, 그대로 유지 |
| MyPageScreen 닉네임 | 로컬만 | 서버 저장 금지(`accounts.nickname` 추가 금지) |
| Create step1 category/duration/location | 참고용 UI | 서버 미전송 유지 또는 라벨만 “참고” |
| Create step2 친구 체크리스트 | 더미 | 초대코드 카드와 병행 유지 |
| 구글 인증 UI (로그인/회원가입) | 장식 | 연동 보류 |
| 관리자 Friends 분기 | face 잔재 | 사용 안 함 |

---

## 명시적 비목표 (이번·다음 UI 작업 공통)

- face 전체를 Material/새 테마로 갈아엎기
- Friends/MyPage를 PRD 밖 기능으로 확장
- 운영 배포·Alembic·Qwen 설정 변경을 UI 작업에 묶기

## 완료 정의 (후속 PR 단위 제안)

1. **P5 격자 PR**: 불가 토글 + slotCounts + collection 재조회, face 톤 유지, 단위/수동 스모크
2. **딥링크 PR**: `/join?code=` → join API
3. **알림 PR**: FCM + P9 시트 (인프라 승인 후)
