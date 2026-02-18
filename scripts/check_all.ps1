$ErrorActionPreference = "Stop"

uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest
