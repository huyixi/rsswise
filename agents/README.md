# Coding Agents

This directory provides a centralized location for files related to AI coding agents used for development within the RSSWise source tree.

The goal is to provide a scalable and organized way to maintain prompts, task-specific skills, reusable commands, and optional tool configurations across local development, deployment, and future collaboration.

## Directory Structure

### Prompts

Shared agent instructions and prompt templates. See [`//agents/prompts/README.md`].

[`//agents/prompts/README.md`]: /agents/prompts/README.md

### Extensions & MCP Servers

Optional MCP server configurations and extension setup notes can be added here when needed.

### Skills

On-demand expertise for specific development tasks, such as code review, debugging, database migrations, deployment, and AI feature implementation. See [`//agents/skills/README.md`].

[`//agents/skills/README.md`]: /agents/skills/README.md

### Custom Commands

Reusable command prompts for coding agents. See [`//agents/commands/README.md`].

[`//agents/commands/README.md`]: /agents/commands/README.md

## Contributing

Add self-contained task prompts, prompt templates, skills, and commands that match the format of the existing examples.

Changes to common agent instructions should be made carefully, because they may affect many coding-agent workflows.

