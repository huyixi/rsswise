# Pre-commit / Pre-push Check（Git 本地提交与推送检查）

## Summary

本方案为项目引入本地 Git hooks，用于在代码进入仓库和推送到远端之前提前发现问题。

方案使用 Lefthook 管理 Git hooks，并采用分层检查策略：

```text
pre-commit：快速检查，阻止明显低级错误
pre-push：完整检查，尽量提前发现 CI 会失败的问题
CI：最终质量门禁
```

具体行为：

* `git commit` 时运行轻量、快速、本地稳定的检查；
* `git push` 时运行完整 `make check`；
* CI 保持独立运行，不依赖 Lefthook；
* `make install` 自动完成依赖安装和 Git hooks 注册；
* 紧急情况下允许使用 `git commit --no-verify` 或 `git push --no-verify` 绕过本地 hooks，但不推荐日常使用。

本方案的目标不是替代 CI，而是在本地开发阶段尽早暴露问题，减少 CI 失败后的反馈循环。

---

## Background

当前项目已有统一检查入口：

```bash
make check
```

该命令覆盖 lint、type-check、test、env-safety 等检查，并且 CI 会在 PR 或 push 到 `main` 时运行相同或等价的检查流程。

但当前本地开发阶段缺少 Git hooks 约束，开发者可以在未运行任何检查的情况下提交或推送代码，导致问题延迟到 CI 阶段才暴露。

直接在 `pre-commit` 运行完整 `make check` 虽然约束最强，但会带来明显开发体验问题：

* 每次 commit 都可能等待较久；
* 如果 `make check` 依赖数据库、Redis、Docker 或其他本地服务，提交会被环境状态影响；
* 开发者可能更频繁使用 `--no-verify`；
* 长期看，本地 hook 的实际执行率会下降。

因此，本方案采用更符合工程实践的分层检查策略：

```text
commit 阶段：快
push 阶段：完整
CI 阶段：权威
```

---

## Decisions

* 使用 Lefthook 管理本地 Git hooks。
* `pre-commit` 只运行快速、本地稳定、不依赖外部服务的检查。
* `pre-push` 运行完整 `make check`。
* CI 继续独立运行完整检查，不依赖 Lefthook。
* `make install` 负责安装依赖并注册 Lefthook Git hooks。
* Lefthook CLI 使用项目本地依赖，不依赖全局安装。
* 不通过 `package.json` 的 `postinstall`、`prepare` 等生命周期脚本隐式注册 hooks。
* 保留 `--no-verify` 作为应急绕过方式。
* 暂不引入 commit message lint。
* 暂不引入自动格式化。
* 暂不引入 staged-only lint。
* 暂不引入 Husky、commitlint、pre-commit framework 或其他 hooks 工具。

---

## Current State

项目当前没有 Git hooks 管理基础设施。

已有相关能力：

| 文件                            | 说明                                 |
| ----------------------------- | ---------------------------------- |
| `Makefile`                    | 已定义 `make check`，作为本地统一检查入口        |
| `.github/workflows/check.yml` | 已定义 CI 检查流程                        |
| `package.json`                | 仓库根目录，用于安装 Lefthook CLI            |
| `scripts/check-env-safety.sh` | env-safety 检查脚本，已由 `make check` 覆盖 |

---

## Goals

* 开发者执行普通 `git commit` 时自动触发快速检查。
* 快速检查失败时阻止 commit。
* 开发者执行普通 `git push` 时自动触发完整 `make check`。
* `make check` 失败时阻止 push。
* 检查失败时保留原始命令输出，方便开发者定位问题。
* 新开发者执行 `make install` 后即可完成 hooks 安装。
* 已有开发者重复执行 `make install` 时不应报错。
* 本地 `pre-push` 检查与 CI 检查入口保持一致。
* CI 保持独立，不依赖 Lefthook。
* 不新增额外质量规则。

---

## Non-Goals

* 不引入 commit message lint。
* 不引入自动格式化。
* 不引入 staged-only lint。
* 不修改 `make check` 的内容。
* 不修改 CI 流程。
* 不在 CI 中运行 Lefthook。
* 不禁止 `git commit --no-verify`。
* 不禁止 `git push --no-verify`。
* 不引入 Husky、commitlint、pre-commit framework 或其他 Git hooks 工具。
* 不解决 `make check` 本身依赖数据库、Redis、Docker 或本地服务的问题。

---

## Requirements

### R1：Pre-commit 行为

