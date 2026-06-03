#!/bin/sh
set -eu

SSH_HOST=${SSH_HOST:-rsswise-prod}
SSH_PATH=${SSH_PATH:-/home/ubuntu/rsswise}
COMPOSE_PROD=${COMPOSE_PROD:-docker compose -f docker-compose.prod.yml}

quote_for_remote_sh() {
	printf "'%s'" "$(printf "%s" "$1" | sed "s/'/'\\\\''/g")"
}

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
	echo "Local tracked files have uncommitted changes. Commit or stash them before deploy." >&2
	git status --short --untracked-files=no >&2
	exit 1
fi

remote_ssh_path=$(quote_for_remote_sh "$SSH_PATH")
remote_compose_prod=$(quote_for_remote_sh "$COMPOSE_PROD")

echo "Pushing current branch..."
git push

echo "Deploying to ${SSH_HOST}:${SSH_PATH}..."
ssh "$SSH_HOST" "SSH_PATH=${remote_ssh_path} COMPOSE_PROD=${remote_compose_prod} sh -s" <<'REMOTE'
set -eu

cd "$SSH_PATH"

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
	echo "Remote tracked files have uncommitted changes. Commit or stash them before deploy." >&2
	git status --short --untracked-files=no >&2
	exit 1
fi

git pull --ff-only

$COMPOSE_PROD up -d --build --remove-orphans
$COMPOSE_PROD exec -T api uv run --no-sync alembic upgrade head
$COMPOSE_PROD ps
REMOTE
