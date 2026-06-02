# Local Development Infra Split Design

## Summary

本地开发环境拆成两层：

- Docker Compose 只运行依赖服务：PostgreSQL 和 Redis。
- 本地机器运行应用进程：FastAPI API、Celery worker、Celery beat、前端、测试和构建检查。

本轮不新增对象存储，不新增 RabbitMQ 或其他独立消息队列，不新增 CLI 或代码生成入口，不改变生产部署。

## Current State

当前仓库有两个 Compose 文件：

- `docker-compose.yml`：本地全栈容器开发，包含 PostgreSQL、Redis、API、worker、beat 和 web。
- `docker-compose.prod.yml`：生产全栈容器部署，包含 PostgreSQL、Redis、API、worker、beat、web 和 Caddy。

当前 Makefile 主要围绕 `docker compose` 全栈容器运行：

- `make up` 启动全部开发服务。
- `make test` 在 API 容器中执行 pytest。
- `make db-migrate` 在 API 容器中执行 Alembic。

这会把应用开发、测试、依赖服务混在容器里。对前端、后端、worker 的本机调试、代码生成和测试都不够直接。

## Target Architecture

新增 `docker-compose.dev.yml` 作为本地依赖栈，只包含：

- `postgres`
- `redis`

保留现有 `docker-compose.yml` 和 `docker-compose.prod.yml` 文件内容不变。全栈 Docker Compose 仍可手动使用，但不是主要本地开发入口。

本机应用进程通过 Makefile 运行：

- `make api`：本机运行 FastAPI。
- `make worker`：本机运行 Celery worker。
- `make beat`：本机运行 Celery beat。
- `make db-migrate`：本机运行 Alembic 数据库迁移。
- `make web`：本机运行前端开发服务器。
- `make test`：本机运行后端测试。
- `make web-build`：本机构建前端。
- `make check`：本机运行后端测试、后端 lint、前端构建。

## Environment Model

本机开发命令默认连接本机端口：

```text
DATABASE_URL=postgresql+psycopg://rsswise:rsswise@127.0.0.1:5432/rsswise
REDIS_URL=redis://127.0.0.1:6379/0
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

这些默认值在 Makefile 中通过 `?=` 设置，开发者可以通过 shell 环境变量覆盖。

`.env.example` 继续保留现有全栈 Compose 默认值，避免破坏从 `.env.example` 复制 `.env` 后运行旧 `docker-compose.yml` 的行为。本机 Makefile 目标会显式覆盖 DB 和 Redis 地址。

Redis 继续作为 Celery broker 和 result backend。本轮不引入独立 MQ。

## Command Surface

本地开发入口：

```text
make install      Install backend and frontend dependencies
make dev-up       Start PostgreSQL and Redis
make dev-down     Stop local dependencies
make dev-logs     Show dependency logs
make dev-reset    Reset local dependency data
make api          Run backend API locally
make worker       Run Celery worker locally
make beat         Run Celery beat locally
make db-migrate   Run database migrations locally
make test         Run backend tests
make web          Run frontend locally
make web-build    Build frontend
make check        Run test/build checks
```

后端依赖安装使用 `uv`，运行命令使用 `uv run --no-sync`，由 `make install` 负责同步依赖，避免日常运行目标生成未跟踪的 `uv.lock`。前端依赖和命令使用 `pnpm`。

## Out of Scope

- 不添加 MinIO 或对象存储服务。
- 不添加 RabbitMQ、Kafka 或其他独立消息队列。
- 不把 Celery broker 从 Redis 切走。
- 不新增 CLI 或代码生成入口。
- 不修改生产 Compose 或 Caddy 部署方式。
- 不迁移前端框架，不处理 `docs/migration/` 中的 Next.js 到 Vite 迁移。

## Acceptance Criteria

- `make dev-up` 只启动 PostgreSQL 和 Redis。
- `docker-compose.dev.yml` 不定义 API、worker、beat、web、Caddy 或对象存储服务。
- `make api`、`make worker`、`make beat` 在本机运行，并默认连接 `127.0.0.1` 的 DB/Redis。
- `make test` 在本机通过 `uv run --no-sync pytest -v` 执行。
- `make web` 和 `make web-build` 在本机通过 `pnpm` 执行。
- `make check` 覆盖后端测试、后端 lint 和前端构建。
- `docker-compose.yml` 和 `docker-compose.prod.yml` 内容不被本轮修改。
