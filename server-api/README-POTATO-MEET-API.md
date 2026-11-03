# Potato Meet 진입 API (v2)

인증: 기존 계정 세션. `POST /v1/auth/register|login` 응답의 `token`을 `Authorization: Bearer <token>`으로 보낸다.
참가자 ID(`participantId`)는 계정 ID이다. 시간은 모두 Asia/Seoul, 분 단위 정수(0~1440).

## 새 API (이번 단계)
| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/v2/rooms` | 방 생성 (`Idempotency-Key` 필수). 201 신규 / 200 재전송 |
| POST | `/v2/rooms/join` | 초대 코드로 참가 (참가 = 수락) |
| GET | `/v2/rooms/{id}` | 방 요약 (멤버만) |
| GET | `/v2/rooms/{id}/participants` | 참가자·초대·RSVP·가용시간 제출 상태 |
| POST | `/v2/rooms/{id}/invitations` | 방장: 계정 초대 `{accountIds, send}` |
| POST | `/v2/rooms/{id}/invitations/exclude` | 방장: 응답 없는 초대자를 명시적으로 제외 `{accountId, reason}` |
| PUT | `/v2/rooms/{id}/invitations/me` | 초대받은 사람: `{response: ACCEPTED|DECLINED, nickname}` |
| GET | `/v2/rooms` | 홈: 내가 참여 중인 Potato 방 목록(확정 여부·확정 시각 포함) |
| POST | `/v2/rooms/{id}/leave` | 코드로 참가한 멤버의 명시적 나가기(소프트, 이력 보존). 방장·초대 연결 멤버는 409 |
| GET | `/v2/rooms/{id}/latest-run` | 모든 참여자가 같은 최신 Run을 따라가기 위한 조회 |
| GET | `/v2/room-invitations/me` | 내게 온(전송된) 초대 목록 |
| GET | `/v2/people/recent?q=&roomId=&limit=` | 초대 대상 조회: 내가 속한 Potato 방에서 함께한 사람(닉네임·계정 ID). 친구 목록이 아니며 전체 사용자 검색이 아니다. `roomId`를 주면 그 방에서의 상태(`member|pending|declined|excluded|not_sent|null`)를 함께 준다 |
| PUT | `/v2/rooms/{id}/minimum-attendees` | 방장: 최소 참석 인원 (2 이상, 유효 참여자 수 이하) |
| GET/PUT | `/v2/rooms/{id}/availability/me` | 본인 가용시간 조회/제출 |

## 기존 API 재사용
`/v1/auth/*`(계정·세션), `POST /v2/rooms/{id}/agent-runs`(Run 생성), `.../agent-runs/{run}/candidates`,
`.../select|consent|approval|finalize`, `/v2/rooms/{id}/agent-change-proposals`, `/agent-final-result`, `/coordination-rounds`.
친구/검색 API는 서버에 없다(앱의 친구 목록은 로컬 목업) — 초대는 계정 ID 또는 코드 링크로만 가능하다.

## 요청/응답
방 생성 `POST /v2/rooms`
```json
{ "title": "금요 저녁", "activity": "식사", "location": "강남역", "durationMinutes": 120,
  "dates": ["2030-01-10", "2030-01-11"], "minimumAttendeeCount": 2,
  "timeZone": "Asia/Seoul", "nickname": "방장" }
```
앱의 `"2시간"` 같은 소요시간 문자열은 클라이언트가 `durationMinutes`로 변환해 보낸다. 후보 날짜는 명시적으로 보낸다
(방장의 슬롯에서 추론하지 않는다). 응답(공통 방 뷰):
```json
{ "roomId": "…", "code": "AB23CD45", "title": "금요 저녁", "activity": "식사", "location": "강남역",
  "durationMinutes": 120, "dates": ["2030-01-10","2030-01-11"], "excludedDates": [],
  "minimumAttendeeCount": 2, "timeZone": "Asia/Seoul", "hostMemberId": "…", "status": "collecting",
  "coordinationRound": 0, "agentInputRevision": 1, "eligibleParticipantCount": 1,
  "me": { "memberId": "…", "accountId": "…", "role": "organizer" }, "replayed": false }
```
가용시간 `PUT /v2/rooms/{id}/availability/me`
```json
{ "timeZone": "Asia/Seoul", "expectedVersion": 1,
  "timeSlots": [ { "date": "2030-01-10", "startTimeMinutes": 540, "endTimeMinutes": 660 } ] }
```
응답: `{status:"submitted", version, timeZone, timeSlots(병합됨), submittedAt, changed, agentInputRevision}`.
같은 날 겹치거나 맞닿는 구간은 서버가 병합한다. 내용이 같은 재전송은 `changed:false`(새 버전·revision 변화 없음).
빈 목록, 활성 날짜가 아닌 날짜, 지난 날짜, 정수가 아닌 분, `start>=end`, `end>1440`, 200개 초과는 422.

참가자 `GET /v2/rooms/{id}/participants` 항목:
`{participantId, memberId|null, displayName|null, role: organizer|invitee, invitationStatus: not_applicable|not_sent|sent,
participationStatus: pending|accepted|declined, eligibility: active|excluded_by_host,
availability: {status: not_submitted|submitted, version, updatedAt}}`.
각 항목에는 `joinPath`가 있다: `organizer | invitation | code`.
코드로 참가한 사람은 서버 기준 `invitationStatus:"not_sent"` + `participationStatus:"accepted"` + `joinPath:"code"`이다.
앱의 `AppointmentParticipant` 유니온은 `not_sent`를 `pending`에만 허용하므로, 이 조합을 다음 변형으로 추가해야 한다:
`{ role:'invitee', invitationStatus:'not_sent', participationStatus:'accepted' }`.
서버 값은 그대로 두고 앱 타입만 넓히는 것이 Agent 스냅샷(`NOT_SENT`+`ACCEPTED`)과 일치하는 방향이다.
(`joinPath`는 초대 행의 유무로 판단하므로, 방장이 만든 초대 행이 코드 참가로 수락된 경우도 `invitation`으로 보인다.)

## 오류
`{ "detail": { "code": "…" } }` — 401 인증, 403 권한, 404, 409 상태 충돌(`ROUND_ALREADY_FINALIZED`, `NICKNAME_TAKEN`,
`SUBMISSION_VERSION_CONFLICT`, `INVITATION_ALREADY_ACCEPTED`, …), 422 검증.

## 규칙 요약
- 미응답 초대자와 가용시간 미제출은 불참이 아니다. 기존 Agent 정책에 따라 Run은 `WAITING_FOR_INPUT`으로 대기하고,
  초대자가 답하거나 방장이 명시적으로 제외해야 계산이 진행된다.
- 입력이 바뀌는 모든 동작(참가·초대 변경·RSVP·가용시간·최소 인원)은 `agentInputRevision`과 `rooms.revision`을 올리고
  열려 있는 Run을 같은 트랜잭션에서 STALE로 만든다. 확정된 Run과 이력은 건드리지 않는다.
- 현재 조정 회차가 확정되면 이 입력 변경 API들은 409 `ROUND_ALREADY_FINALIZED`이다(`/v2/rooms/{id}/coordination-rounds`로 새 회차).

## MVP(4인) 릴리스 규칙
- 방장의 초대자 제외(`/invitations/exclude`)는 **RSVP 마감이 없는 동안 릴리스에서 비활성**이다(409 `RSVP_DEADLINE_REQUIRED`).
  개발/테스트에서만 `POTATO_ALLOW_UNGATED_EXCLUSION=1`로 켠다. 앱에는 제외 UI가 없다.
- 빈 가용시간은 422 `AVAILABILITY_EMPTY`로 거부한다. 앱은 "가능한 시간이 없다면 제출하지 말고 방장에게 알리거나 모임에서 나가세요.
  응답하지 않아도 불참으로 처리되지는 않아요"라고 안내하며, 사용자의 명시적 행동 없이 RSVP를 바꾸지 않는다.
- 시각 필드(`startsAt`/`endsAt` 등)는 PostgreSQL에서는 UTC 인스턴트(`...Z`), SQLite에서는 서울 벽시계(오프셋 없음)로 내려온다.
  클라이언트는 둘 다 서울 시간으로 변환해 표시해야 한다(앱: `seoulTime.ts`).
- 커밋 시점: `/v1/auth/*`와 Agent Run 엔드포인트는 응답 전송 **전에** 커밋한다(`Depends(db_session, scope="function")`).
  그렇지 않으면 가입 직후 로그인이 401이 되는 경쟁 조건이 PostgreSQL에서 발생한다.
