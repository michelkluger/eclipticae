# Contributing

Thanks for your interest in improving `ecliptica`.

## Development Setup

1. Install dependencies:

```bash
uv sync --dev
```

On Ubuntu/Linux, install Manim native prerequisites first:

```bash
sudo apt-get update
sudo apt-get install -y pkg-config libcairo2-dev libpango1.0-dev ffmpeg
```

2. Run checks before opening a PR:

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest
```

## Pull Requests

- Keep PRs focused and small enough to review.
- Add or update tests for behavior changes.
- Update `CHANGELOG.md` for user-visible changes.
- Ensure CI is green before requesting review.

## Commit/Review Expectations

- Prefer clear, descriptive commit messages.
- Keep public API changes explicit in PR descriptions.
- Include before/after behavior when fixing bugs.

## Release Process

1. Update `CHANGELOG.md`.
2. Create and push a semantic version tag, for example `v0.1.1`.
3. GitHub Actions will run `.github/workflows/release.yml` and publish to PyPI.

PyPI Trusted Publishing setup (one-time in PyPI project settings):
- Add a Trusted Publisher for this GitHub repo (`michelkluger/ecliptica`).
- Workflow file: `release.yml`.
- Environment: `pypi`.
- No `PYPI_API_TOKEN` secret is needed after Trusted Publishing is configured.
