# 재부팅 후 실제 Qwen 검증

모든 요청 meeting_date=2026-10-17. 배열 순서와 확인 문구를 포함한 전체 JSON 정확 일치로 판정.

| # | 입력 | 기대 JSON | 실제 JSON | 결과 | 초 |
|---|---|---|---|---|---|
| 1 | 오후 2시부터 오후 4시까지 가능해요. | `{"availability":[{"date":"2026-10-17","start":"14:00","end":"16:00","kind":"available","strength":"required"}],"role_preferences":[],"role_unavailable":[],"companion_requirement":[],"ambiguities":[]}` | `{"availability":[{"date":"2026-10-17","start":"14:00","end":"16:00","kind":"available","strength":"required"}],"role_preferences":[],"role_unavailable":[],"companion_requirement":[],"ambiguities":[]}` | PASS | 27.078 |
| 2 | 14:00~16:00에는 참여가 불가능해요. | `{"availability":[{"date":"2026-10-17","start":"14:00","end":"16:00","kind":"unavailable","strength":"required"}],"role_preferences":[],"role_unavailable":[],"companion_requirement":[],"ambiguities":[]}` | `{"availability":[{"date":"2026-10-17","start":"14:00","end":"16:00","kind":"unavailable","strength":"required"}],"role_preferences":[],"role_unavailable":[],"companion_requirement":[],"ambiguities":[]}` | PASS | 10.391 |
| 3 | 기록 역할을 선호해요. 촬영 역할은 못 해요. | `{"availability":[],"role_preferences":[{"role":"기록","strength":"preferred"}],"role_unavailable":["촬영"],"companion_requirement":[],"ambiguities":[]}` | `{"availability":[],"role_preferences":[{"role":"기록","strength":"preferred"}],"role_unavailable":["촬영"],"companion_requirement":[],"ambiguities":[]}` | PASS | 7.32 |
| 4 | 저는 반드시 진행 역할을 맡아야 해요. | `{"availability":[],"role_preferences":[{"role":"진행","strength":"required"}],"role_unavailable":[],"companion_requirement":[],"ambiguities":[]}` | `{"availability":[],"role_preferences":[{"role":"진행","strength":"required"}],"role_unavailable":[],"companion_requirement":[],"ambiguities":[]}` | PASS | 6.48 |
| 5 | 민지와 반드시 함께 참여해야 해요. | `{"availability":[],"role_preferences":[],"role_unavailable":[],"companion_requirement":[{"person":"민지","relation":"together","strength":"required"}],"ambiguities":[]}` | `{"availability":[],"role_preferences":[],"role_unavailable":[],"companion_requirement":[{"person":"민지","relation":"together","strength":"required"}],"ambiguities":[]}` | PASS | 7.071 |
| 6 | 민지와 가능하면 함께 참여하고 싶어요. | `{"availability":[],"role_preferences":[],"role_unavailable":[],"companion_requirement":[{"person":"민지","relation":"together","strength":"preferred"}],"ambiguities":[]}` | `{"availability":[],"role_preferences":[],"role_unavailable":[],"companion_requirement":[{"person":"민지","relation":"together","strength":"preferred"}],"ambiguities":[]}` | PASS | 6.859 |
| 7 | 저녁쯤 가능해요. | `{"availability":[],"role_preferences":[],"role_unavailable":[],"companion_requirement":[],"ambiguities":["저녁의 정확한 시작과 종료 시간을 알려주세요."]}` | `{"availability":[],"role_preferences":[],"role_unavailable":[],"companion_requirement":[],"ambiguities":["저녁의 정확한 시작과 종료 시간을 알려주세요."]}` | PASS | 6.367 |
| 8 | 14:00~16:00 시간이 좋아요. | `{"availability":[{"date":"2026-10-17","start":"14:00","end":"16:00","kind":"available","strength":"preferred"}],"role_preferences":[],"role_unavailable":[],"companion_requirement":[],"ambiguities":[]}` | `{"availability":[{"date":"2026-10-17","start":"14:00","end":"16:00","kind":"available","strength":"preferred"}],"role_preferences":[],"role_unavailable":[],"companion_requirement":[],"ambiguities":[]}` | PASS | 10.432 |
| 9 | 3시쯤 가능해요. | `{"availability":[],"role_preferences":[],"role_unavailable":[],"companion_requirement":[],"ambiguities":["3시쯤의 정확한 시작과 종료 시간을 알려주세요."]}` | `{"availability":[],"role_preferences":[],"role_unavailable":[],"companion_requirement":[],"ambiguities":["3시쯤의 정확한 시작과 종료 시간을 알려주세요."]}` | PASS | 6.48 |
| 10 | 09:00~10:00, 15:00~16:00 두 구간에 참여 가능해요. | `{"availability":[{"date":"2026-10-17","start":"09:00","end":"10:00","kind":"available","strength":"required"},{"date":"2026-10-17","start":"15:00","end":"16:00","kind":"available","strength":"required"}],"role_preferences":[],"role_unavailable":[],"companion_requirement":[],"ambiguities":[]}` | `{"availability":[{"date":"2026-10-17","start":"09:00","end":"10:00","kind":"available","strength":"required"},{"date":"2026-10-17","start":"15:00","end":"16:00","kind":"available","strength":"required"}],"role_preferences":[],"role_unavailable":[],"companion_requirement":[],"ambiguities":[]}` | PASS | 16.549 |

측정 요약:
```json
{
  "boot_id": "eaa24c2b-c22a-4d06-ba13-08ea5b691e2d",
  "model_pid": 972,
  "passed": 10,
  "total": 10,
  "mean_seconds": 10.503,
  "median_seconds": 7.196,
  "min_seconds": 6.367,
  "max_seconds": 27.078,
  "first_request_seconds": 27.078,
  "warm_mean_seconds": 8.661,
  "memory_before": {
    "VmHWM_KiB": 2767296,
    "VmRSS_KiB": 2767296,
    "VmSwap_KiB": 0
  },
  "memory_after": {
    "VmHWM_KiB": 2826796,
    "VmRSS_KiB": 2826796,
    "VmSwap_KiB": 0
  },
  "sampled_peak_RSS_KiB": 2826796,
  "sampled_mean_RSS_KiB": 2824969,
  "memory_samples": 420
}
```

RAM: /proc/<pid>/status의 VmRSS(실제 상주 메모리)를 250ms 간격으로 측정. VmHWM은 프로세스 생애 최대 RSS. 응답시간은 서버에서 공개 HTTPS API를 순차 호출한 종단 간 시간이며, 동시 부하 측정은 아님.
