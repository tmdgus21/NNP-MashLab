# Production verification — 2026-10-14

- Local signed Release APK (version 1.0.0 / code 2) built and signature verified; SHA-256 certificate E8:55:71:68:9A:3D:10:4A:8E:29:E0:AE:68:8F:84:7F:6D:7D:B1:21:6B:38:21:68:DD:41:04:EA:9B:1A:87:D6.
- Installed and launched on ConditionalOK_API35. Previous debug app data backed up locally before replacing the incompatible development signature.
- Latest mobile typecheck and 31 Jest tests pass. GitHub Actions test job also passes mobile and 22 server tests.
- Actual device invitation parsing regression fixed; rebuilt signed APK installed successfully. Cold-start invitation opened the join form with the exact eight-character code. Actual join request returned the current server 404 and stayed on the form without mock fallback.
- IMPORTANT: Current ssh conditional-ok host no longer has the previously deployed workflow API, Qwen model/binary/systemd units, or backup directory. Current public OpenAPI only exposes GET / and POST /rooms. No listener on 8080.
- October 11 live-service report is historical evidence, not proof of the current server state. Current live end-to-end verification is blocked pending server restoration/target clarification.
- No server reconstruction performed on October 14 because the user explicitly requested preservation of existing Qwen without rebuilding it; clarification requested after discovering it absent.
- GitHub branch: codex/production-service. Release CI is being verified; do not infer completion from test-only success.

