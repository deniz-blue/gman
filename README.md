# gman

Small CLI tool for doing batch operations with cloned git repositories.

**Problem**: If you have too many repositories, it's a hassle to work with all of them. `gman` allows you to do batch operations like fetching, status checks, or running arbitrary commands across one or many cloned repositories.

**Technologies**: Python

**OOP Principles**: <fill>

**Design Patterns**: <fill>

**Team**:
- **Deniz**: Development
- **Stanislav**: Testing and Documentation
- **Dilara**: Presentation Slides

## Class Diagrams

```mermaid
<fill>
```

## Installation

```bash
git clone https://github.com/deniz-blue/gman.git
cd gman
pipx install .
```

## Commands

- `gman list` lists discovered repositories
  - `--status`/`-S` includes remote tracking status (ahead/behind)
  - `--dirty`/`-D` includes dirty status (uncommitted changes)
  - `--clean`/`-u` includes clean status (no uncommitted changes)
  - `--show-path`/`-P` includes a path column in `pretty` output
- `gman run <command>` runs command in filtered repositories
  - `--fail-fast`/`-x` stops on first failure
  - `--pipe`/`-i` pipe commands to stdout
- `gman clone <remote> [post_clone_command]`
- `gman fetch` => alias for `gman run "git fetch"`

- **Global Options**
  - `--config <path>`/`-c <path>` specifies config file path
  - `--output <mode>`/`-o <mode>` selects output format:
    - `pretty` (default) - human-friendly table
    - `json` - machine-readable JSON
    - `whitespace` - space-separated values for scripting

- **Filters** for `list`, `run`, `fetch`:
  - `--name <text>`/`-n <text>` filters by repository name
  - `--path <text>`/`-p <text>` filters by repository path
  - `--root <path>`/`-r <path>` filters to repositories under specific roots (repeatable)

- **Sorting and Limiting** for `list`, `run`, `fetch`:
  - `--sort <key>`/`-s <key>` sorts rows by command-specific key
  - `--limit <n>`/`-l <n>` limits the number of printed rows
  - `--desc`/`-d` reverses sort order

Examples:

- `gman -c ~/.config/gman/config.json list -n work -s name`
- `gman list -S -D -s behind -d`
- `gman -o json list`
- `gman -o pretty -P list`
- `gman -o whitespace fetch`
- `gman run -n work "git status --short"`
- `gman run -i "echo hello"`
- `gman run -x "./scripts/check.sh"`
- `gman clone git@github.com:owner/repo.git "uv sync && uv run pytest"`

## Configuration

The default config file lives at `~/.config/gman/config.json` unless `XDG_CONFIG_HOME` is set.

Expected fields:

- `watched_roots` - list of directories to scan for local repositories.
- `ignore_patterns` - simple glob patterns to skip matching paths.
- `default_remote_name` - remote name used for fetch and remote checks.
- `cloneInto` - destination template for new clones (default: `~/Source/Repos/{owner}/{name}`).

`cloneInto` template variables:

- `{host}` - remote host, for example `github.com`.
- `{owner}` - first path segment after host, usually org/user.
- `{name}` - repository name without `.git`.
- `{path}` - remote path without leading slash.
- `{remote}` - normalized remote identifier.

> [!NOTE]
> This project was developed with AI assistance.
> Parts of the code, tests, and documentation were generated or refined with help from AI tooling and then reviewed.
