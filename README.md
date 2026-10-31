# Pontis

Desktop app for bidirectional sync between local folders and the cloud, powered by [rclone](https://rclone.org). Linux only in v1.

> Status: under development (Part 0 — project foundation).

## Development

```bash
conda create -n pontis-dev python=3.12
conda activate pontis-dev
pip install -e ".[dev]"
pre-commit install

pontis          # opens an empty window
pytest && ruff check . && mypy
```

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
