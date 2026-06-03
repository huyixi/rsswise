#!/bin/sh
set -eu

tracked_env_files=$(git ls-files | grep -E '(^|/)\.env($|\.)' | grep -vE '(\.example|\.env\.compose\.example)$' || true)
if [ -n "$tracked_env_files" ]; then
	echo "Tracked real env files found:" >&2
	echo "$tracked_env_files" >&2
	exit 1
fi

frontend_secret_refs=$(rg -n 'VITE_.*(SECRET|TOKEN|PASSWORD|DATABASE|JWT|OPENAI|DEEPSEEK|STRIPE|S3)' apps/web .env.example .env.compose.example apps/web/.env.example || true)
if [ -n "$frontend_secret_refs" ]; then
	echo "Dangerous frontend env names found:" >&2
	echo "$frontend_secret_refs" >&2
	exit 1
fi

web_bundle_secret_refs=""
if [ -d apps/web/dist ]; then
	web_bundle_secret_refs=$(rg -n 'DEEPSEEK_API_KEY|DATABASE_URL|POSTGRES_PASSWORD|JWT_SECRET|SESSION_SECRET|S3_SECRET_ACCESS_KEY|STRIPE_SECRET_KEY|OPENAI_API_KEY' apps/web/dist || true)
fi

if [ -n "$web_bundle_secret_refs" ]; then
	echo "Sensitive names found in web bundle:" >&2
	echo "$web_bundle_secret_refs" >&2
	exit 1
fi

echo "env safety checks passed"
