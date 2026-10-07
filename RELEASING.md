# Releasing

Releases go to PyPI from GitHub Actions (`.github/workflows/release.yml`) using
[trusted publishing](https://docs.pypi.org/trusted-publishers/). No API token is stored anywhere.

## One-time setup

1. Create an account on [pypi.org](https://pypi.org) and enable 2FA.
2. Add a pending trusted publisher at <https://pypi.org/manage/account/publishing/>:
   - PyPI project name: `knott`
   - Owner: `nesterione`, repository: `knott`
   - Workflow name: `release.yml`
   - Environment name: `pypi`
3. In the GitHub repo, open Settings → Environments and create an environment named `pypi`.
   Optionally add yourself as a required reviewer so each publish waits for approval.

## Each release

```sh
uv version --bump patch          # or minor / major; updates pyproject.toml and uv.lock
git commit -am "Release v$(uv version --short)"
git tag "v$(uv version --short)"
git push origin main --tags
```

The workflow runs CI, checks that the tag matches the version in `pyproject.toml`, builds,
smoke-tests the wheel with `uvx`, and publishes. A new version shows up for `uvx knott`
within a few minutes. Users with a cached copy can run `uvx knott@latest` to pick it up.
