# wxweb risk control

- Default mode is `observe`.
- `auto` mode should require a non-empty group allowlist.
- Avoid logging large DOM, image base64, credentials or sensitive personal data.
- Do not persist wxweb artifacts under `/tmp`.
- Logs and snapshots are bounded by rotation, retention and total-size GC.
