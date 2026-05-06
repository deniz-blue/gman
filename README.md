# gman (coursework)

Small CLI tool for doing batch operations with cloned git repositories.

**Problem**: If you have too many repositories, it's a hassle to work with all of them. `gman` allows you to do batch operations like fetching, status checks, or running arbitrary commands across one or many cloned repositories.

**Technologies**: Python

**OOP Principles**:

- Encapsulation: repository discovery, git execution, output formatting, and CLI orchestration live in separate modules.
- Abstraction: the CLI talks to high-level models and printer interfaces instead of raw subprocess or formatting details.
- Polymorphism: output backends and selector operators share common interfaces and are swapped at runtime.
- Single Responsibility: each class focuses on one concern, such as config loading, git execution, sorting/filtering, or rendering output.

**Design Patterns**:

- Strategy: output formatters and selector operators are selected at runtime based on CLI arguments.
- Factory: `create_output_printer()` and the `from_args()` selector constructors build the right implementation for each command.
- Singleton: `GitCommandExecutor` keeps a single shared executor instance.
- Template-style composition: CLI commands build pipelines from reusable filters, sorts, and limits.

**Testing**:

- The test suite uses Python's built-in `unittest` framework.
- CLI tests cover repository listing, filtering, sorting, output formats, `fetch`, `run`, and `clone` behavior.
- Core tests create temporary git repositories to verify discovery, status inspection, nested repo handling, and clone destination rendering.
- Tests rely on real local git commands inside temporary directories, so they exercise the same subprocess-driven paths as the application.

**Team**:
- **Deniz**: Development
- **Stanislav**: Testing and Documentation
- **Dilara**: Presentation Slides

## Class Diagrams

```mermaid
classDiagram
  class AppConfig {
    +list~Path~ watched_roots
    +list~str~ ignore_patterns
    +str default_remote_name
    +str clone_into
    +load(config_path)
    +repositories()
    +clone_destination(remote)
  }

  class Repository {
    +Path path
    +str display_name
    +name
    +status()
    +fetch(remote_name)
  }

  class RepositoryStatus {
    +Repository repository
    +str current_branch
    +str head_sha
    +str tracking_branch
    +int ahead_count
    +int behind_count
    +bool is_dirty
    +bool is_detached_head
    +datetime last_commit_date
    +is_up_to_date
  }

  class FetchResult {
    +Repository repository
    +bool success
    +str error_message
    +int duration_ms
    +tuple updated_refs
  }

  class RunResult {
    +Repository repository
    +str command
    +bool success
    +int exit_code
    +int duration_ms
    +str stdout
    +str stderr
  }

  class GitCommandExecutor {
    +run(repo_path, args)
    +is_repository(path)
    +current_branch(repo_path)
    +head_sha(repo_path)
    +tracking_branch(repo_path)
    +ahead_behind(repo_path, tracking_branch)
    +is_dirty(repo_path)
    +last_commit_date(repo_path)
    +remote_url(repo_path, remote_name)
    +fetch(repo_path, remote_name)
    +clone(remote, destination)
  }

  class OutputPrinter {
    <<abstract>>
    +print_repositories(repositories)
    +print_status_rows(rows)
    +print_fetch_results(results)
    +print_clone_result(remote, destination)
    +print_before_run(repository)
    +print_after_run(result)
    +finalize_run(results)
  }

  class PrettyPrinter
  class JsonPrinter
  class WhitespacePrinter

  class StatusRow {
    +Repository repository
    +RepositoryStatus status
  }

  class SequenceOperator~T~ {
    <<abstract>>
    +apply(items)
  }

  class RepositoryOperator {
    <<abstract>>
  }

  class StatusOperator {
    <<abstract>>
  }

  class NameContainsFilter
  class PathContainsFilter
  class UnderRootsFilter
  class DirtyFilter
  class UpToDateFilter
  class RepositorySort {
    <<abstract>>
  }
  class StatusSort {
    <<abstract>>
  }
  class RepositoryPathSort
  class RepositoryNameSort
  class StatusPathSort
  class StatusNameSort
  class StatusBranchSort
  class StatusAheadSort
  class StatusBehindSort
  class LimitFilter~T~

  AppConfig --> Repository : discovers
  Repository --> RepositoryStatus : builds
  Repository --> FetchResult : returns
  Repository --> RunResult : returns
  RepositoryStatus --> GitCommandExecutor : queries
  Repository --> GitCommandExecutor : fetch/status
  AppConfig --> GitCommandExecutor : clone destination
  GitCommandExecutor --> OutputPrinter : invoked by CLI
  OutputPrinter <|-- PrettyPrinter
  OutputPrinter <|-- JsonPrinter
  OutputPrinter <|-- WhitespacePrinter
  SequenceOperator <|-- RepositoryOperator
  SequenceOperator <|-- StatusOperator
  SequenceOperator <|-- LimitFilter
  RepositoryOperator <|-- RepositorySort
  StatusOperator <|-- StatusSort
  RepositorySort <|-- RepositoryPathSort
  RepositorySort <|-- RepositoryNameSort
  StatusSort <|-- StatusPathSort
  StatusSort <|-- StatusNameSort
  StatusSort <|-- StatusBranchSort
  StatusSort <|-- StatusAheadSort
  StatusSort <|-- StatusBehindSort
  RepositoryOperator <|-- NameContainsFilter
  RepositoryOperator <|-- PathContainsFilter
  RepositoryOperator <|-- UnderRootsFilter
  StatusOperator <|-- DirtyFilter
  StatusOperator <|-- UpToDateFilter
  StatusRow --> Repository
  StatusRow --> RepositoryStatus
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
> We do not like Python. Sorry.
