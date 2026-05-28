# wxweb runbook

1. Start TMWebDriver/browser support if needed: `ops/ga-service tmwd start`.
2. Open Web WeChat: `ops/ga-service wxweb open` or `ops/ga-service wxweb qr`.
3. Scan login QR in VNC Chromium.
4. Probe page state: `ops/ga-service wxweb probe`.
5. Keep mode `observe` until selectors and allowlisted groups are verified.
6. Run service: `ops/ga-service wxweb start`.
7. Control log growth: `ops/ga-service wxweb gc` and `ops/ga-service wxweb logs-size`.
