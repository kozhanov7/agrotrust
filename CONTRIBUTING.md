# Contributing

## Set up

```bash
git clone https://github.com/kozhanov7/agrotrust.git
cd agrotrust-metrics
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Workflow

1. Open an issue that describes the bug or the new metric.
2. Create a branch from `main`: `feature/<short-name>` or `fix/<short-name>`.
3. Write a test first when you change a formula, then the code.
4. Run the same checks as CI:
   ```bash
   ruff check . && ruff format --check . && pytest --cov=agrotrust_metrics
   ```
5. Open a pull request that references the issue (`Closes #12`). CI must be green before merge.

## Commit messages

Short imperative subject (`Add MTTR to the fleet summary`), blank line, then the reason if it is not obvious.

## Releases

Update `version` in `pyproject.toml` and `CHANGELOG.md`, then tag:

```bash
git tag -a v0.2.0 -m "v0.2.0" && git push origin v0.2.0
```

The `release` job of the CI workflow builds the package and publishes a GitHub release with the wheel and the example results attached.