每次执行普通 `git commit` 时，必须自动运行 Lefthook `pre-commit`。

`pre-commit` 只允许运行快速、本地稳定的检查。

检查要求：

* 不依赖数据库；
* 不依赖 Redis；
* 不依赖 Docker 容器状态；
* 不执行完整测试套件；
* 不自动修改文件；
* 不新增与本需求无关的检查维度；
* 失败时必须阻止 commit；
* 失败时必须保留原始命令输出。

第一版推荐只运行 env-safety 快速检查：

```bash
scripts/check-env-safety.sh
```

如果项目已有足够快且稳定的 lint 命令，也可以加入 `pre-commit`，但必须满足：

* 通常能在较短时间内完成；
* 不依赖外部服务；
* 不自动修改文件；
* 不改变 staged 文件内容；
* 不引入额外复杂配置。

不建议在 `pre-commit` 中运行完整 `make check`。

---

### R2：Pre-push 行为

每次执行普通 `git push` 时，必须自动运行 Lefthook `pre-push`。

`pre-push` 必须运行：

```bash
make check
```

当 `make check` 返回非 0 exit code 时：

* push 必须被阻止；
* 终端应展示 `make check` 的原始输出；
* 开发者修复问题后可重新 push。

当 `make check` 返回 0 时：

* push 正常继续；
* 不应改变 Git 的默认推送流程。

---

### R3：Lefthook 配置

仓库根目录必须存在 Lefthook 配置文件：

```text
lefthook.yml
```

该配置必须至少定义：

* `pre-commit`
* `pre-push`

推荐初始配置：

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

如果实际验证发现命令没有在仓库根目录执行，则必须调整配置，显式保证命令从仓库根目录运行。

允许使用 Lefthook 的 `root` 配置或在命令中显式 `cd` 到仓库根目录，但不得引入额外 hooks 工具。

不允许在 `lefthook.yml` 中加入以下内容：

* commitlint；
* 自动格式化；
* 自动修改文件；
* staged-only lint；
* 与本需求无关的额外检查；
* 会改变工作区文件内容的命令。

---

### R4：Lefthook 依赖

项目必须安装 Lefthook CLI，供本地开发者执行 hooks 安装和手动运行 hooks。

在仓库根目录创建 `package.json`，仅安装 Lefthook：

```json
{
  "name": "rsswise",
  "private": true,
  "devDependencies": {
    "lefthook": "^latest"
  }
}
```

选择根目录 `package.json` 而非 `apps/web/package.json` 的原因是：
* Lefthook 是仓库级工具，与前端应用无关；
* 根目录直接运行 `pnpm exec lefthook` 天然能正确找到根目录的 `lefthook.yml`；
* 避免 monorepo 子目录路径问题。

安装依赖后必须更新对应 lockfile：

```text
pnpm-lock.yaml
```

不得要求开发者通过 Homebrew、npm global、Go 或其他方式全局安装 Lefthook。

---

### R5：安装入口

执行：

```bash
make install
```

必须完成以下事情：

* 安装后端开发依赖；
* 安装前端依赖；
* 安装根目录 Lefthook 依赖（`pnpm install` at root）；
* 使用项目本地 Lefthook CLI 注册 Git hooks。

注册 hooks 必须在 Lefthook 依赖安装完成后执行。

使用本地 binary 调用：

```bash
./node_modules/.bin/lefthook install
```

或等价的 `pnpm exec`：

```bash
pnpm exec lefthook install
```

不得依赖全局 `lefthook` 命令。

`make install` 必须支持重复执行。重复执行时不应因为 hooks 已存在而失败。

不得通过 `package.json` 的 `postinstall`、`prepare` 等生命周期脚本隐式执行 `lefthook install`。

---

### R6：Monorepo 路径要求

Lefthook 依赖安装在仓库根目录，`lefthook.yml` 也在根目录，天然不存在路径不一致问题。

仍需验证以下命令：

```bash
pnpm exec lefthook run pre-commit
```

以及：

```bash
pnpm exec lefthook run pre-push
```

确保命令能从仓库根目录正确执行。

推荐额外提供 Makefile 手动入口，避免开发者记忆长命令：

```bash
make hooks-install
make hooks-run-pre-commit
make hooks-run-pre-push
```

---

### R7：开发工作流

日常提交：

```bash
git add .
git commit -m "..."
```

预期行为：

* 自动运行 `pre-commit` 快速检查；
* 检查通过则 commit 成功；
* 检查失败则阻止 commit。

