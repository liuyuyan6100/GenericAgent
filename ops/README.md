# GenericAgent service ops

This folder contains lightweight operational scripts for verified GenericAgent services.
The scripts are intentionally repository-local until they are tested and reviewed; they do not affect external services such as Hermes.

## Unified service manager

```bash
/home/ubuntu/tool/GenericAgent/ops/ga-service help
```

Current services:

- `wechat`: GenericAgent WeChat customer-service frontend, backed by `frontends/wechatapp.py` and the repo `.venv`.

Helper commands:

- `browser`: VNC Chromium helper, backed by `ops/vnc-browser`; it defaults to the real VNC display `:1` instead of an inherited SSH display such as `localhost:11.0`.
- `feishu-qr`: Open the default Feishu login/QR page or a target Feishu app page in VNC Chromium.
- `mumu-qr`: Shortcut alias for the Mumu AI Feishu app (`cli_a979473759f85bd6`).

Browser examples:

```bash
# Show VNC/browser environment and selected display
/home/ubuntu/tool/GenericAgent/ops/ga-service browser status

# Open or reuse Chromium inside the VNC desktop
/home/ubuntu/tool/GenericAgent/ops/ga-service browser open https://open.feishu.cn/app

# Open Feishu login/QR page or the Mumu AI app page
/home/ubuntu/tool/GenericAgent/ops/ga-service feishu-qr
/home/ubuntu/tool/GenericAgent/ops/ga-service feishu-qr cli_a979473759f85bd6
/home/ubuntu/tool/GenericAgent/ops/ga-service mumu-qr

# List VNC windows or capture a screenshot for evidence
/home/ubuntu/tool/GenericAgent/ops/ga-service browser list-windows
/home/ubuntu/tool/GenericAgent/ops/ga-service browser screenshot temp/vnc-browser.png
```

Common commands:

```bash
# Start without entering the repo directory
/home/ubuntu/tool/GenericAgent/ops/ga-service wechat start

# Check status
/home/ubuntu/tool/GenericAgent/ops/ga-service wechat status

# Show recent logs
/home/ubuntu/tool/GenericAgent/ops/ga-service wechat logs -n 100

# Show QR metadata and render QR in terminal when available
/home/ubuntu/tool/GenericAgent/ops/ga-service wechat qr

# Restart or stop
/home/ubuntu/tool/GenericAgent/ops/ga-service wechat restart
/home/ubuntu/tool/GenericAgent/ops/ga-service wechat stop
```

For shell-wide one-command usage, install a symlink. User-level install is the safe default, but it only works as `ga-service` if `~/.local/bin` is in `PATH`:

```bash
/home/ubuntu/tool/GenericAgent/ops/ga-service install-bin --user
```

For system-level direct execution from normal shells, install to `/usr/local/bin` explicitly:

```bash
/home/ubuntu/tool/GenericAgent/ops/ga-service install-bin --system
```

Then use:

```bash
ga-service wechat start
ga-service status
ga-service logs -n 80
```

Uninstall the symlink:

```bash
ga-service uninstall-bin
```

## Safety notes

- The manager only controls known GenericAgent services in this repository.
- It verifies the service process command before stopping it, so it should not kill unrelated Python processes.
- WeChat token content is never printed; only metadata/status is shown.
- Logs remain under `temp/`, for example `temp/wechatapp.runner.log` and `temp/wechatapp.log`.
