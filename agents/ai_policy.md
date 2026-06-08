# AI Coding Policy

This policy applies to contributors using AI tools to help write code, documentation, tests, plans, reviews, issues, or pull requests.

AI may assist development, but it does not own the change. Authors are responsible for the correctness, security, maintainability, and long-term impact of their changes.

**Do not commit or merge AI-assisted changes that you cannot explain, test, or maintain.**

## Basic Rules

Authors must review and understand all AI-assisted changes before committing or merging them.

AI-generated work should not be committed unless the author can explain:

* What changed
* Why it is needed
* How it works
* How it was verified
* What risks remain

Authors must ensure that submitted work is original and does not knowingly include copied code from unknown or unverified sources.

When an AI agent drafts an issue, pull request, or response, and a human replies, the human operator must review and respond. AI may draft the reply, but a human must decide what to say.

## High-Risk Changes

AI tools must not make broad changes to high-risk areas without first outputting a plan.

High-risk areas include:

* Authentication, authorization, and access control
* Database schemas, migrations, data deletion, or irreversible data changes
* Deployment, CI/CD, infrastructure, secrets, and production configuration
* Payment, billing, quotas, or cost-related logic
* User privacy, personal data, analytics, and logging
* File uploads, storage, and user-generated content
* Background jobs, queues, retries, and external API integrations when they affect production data, cost, privacy, or external systems
* AI prompts, model selection, retrieval, caching, or evaluation when they affect product behavior, cost, or user-facing output
* Security-sensitive dependencies, SDKs, middleware, or configuration

A broad change means any change that affects production behavior, data shape, deployment behavior, security boundaries, user data, external systems, cost, or multiple modules.

Before modifying a high-risk area, AI tools must output:

```md
## Modification Plan

### Current behavior

### Planned changes

### What will NOT be changed

### Potential risks

### Items requiring human confirmation

### Verification commands
```

Only after human confirmation may the modification proceed, unless the author has explicitly granted session-level approval.

## Prohibited Actions

AI tools must not:

* Commit or push changes without explicit human approval
* Modify or print secrets, access tokens, API keys, private credentials, or private configuration
* Run destructive database commands without explicit human approval
* Delete data, files, migrations, branches, or deployment configuration without explicit human approval
* Change production deployment targets, domains, credentials, or environment variables without explicit human approval
* Introduce third-party services, SDKs, paid APIs, analytics, or tracking tools without explaining cost, security, and privacy impact
* Claim verification was completed when it was not actually run
* Hide uncertainty behind vague language

If uncertain, mark the relevant area as:

```txt
NEEDS HUMAN CONFIRMATION
```

## Required Summary

After each AI-assisted modification, the agent must output:

```md
## Modification Summary

### Files changed

### Why each file was changed

### Core logic changes

### Risks

### Items requiring manual review

### Suggested verification commands
```

## Pull Request Note

For non-trivial AI-assisted changes, include a short note in the pull request, commit message, or development notes.

```md
## AI Assistance

AI tools were used for:

- 

Manual review performed:

- 

Verification:

- 

Risks or uncertain areas:

- 
```
