#!/usr/bin/env bash
# Keeps mutable runtime state on a separate "state" branch so the protected "main" branch
# never receives bot commits.
#   pull : copy state files from origin/state over the checked-out working tree
#   push : commit the working-tree state files to origin/state
set -euo pipefail

BRANCH="${STATE_BRANCH:-state}"
PATHS=(data/memory.sqlite3 evolution/stable.json evolution/history.json evolution/versions evolution/proposals docs/state)

remote_has_branch() {
  git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1
}

case "${1:-}" in
  pull)
    if remote_has_branch; then
      git fetch --depth=1 origin "$BRANCH"
      for p in "${PATHS[@]}"; do
        if git cat-file -e "FETCH_HEAD:$p" 2>/dev/null; then
          rm -rf "$p"
          mkdir -p "$(dirname "$p")"
          git checkout FETCH_HEAD -- "$p"
        fi
      done
      git reset -q
      echo "State restored from branch '$BRANCH'."
    else
      echo "No '$BRANCH' branch yet; using the files committed on the default branch."
    fi
    ;;
  push)
    git config user.name "github-actions[bot]"
    git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
    WT="$(mktemp -d)"
    if remote_has_branch; then
      git fetch --depth=1 origin "$BRANCH"
      git worktree add --detach "$WT" FETCH_HEAD
    else
      git worktree add --detach "$WT"
      git -C "$WT" checkout -q --orphan "$BRANCH"
      git -C "$WT" rm -rfq . || true
    fi
    for p in "${PATHS[@]}"; do
      if [ -e "$p" ]; then
        rm -rf "$WT/$p"
        mkdir -p "$WT/$(dirname "$p")"
        cp -r "$p" "$WT/$p"
      fi
    done
    cd "$WT"
    git add -f -A "${PATHS[@]}" 2>/dev/null || git add -f -A .
    if git diff --cached --quiet; then
      echo "No state changes to commit."
    else
      git commit -q -m "Update state (${GITHUB_WORKFLOW:-manual})"
      git push origin "HEAD:refs/heads/$BRANCH"
      echo "State pushed to branch '$BRANCH'."
    fi
    ;;
  *)
    echo "usage: state_sync.sh pull|push" >&2
    exit 2
    ;;
esac