日常推送：

```bash
git push
```

预期行为：

* 自动运行 `pre-push`；
* 执行完整 `make check`；
* `make check` 通过则 push 成功；
* `make check` 失败则阻止 push。

手动运行完整检查：

```bash
make check
```

手动运行 pre-commit hook：

```bash
pnpm exec lefthook run pre-commit
```

或：

```bash
make hooks-run-pre-commit
```

手动运行 pre-push hook：

```bash
pnpm exec lefthook run pre-push
```

或：

```bash
make hooks-run-pre-push
```

紧急绕过 commit hook：

```bash
git commit --no-verify -m "..."
```

紧急绕过 push hook：

```bash
git push --no-verify
```

`--no-verify` 只作为应急手段保留，不作为推荐流程。

---

### R8：与 CI 的关系

CI 继续使用现有：

```text
.github/workflows/check.yml
```

CI 继续独立运行完整检查。

本地 Lefthook 不应成为 CI 的依赖。

CI 不需要执行：

```bash
lefthook install
lefthook run pre-commit
lefthook run pre-push
```

本地 hooks 的作用是提前发现问题；CI 仍然是最终验证入口。

---

### R9：文档说明

如果仓库已有合适的开发文档位置，应补充说明：

* 执行 `make install` 会自动安装 Git hooks；
* 普通 `git commit` 会自动运行快速检查；
* 普通 `git push` 会自动运行完整 `make check`；
* 可使用 `make check` 手动运行完整检查；
* 可使用 Lefthook 手动运行 `pre-commit`；
* 可使用 Lefthook 手动运行 `pre-push`；
* 紧急情况可以使用 `--no-verify`，但不建议日常使用。

如果没有合适文档位置，可以暂不新增文档文件。

---

## Acceptance Criteria

### AC1：配置存在

仓库根目录存在：

```text
lefthook.yml
```

且其中只配置与本需求相关的 hooks：

* `pre-commit`
* `pre-push`

不得包含：

* commitlint；
* 自动格式化；
* 自动修改文件；
* 与本需求无关的额外检查。

---

### AC2：依赖安装成功

执行：

```bash
pnpm exec lefthook --version
```

应输出 Lefthook 版本号。

---

### AC3：`make install` 可注册 hooks

执行：

```bash
make install
```

应成功完成依赖安装和 Git hooks 注册。

重复执行：

```bash
make install
```

不应失败。

---

### AC4：手动运行 pre-commit

执行：

```bash
pnpm exec lefthook run pre-commit
```

应触发 `pre-commit` 快速检查。

预期：

* 能找到仓库根目录的 `lefthook.yml`；
* 能正确执行配置中的快速检查命令；
* 如果检查失败，必须显示失败原因。

---

### AC5：手动运行 pre-push

执行：

```bash
pnpm exec lefthook run pre-push
```

应触发完整：

```bash
make check
```

预期：

* 能找到仓库根目录的 `lefthook.yml`；
* 能正确找到仓库根目录的 `Makefile`；
* 能从正确目录执行 `make check`；
* 如果 `make check` 因数据库、Redis、容器或其他开发环境依赖失败，必须明确显示失败原因。

---

### AC6：Commit 失败时阻止提交

人为制造一个可被 `pre-commit` 捕获的问题后，执行：

```bash
git add .
git commit -m "test: should fail"
```

预期：

* `pre-commit` 被触发；
* commit 被阻止；
* 终端输出错误详情。

涉及真实 commit 的验收必须在临时分支执行，或在验收后清理测试提交，不应污染最终提交历史。

---

### AC7：Commit 通过时允许提交

在 `pre-commit` 通过的状态下执行：

```bash
git add .
git commit -m "test: pre-commit check"
```

预期：

* `pre-commit` 被触发；
* commit 成功创建。

验收后应清理测试提交，不应将测试提交保留在最终历史中。

---

### AC8：Push 失败时阻止推送

人为制造一个可被 `make check` 捕获的问题后，执行：

```bash
git push
```

预期：

* `pre-push` 被触发；
* `make check` 被执行；
* push 被阻止；
* 终端输出错误详情。

如需避免影响远端分支，应在临时分支或本地测试远端中验证。

---

### AC9：Push 通过时允许推送

在 `make check` 通过的状态下执行：

```bash
git push
```

预期：

* `pre-push` 被触发；
* `make check` 被执行；
* push 正常继续。

---

### AC10：`--no-verify` 可绕过

执行：

