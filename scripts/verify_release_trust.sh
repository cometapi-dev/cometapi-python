#!/usr/bin/env bash
set -euo pipefail

: "${DEFAULT_BRANCH:?DEFAULT_BRANCH is required}"
: "${RELEASE_IMMUTABLE:?RELEASE_IMMUTABLE is required}"
: "${RELEASE_TAG:?RELEASE_TAG is required}"

if [[ "$RELEASE_IMMUTABLE" != "true" ]]; then
  echo "Publication requires a GitHub release with immutable=true." >&2
  exit 1
fi

git check-ref-format --branch "$DEFAULT_BRANCH" >/dev/null
release_ref="refs/tags/${RELEASE_TAG}"
release_commit="$(git rev-parse --verify "${release_ref}^{commit}")"
head_commit="$(git rev-parse --verify 'HEAD^{commit}')"

if [[ "$head_commit" != "$release_commit" ]]; then
  echo "Checked-out commit $head_commit does not match $release_ref ($release_commit)." >&2
  exit 1
fi

default_remote_ref="refs/remotes/origin/${DEFAULT_BRANCH}"
git fetch --no-tags origin "+refs/heads/${DEFAULT_BRANCH}:${default_remote_ref}"
if ! git merge-base --is-ancestor "$release_commit" "$default_remote_ref"; then
  echo "Release commit $release_commit is not reachable from origin/$DEFAULT_BRANCH." >&2
  exit 1
fi

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "release-commit=$release_commit" >> "$GITHUB_OUTPUT"
fi
