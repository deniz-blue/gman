# gman

`gman` is a small CLI for managing locally cloned Git repositories.

## Commands

- `gman list` lists discovered repositories
- `gman list --status` prints repository status details
- `gman fetch` fetches all discovered repositories from their configured remote
- `gman clone <remote> [post_clone_command]` clones into the configured path template and can run a command in the cloned directory

### Filtering and sorting

Most commands support these shared selectors:

- `--name-contains <text>` filters by repository name.
- `--path-contains <text>` filters by repository path.
- `--under-root <path>` filters to repositories under specific roots (repeatable).
- `--sort-by <key>` sorts rows by command-specific key.
- `--descending` reverses sort order.
- `--limit <n>` limits the number of printed rows.

Additional command-specific filters:

- `list`: `--status`, `--dirty-only`, `--up-to-date-only`

Examples:

- `gman list --name-contains work --sort-by name`
- `gman list --status --dirty-only --sort-by behind --descending`
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
