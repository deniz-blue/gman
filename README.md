# gman

`gman` is a small CLI for managing locally cloned Git repositories.

## Commands

- `gman list` lists discovered repositories
- `gman list --status` (or `gman list -S`) prints repository status details
- `gman fetch` fetches all discovered repositories from their configured remote (implemented via `gman run` internally)
- `gman run <command>` runs a shell command in filtered repositories
- `gman clone <remote> [post_clone_command]` clones into the configured path template and can run a command in the cloned directory

`run` options:

- `--fail-fast` / `-x` stops after the first repository command failure.
- `--pipe` / `-i` streams each repository command stdout to terminal.

### Filtering and sorting

Most commands support these shared selectors (simpler names first):

- `-n`, `--name <text>` filters by repository name.
- `-p`, `--path <text>` filters by repository path.
- `-r`, `--root <path>` filters to repositories under specific roots (repeatable).
- `-s`, `--sort <key>` sorts rows by command-specific key.
- `-d`, `--desc` reverses sort order.
- `-l`, `--limit <n>` limits the number of printed rows.
- `-o`, `--output <pretty|json|whitespace>` selects output formatting mode.
- `-P`, `--show-path` includes a path column in `pretty` output.
- `-c`, `--config <path>` sets config file path.

Additional command-specific filters:

- `list`: `-S`, `--status`; `-D`, `--dirty` (alias: `--dirty-only`); `-u`, `--clean` (alias: `--up-to-date-only`)
- `list`: `-S`, `--status`; `-D`, `--dirty`; `-u`, `--clean`

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

Output modes:

- `pretty` - human-readable table output with terminal colors when supported. Shows repository directory names by default; use `--show-path` to include paths.
- `json` - structured JSON output for machine consumption.
- `whitespace` - tab-separated output for shell scripting pipelines.

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
