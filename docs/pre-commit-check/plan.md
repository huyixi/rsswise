# Pre-commit / Pre-push Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Lefthook-managed local Git hooks so commits run a fast env-safety check and pushes run the existing full `make check`.

**Architecture:** Keep hooks as repository-level infrastructure: root `package.json` owns the Lefthook CLI, root `lefthook.yml` defines the two Git hooks, and `Makefile` installs dependencies plus registers hooks. CI remains independent and continues to use its existing workflow without invoking Lefthook.

**Tech Stack:** Git hooks, Lefthook, pnpm, Makefile, shell, existing `scripts/check-env-safety.sh`, existing `make check`.

---

## Task 1: Add Root Lefthook Dependency

**Files:**

- Create: `package.json`
- Create: `pnpm-lock.yaml`

- [ ] **Step 1: Confirm root Node metadata is absent**

Run:

```bash
test -f package.json
```

Expected: command exits with status 1 before implementation.

Run:

```bash
test -f pnpm-lock.yaml
```

Expected: command exits with status 1 before implementation.

- [ ] **Step 2: Create the root package manifest**

Create `package.json` with repository-level metadata only:

```json
{
  "name": "rsswise",
  "private": true,
  "packageManager": "pnpm@11.3.0",
  "devDependencies": {}
}
```

Do not add `postinstall`, `prepare`, or any other lifecycle script.

- [ ] **Step 3: Install Lefthook as a local dev dependency**

Run from the repository root:

```bash
pnpm add -D lefthook@latest
```

Expected:

- `package.json` contains a `devDependencies.lefthook` entry with the resolved version range from pnpm.
- `pnpm-lock.yaml` is created at the repository root.
- No dependency is added to `apps/web/package.json`.
- No change is made to `apps/web/pnpm-lock.yaml`.

Do not handwrite `"lefthook": "^latest"` because `^latest` is not a valid semver range. Let pnpm resolve and write the actual dependency range.

- [ ] **Step 4: Verify the local Lefthook binary**

Run:

```bash
pnpm exec lefthook --version
```

Expected: command exits 0 and prints a Lefthook version string.

- [ ] **Step 5: Commit**

```bash
git add package.json pnpm-lock.yaml
git commit -m "chore: add lefthook dependency"
```

## Task 2: Add Lefthook Configuration

**Files:**

- Create: `lefthook.yml`

- [ ] **Step 1: Confirm hook configuration is absent**

Run:

```bash
test -f lefthook.yml
```

Expected: command exits with status 1 before implementation.

- [ ] **Step 2: Create `lefthook.yml`**

Create the file with exactly the two required hooks:

```yaml
pre-commit:
  commands:
    env-safety:
      run: scripts/check-env-safety.sh

pre-push:
  commands:
    check:
      run: make check
```

Do not add commit message lint, formatting, staged-only lint, or commands that modify files.

- [ ] **Step 3: Verify manual pre-commit execution**

Run:

```bash
pnpm exec lefthook run pre-commit
```

Expected: command runs `scripts/check-env-safety.sh` from the repository root and prints:

```text
env safety checks passed
```

If the command cannot find `scripts/check-env-safety.sh`, change the hook command to explicitly run from the repository root:

```yaml
pre-commit:
  commands:
    env-safety:
      run: 'cd "$(git rev-parse --show-toplevel)" && scripts/check-env-safety.sh'

pre-push:
  commands:
    check:
      run: 'cd "$(git rev-parse --show-toplevel)" && make check'
```

Then rerun the same verification command.

- [ ] **Step 4: Verify manual pre-push execution**

Run:

```bash
pnpm exec lefthook run pre-push
```

Expected: command runs `make check` from the repository root and preserves the original output from pytest, ruff, pnpm build, and env-safety.

If this fails because local PostgreSQL, Redis, Docker, or environment values are not ready, do not weaken the hook. Record the failure in the final report and verify again after the local environment is ready.

