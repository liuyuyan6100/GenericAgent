# wxweb design

`wxweb` uses GenericAgent browser control to open/probe Web WeChat and keeps service artifacts local to `ops/wechat_web_bot/`. The current implementation is a safe MVP skeleton: service loop, mode switching, page probing, log rotation and cleanup. Reply execution should remain allowlist-first and default to observe mode.
