# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

BatchGitOps is a Python CLI tool for batch-managing multiple Git repositories. It automates cloning/pulling, branch creation, code replacements (string/regex), command execution, and commit/push operations across multiple repositories simultaneously.

## Running the Tool

```bash
# Run with default config.json
python batch_repo_manager.py

# Run with custom config
python batch_repo_manager.py /path/to/custom-config.json
```

## Architecture

The codebase is organized into modular classes in `batch_repo_manager.py`:

| Class | Responsibility |
|-------|---------------|
| `LogManager` | Initializes logging to file and console with timestamps |
| `ConfigLoader` | Parses JSON config, expands environment variables (`${VAR_NAME}`), validates required fields |
| `GitOperations` | All Git operations (clone/pull, checkout, branch creation, commit, push, token injection) |
| `CodeModifier` | Applies search/replace rules across files (supports regex, file filtering) |
| `CommandExecutor` | Executes shell commands in repo directories with timeout handling |
| `BatchRepoManager` | Orchestrates the full workflow |

### Execution Flow

```
BatchRepoManager.run()
  ├─ _load_config()        # Load and validate config.json
  ├─ _init_components()    # Initialize all modules (logging, git, etc.)
  └─ For each repo in config:
      ├─ clone_or_pull()              # Clone or fetch latest
      ├─ create_personal_branch()     # Create branch from source
      ├─ apply_replacements()         # Apply code modifications
      ├─ execute_in_repo()            # Run custom commands
      └─ commit_and_push()            # Commit and push changes
```

**Important:** `_load_config()` runs before logging is initialized, so it cannot use `self.logger`.

## Configuration

The `config.json` file defines:

- **global**: Error handling strategy, log directory, Git token, source branch
- **repositories**: List of repos with `name` (local dir) and `url`
- **personal_branch**: Target branch name to create
- **replacements**: Search/replace rules with `search`, `replace`, `is_regex`, `include_extensions`, `exclude_patterns`
- **commands**: Shell commands to run in each repo
- **commit**: Message template with placeholders (supports `{repo_name}`, `{date}`, `{datetime}`, `{timestamp}`, `{replacement_count}`, `{command_count}`, and custom variables)

Environment variables are loaded from `.env` file and referenced in config as `${VAR_NAME}`.

## Important Implementation Details

- **File encoding**: All files are read/written as UTF-8. Binary files (images, etc.) will fail gracefully with warnings
- **Git token injection**: Tokens are injected into HTTPS URLs for authentication: `https://token@github.com/user/repo.git`
- **Command timeout**: Commands have a 5-minute timeout (hardcoded in `execute_single_command`)
- **Error handling**: Controlled by `global.on_error` - "continue" skips to next repo, "stop" aborts entirely
- **Working directory**: Repos are cloned to `repos/<name>/` relative to config file location
- **Logging**: Log files are created as `logs/batchgitops_YYYYMMDD_HHMMSS.log`

## File Exclusion Patterns

The `exclude_patterns` in replacement rules uses `fnmatch` for wildcard matching:
- `*_test.py` matches files ending with `_test.py`
- `node_modules/*` matches paths under `node_modules/`
- Full paths are matched, not just filenames (except when the pattern contains no `/`)