- [ ] **Step 5: Commit**

```bash
git add lefthook.yml
git commit -m "chore: configure local git hooks"
```

## Task 3: Wire Hooks Into Makefile

**Files:**

- Modify: `Makefile`

- [ ] **Step 1: Add hook targets to `.PHONY`**

Update the existing `.PHONY` line so it includes the new hook helpers:

```makefile
.PHONY: help install dev-up dev-down dev-logs dev-reset deploy-check deploy api worker beat test web web-build check db-migrate env-check epub-test hooks-install hooks-run-pre-commit hooks-run-pre-push
```

- [ ] **Step 2: Add hook commands to `make help`**

Add these lines in the local development command list after `make check`:

```makefile
	@echo "  make hooks-install          Install Lefthook Git hooks"
	@echo "  make hooks-run-pre-commit  Run pre-commit hook manually"
	@echo "  make hooks-run-pre-push    Run pre-push hook manually"
```

- [ ] **Step 3: Update `make install`**

Change the existing `install` target from:

```makefile
install:
	cd $(API_DIR) && uv venv && uv pip install -e ".[dev]"
	cd $(WEB_DIR) && pnpm install
```

to:

```makefile
install:
	cd $(API_DIR) && uv venv && uv pip install -e ".[dev]"
	cd $(WEB_DIR) && pnpm install
	pnpm install
	pnpm exec lefthook install
```

This keeps backend and frontend dependency installation unchanged, then installs root Lefthook dependencies and registers hooks with the local binary.

- [ ] **Step 4: Add manual hook helper targets**

Add these targets near `env-check` or after `check`:

```makefile
hooks-install:
	pnpm install
	pnpm exec lefthook install

hooks-run-pre-commit:
	pnpm exec lefthook run pre-commit

hooks-run-pre-push:
	pnpm exec lefthook run pre-push
```

- [ ] **Step 5: Dry-run Makefile targets**

Run:

```bash
make -n install
make -n hooks-install
make -n hooks-run-pre-commit
make -n hooks-run-pre-push
```

Expected:

- `make -n install` prints backend install, frontend install, root `pnpm install`, and `pnpm exec lefthook install`.
- `make -n hooks-install` prints root `pnpm install` and `pnpm exec lefthook install`.
- `make -n hooks-run-pre-commit` prints `pnpm exec lefthook run pre-commit`.
- `make -n hooks-run-pre-push` prints `pnpm exec lefthook run pre-push`.

- [ ] **Step 6: Verify repeatable hook installation**

Run:

```bash
make hooks-install
make hooks-install
```

Expected: both runs exit 0. The second run must not fail because hooks already exist.

- [ ] **Step 7: Commit**

```bash
git add Makefile
git commit -m "chore: install git hooks from make"
```

## Task 4: Document Local Hook Workflow

**Files:**

- Modify: `README.md`

- [ ] **Step 1: Update the Local Development section**

After the initial setup command block:

```bash
cp .env.compose.example .env.compose
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env
make install
make dev-up
make db-migrate
```

add:

```markdown
`make install` installs backend dependencies, frontend dependencies, the repository-level Lefthook dependency, and local Git hooks.
```

- [ ] **Step 2: Expand the Checks section**

Replace the current Checks section:

````markdown
## Checks

```bash
make check
```
````

with:

````markdown
## Checks

Run the full local check suite:

```bash
make check
```

Local Git hooks are installed by `make install`.

- `git commit` runs a fast `pre-commit` env-safety check.
- `git push` runs `pre-push`, which executes the full `make check`.
- `make hooks-run-pre-commit` runs the pre-commit hook manually.
- `make hooks-run-pre-push` runs the pre-push hook manually.

Emergency bypasses are available through Git's native flags, but should not be part of normal development:

