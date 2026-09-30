# Quant Pricer

A local pricing and risk workstation for equity derivatives and structured products. It starts with
vanilla options and grows, phase by phase, into exotics and structured products.

## Quick start

Requirements:
- [uv](https://docs.astral.sh/uv/), which installs Python 3.12 automatically.
- Node.js 20+.

To start, use either:
- **macOS:** double-click `start.command`.
- **Windows:** double-click `start.bat`.
- **Anywhere:** `make serve`, or `make dev` for hot reload.

The app opens at http://127.0.0.1:8765 (http://localhost:5173 in dev mode).

## Development

```
make install   # dependencies
make check     # ruff, mypy (strict on engine/), pytest + hypothesis, eslint, prettier, tsc, vitest
make e2e       # Playwright smoke tests
```

See [`CLAUDE.md`](CLAUDE.md) for architecture, conventions and the decision log, and
[`docs/`](docs/) for model and method notes.
