# GA Web WeChat Bot (`wxweb`)

This directory contains the GA-controlled Web WeChat automation skeleton. All persistent configuration, runtime state, logs, screenshots, and DOM snapshots stay inside this directory.

## Layout

- `config.yaml` — operation mode, reply and log-retention settings.
- `src/` — Python CLI and browser probing helpers.
- `data/` — group allowlist, FAQ, selectors and optional knowledge files.
- `runtime/` — pid/state/mode files; ignored by git except `.gitkeep`.
- `logs/` — rotating app/error logs, messages, screenshots, DOM snapshots; ignored by git except `.gitkeep`.
- `docs/` — design and runbook notes.

## Common commands

```bash
ops/ga-service wxweb status
ops/ga-service wxweb open
ops/ga-service wxweb qr
ops/ga-service wxweb probe
ops/ga-service wxweb mode observe
ops/ga-service wxweb start
ops/ga-service wxweb logs -n 100
ops/ga-service wxweb gc --dry-run
ops/ga-service wxweb stop
```

The MVP starts in `observe` mode. Configure `data/allowed_groups.yaml` before enabling `auto` mode.