```bash
git commit --no-verify -m "..."
git push --no-verify
```
````

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document local git hooks"
```

## Task 5: Verify Hook Behavior

**Files:**

- Read: `lefthook.yml`
- Read: `Makefile`
- Read: `README.md`
- Temporary only: `apps/web/src/_lefthook_env_verify.ts`
- Temporary only: `apps/api/app/_lefthook_verify_bad.py`
- Temporary only: local bare Git remote under `/tmp`

- [ ] **Step 1: Run full static verification**

Run:

```bash
pnpm exec lefthook --version
make hooks-install
make hooks-run-pre-commit
make hooks-run-pre-push
make check
```

Expected:

- `pnpm exec lefthook --version` exits 0.
- `make hooks-install` exits 0.
- `make hooks-run-pre-commit` exits 0.
- `make hooks-run-pre-push` executes `make check`.
- `make check` exits 0 in a ready local environment.

If `make hooks-run-pre-push` or `make check` fails because the local database, Redis, Docker, or environment is unavailable, keep the `pre-push` hook unchanged and record the exact failing command and output in the final report.

- [ ] **Step 2: Verify pre-commit blocks a failing commit**

Create a temporary frontend env-name violation:

```bash
printf 'const VITE_DEEPSEEK_API_KEY = "test";\n' > apps/web/src/_lefthook_env_verify.ts
git add apps/web/src/_lefthook_env_verify.ts
git commit -m "test: should fail pre-commit"
```

Expected:

- Lefthook runs `pre-commit`.
- `scripts/check-env-safety.sh` reports `Dangerous frontend env names found`.
- Commit is blocked.

Clean up:

```bash
git restore --staged apps/web/src/_lefthook_env_verify.ts
rm -f apps/web/src/_lefthook_env_verify.ts
```

- [ ] **Step 3: Verify pre-commit allows a passing commit without polluting the working branch**

Only run this step after committing the implementation work or from a clean worktree.

Run:

```bash
current_branch=$(git branch --show-current)
git switch -c verify/lefthook-commit-pass
git commit --allow-empty -m "test: pre-commit check"
git switch "$current_branch"
git branch -D verify/lefthook-commit-pass
```

Expected:

- Lefthook runs `pre-commit`.
- Empty test commit is created on the temporary branch.
- Temporary branch is deleted after switching back.

- [ ] **Step 4: Verify `git commit --no-verify` bypasses pre-commit without polluting the working branch**

Only run this step after committing the implementation work or from a clean worktree.

Run:

```bash
current_branch=$(git branch --show-current)
git switch -c verify/lefthook-commit-no-verify
printf 'const VITE_DEEPSEEK_API_KEY = "test";\n' > apps/web/src/_lefthook_env_verify.ts
git add apps/web/src/_lefthook_env_verify.ts
git commit --no-verify -m "test: skip pre-commit"
git switch "$current_branch"
git branch -D verify/lefthook-commit-no-verify
```

Expected:

- `pre-commit` does not run.
- Test commit is created on the temporary branch.
- Temporary branch is deleted after switching back.
- The original branch has no `_lefthook_env_verify.ts` file.

- [ ] **Step 5: Verify pre-push blocks a failing push using a local remote**

Create a temporary local bare remote and a temporary branch:

```bash
tmp_remote_dir=$(mktemp -d)
git init --bare "$tmp_remote_dir/rsswise.git"
git remote add lefthook-test "$tmp_remote_dir/rsswise.git"
current_branch=$(git branch --show-current)
git switch -c verify/lefthook-push-fail
printf 'def broken(:\n    pass\n' > apps/api/app/_lefthook_verify_bad.py
git add apps/api/app/_lefthook_verify_bad.py
git commit --no-verify -m "test: push should fail"
git push lefthook-test HEAD:refs/heads/lefthook-push-fail
```

Expected:

- Lefthook runs `pre-push`.
- `make check` runs.
- Ruff or Python tooling reports the syntax error in `apps/api/app/_lefthook_verify_bad.py`.
- Push is blocked.

Clean up:

```bash
git switch "$current_branch"
git branch -D verify/lefthook-push-fail
git remote remove lefthook-test
rm -rf "$tmp_remote_dir"
```

- [ ] **Step 6: Verify pre-push allows a passing push using a local remote**

Only run this step when `make check` passes locally.

Run:

```bash
tmp_remote_dir=$(mktemp -d)
git init --bare "$tmp_remote_dir/rsswise.git"
git remote add lefthook-test "$tmp_remote_dir/rsswise.git"
current_branch=$(git branch --show-current)
git switch -c verify/lefthook-push-pass
git commit --allow-empty -m "test: pre-push check"
git push lefthook-test HEAD:refs/heads/lefthook-push-pass
git switch "$current_branch"
git branch -D verify/lefthook-push-pass
git remote remove lefthook-test
rm -rf "$tmp_remote_dir"
```

Expected:

- Lefthook runs `pre-push`.
- `make check` exits 0.
- Push to the local bare remote succeeds.
- No remote branch is pushed to the real `origin`.

- [ ] **Step 7: Verify `git push --no-verify` bypasses pre-push using a local remote**

Run:

```bash
tmp_remote_dir=$(mktemp -d)
git init --bare "$tmp_remote_dir/rsswise.git"
git remote add lefthook-test "$tmp_remote_dir/rsswise.git"
current_branch=$(git branch --show-current)
git switch -c verify/lefthook-push-no-verify
printf 'def broken(:\n    pass\n' > apps/api/app/_lefthook_verify_bad.py
git add apps/api/app/_lefthook_verify_bad.py
git commit --no-verify -m "test: skip pre-push"
git push --no-verify lefthook-test HEAD:refs/heads/lefthook-push-no-verify
git switch "$current_branch"
git branch -D verify/lefthook-push-no-verify
git remote remove lefthook-test
rm -rf "$tmp_remote_dir"
```

Expected:

- `pre-push` does not run.
- Push to the local bare remote succeeds despite the broken file on the temporary branch.
- Temporary branch, temporary remote, and temporary directory are removed.

## Task 6: Final Review

**Files:**

- Read: `docs/pre-commit-check/spec.md`
- Read: `package.json`
- Read: `pnpm-lock.yaml`
- Read: `lefthook.yml`
- Read: `Makefile`
- Read: `README.md`

- [ ] **Step 1: Confirm changed files match scope**

Run:

```bash
git status --short
```

Expected changed files for the implementation:

```text
lefthook.yml
package.json
pnpm-lock.yaml
Makefile
README.md
```

No changes should appear under:

```text
.github/workflows/check.yml
scripts/check-env-safety.sh
apps/api/
apps/web/
```

except for temporary verification files that have already been removed.

- [ ] **Step 2: Inspect Lefthook configuration for forbidden commands**

Run:

```bash
rg -n 'commitlint|format|prettier|eslint|lint-staged|staged|write|fix' lefthook.yml
```

Expected: no matches.

- [ ] **Step 3: Confirm final dependency version**

Run:

```bash
pnpm exec lefthook --version
pnpm list lefthook --depth 0
```

Expected: both commands identify the installed local Lefthook package and version.

- [ ] **Step 4: Prepare the final implementation report**

Include:

- Changed files.
- Lefthook npm package name and installed version.
- Whether `make install` succeeded.
- Whether `pnpm exec lefthook run pre-commit` succeeded.
- Whether `pnpm exec lefthook run pre-push` succeeded.
- Whether `make check` succeeded.
- Whether ordinary `git commit` triggered `pre-commit`.
- Whether ordinary `git push` triggered `pre-push`.
- Whether `git commit --no-verify` bypassed `pre-commit`.
- Whether `git push --no-verify` bypassed `pre-push`.
- Whether test commits, test branches, local test remote, and temporary files were cleaned up.
- Any local environment failures and the exact next step required to re-run verification.
