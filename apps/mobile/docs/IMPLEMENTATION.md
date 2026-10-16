# 구현 및 검증 계획

- RN 0.87.1 Community CLI 기본 앱을 API35 AVD에서 먼저 실행한다.
- 모임 생성/코드 참가 후 현황, 내 조건, 담당표를 탐색한다.
- 시간은 날짜별 30분 슬롯을 사용하며 JSON에서는 로컬 날짜 + 분 단위 반열린 구간 [start, end)와 IANA 시간대를 전송한다.
- 서버가 담당표, 충돌, 확인사항과 계산 상태를 반환한다. 자연어 해석 결과는 사용자가 확인할 조건 초안이며 최종 배정 권한이 없다.
- 조건 수정은 expectedRevision을 포함한 미리보기/적용으로 분리한다. 적용 시 회차 증가, 기존 동의 무효화, 재계산 및 재동의를 요구한다.
- 합의는 특정 회차에 귀속된다. 모든 참가자의 해당 회차 동의가 있고 배정가능 상태일 때만 방장이 확정한다.
- Mock 시나리오: 배정가능, 시간충돌, 배정불가, 조건변경/재합의, 최종확정, 빈 상태, 네트워크 오류.
- 검증: 시간 변환/드래그 경계/중복 시간 병합, 서버 계약, 회차 및 권한, 불가능 배정, HTTP 오류, 실제 Android 제스처/탭/합의 흐름.

## 참고 공식 문서
- https://reactnative.dev/blog/2026/08/11/react-native-0.87
- https://github.com/react-native-community/template
- https://developer.android.com/tools/agents/android-cli
- https://reactnavigation.org/docs/getting-started/
- https://docs.swmansion.com/react-native-gesture-handler/docs/fundamentals/getting-started/