```bash
git commit --no-verify -m "test: skip pre-commit"
```

预期：

* 不运行 `pre-commit`；
* commit 可直接创建。

执行：

```bash
git push --no-verify
```

预期：

* 不运行 `pre-push`；
* push 可直接继续。

验收后应清理测试提交或临时分支。

---

## Risks and Trade-offs

### 分层检查带来的权衡

本方案不在 `pre-commit` 运行完整 `make check`，而是将完整检查放在 `pre-push`。

优点：

* commit 阶段更快；
* 日常开发阻力更小；
* 开发者更不容易频繁使用 `--no-verify`；
* 完整检查仍会在 push 前运行；
* CI 仍然作为最终质量门禁。

代价：

* 某些问题可能在 commit 阶段不会被发现；
* 问题可能延迟到 push 阶段才暴露；
* 如果开发者长期只 commit 不 push，本地完整检查不会自动运行。

该权衡是有意选择。

---

### `make check` 仍可能受本地环境影响

`pre-push` 会运行完整 `make check`。

如果 `make check` 依赖：

* PostgreSQL；
* Redis；
* Docker；
* 本地环境变量；
* 其他开发服务；

那么 push 行为也会受到这些本地环境状态影响。

本需求不修改 `make check` 的内容，也不解决 `make check` 的环境依赖问题。

---

### Monorepo 路径问题

Lefthook 依赖安装在仓库根目录，与 `lefthook.yml` 和 `Makefile` 同目录，天然不存在子目录路径问题。

---

### 包名兼容问题

Lefthook npm 依赖优先使用：

```text
lefthook
```

如果当前环境无法安装该包，或官方推荐方式发生变化，允许调整，但必须在最终报告中说明：

* 使用的包名；
* 使用的版本；
* 调整原因；
* lockfile 是否已更新。

---

### Hooks 可被绕过

Git 原生支持 `--no-verify` 绕过 hooks。

本方案不试图禁止该行为。

正确做法是：

* 本地 hooks 提前反馈；
* CI 作为最终兜底；
* 文档中说明 `--no-verify` 只用于应急。

---

## Expected Changed Files

预计涉及：

| 文件                      | 变更                                          |
| ------------------------- | ------------------------------------------- |
| `lefthook.yml`            | 新建，定义 `pre-commit` 与 `pre-push`             |
| `package.json`            | 新建，仓库根目录，仅安装 Lefthook CLI devDependency    |
| `pnpm-lock.yaml`          | 安装依赖后自动更新（根目录）                              |
| `Makefile`                | 修改 `install` 目标，追加 hooks 注册；可选新增 hooks 手动入口 |
| `README.md` 或开发文档         | 可选，补充本地 hooks 说明                            |

不应涉及：

| 文件                            | 原因         |
| ----------------------------- | ---------- |
| `.github/workflows/check.yml` | CI 保持独立    |
| `scripts/check-env-safety.sh` | 只被调用，不修改内容 |
| 后端业务代码                        | 与本需求无关     |
| 前端业务代码                        | 与本需求无关     |
| `.gitignore`                  | 通常无需修改     |

---

## Implementation Notes

实现时应先完成最小闭环：

1. 在仓库根目录创建 `package.json` 并安装 Lefthook CLI；
2. 创建 `lefthook.yml`；
3. 配置 `pre-commit` 快速检查；
4. 配置 `pre-push` 运行 `make check`；
5. 修改 `make install`，加入 hooks 注册；
6. 验证 `make install`；
7. 验证 `pre-commit`；
8. 验证 `pre-push`；
9. 验证普通 commit 行为；
10. 验证普通 push 行为；
11. 必要时补充文档。

不得在未验证 monorepo 路径的情况下认为实现完成。

不得因为本地环境问题而弱化 `make check`。

不得为了让 hook 通过而修改 CI、业务代码或检查脚本。

---

## Final Report Requirements

实现完成后，需要输出：

* 修改了哪些文件；
* Lefthook 最终使用的 npm 包名和版本；
* `make install` 是否成功；
* `lefthook run pre-commit` 是否成功；
* `lefthook run pre-push` 是否成功；
* `make check` 是否成功；
* 普通 `git commit` 是否能触发 `pre-commit`；
* 普通 `git push` 是否能触发 `pre-push`；
* `git commit --no-verify` 是否能绕过；
* `git push --no-verify` 是否能绕过；
* 测试提交或临时分支是否已清理；
* 如果有失败，说明失败原因和下一步建议。
