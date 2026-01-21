# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **IMPORTANT**: When adding or modifying features, always update [README.md](README.md) to keep documentation in sync with code changes.

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

- **global**: Error handling strategy, log directory, Git token, source branch, and execution control
  - `on_error`: "continue" or "stop" - error handling strategy
  - `log_dir`: directory for log files
  - `log_level`: logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  - `git_token`: Git access token (can reference env var as `${GIT_TOKEN}`)
  - `source_branch`: source branch to clone/pull from (default: "main")
  - `branch_exists_strategy`: how to handle existing personal branches
    - "checkout": checkout the existing remote branch (default)
    - "recreate": delete local branch and create new from source
    - "reset": checkout branch and reset to source branch
  - `show_command_output`: whether to display command output (default: true)
  - `command_scope`: where to execute commands
    - "repo": execute in each repository's root directory (default)
    - "parent": execute once in the parent directory of all repos
  - `execute_clone`: whether to execute clone/pull step (default: true)
  - `execute_branch`: whether to execute branch creation step (default: true)
  - `execute_replacements`: whether to execute code replacements (default: true)
  - `execute_commands`: whether to execute custom commands (default: true)
  - `execute_commit`: whether to execute commit/push step (default: true)

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

## Recent Enhancements

### 1. UTF-8 Command Execution
All shell commands now execute with UTF-8 encoding and error replacement for compatibility.

### 2. Replacement Rule Statistics (Enhanced)
The `CodeModifier` now tracks and reports:
- Number of repositories with actual modifications (excluding zero-match)
- Number of zero-match repositories for each rule
- Total replacement count (not just file count)
- Per-repository replacement counts
- Summary statistics after processing all repositories
- Warning for rules that matched nothing across all repos

### 3. Step Execution Control
You can now selectively disable execution steps using the `execution` config entity:
- Set `clone`, `branch`, `replacements`, `commands`, or `commit` to `false` to skip those steps
- Useful for testing or running partial workflows
- Old format (in `global`) is still supported for backward compatibility

### 4. Branch Existence Handling
When a personal branch already exists locally or remotely:
- `checkout`: Checkout the existing branch (default)
- `recreate`: Delete and recreate from source branch
- `reset`: Reset existing branch to source branch

### 5. Command Output Visibility
- `show_command_output` controls whether command stdout/stderr is displayed
- Output is shown line-by-line with INFO/WARNING levels
- Includes line count for easy review

### 6. Command-Level Scope Configuration
Commands now support per-command `scope` configuration:

**Old format (still supported)**:
```json
"commands": ["npm install", "npm run build"]
```
Default behavior: executes in each repository

**New format (recommended)**:
```json
"commands": [
  {"command": "npm install", "scope": "repo"},
  {"command": "docker-compose build", "scope": "parent"}
]
```

| scope | Behavior | Execution Timing |
|-------|----------|------------------|
| `repo` | Execute in each repository's root directory | During each repo processing |
| `parent` | Execute once in parent directory | After all repos processed |

**Execution flow**:
1. Process all repositories (clone → branch → replacements → repo commands → commit)
2. Execute parent-scope commands once

### 7. Git Account Configuration
Added `git_account` global config for Git token authentication:
- When configured: `https://account:token@github.com/...`
- When not configured: `https://token@github.com/...`

### 8. All subprocess.run UTF-8 Encoding
All `subprocess.run()` calls now include `encoding='utf-8'` and `errors='replace'` parameters:
- Git operations (clone, pull, checkout, branch, push, etc.)
- Command execution
- Remote/local branch existence checks
- Ensures proper handling of Chinese and other non-ASCII characters

## Usage Scenarios

### Scenario 1: Batch Update Dependencies
```json
{
  "global": {"source_branch": "main"},
  "repositories": [
    {"name": "frontend", "url": "..."},
    {"name": "backend", "url": "..."}
  ],
  "personal_branch": "update/deps-v2.0",
  "replacements": [
    {
      "search": "\"react\": \".*?\"",
      "replace": "\"react\": \"^18.0.0\"",
      "is_regex": true,
      "include_extensions": [".json"]
    }
  ],
  "commands": ["npm install", "npm run build"]
}
```

### Scenario 2: Code Modifications Only (Skip Commands/Commit)
```json
{
  "global": {
    "execute_commands": false,
    "execute_commit": false,
    "show_command_output": true
  },
  "replacements": [
    {
      "search": "Copyright 2023",
      "replace": "Copyright 2024",
      "exclude_patterns": ["node_modules/*", "*.min.js"]
    }
  ]
}
```

### Scenario 3: Mixed Command Execution (Repo + Parent Scope)
```json
{
  "global": {
    "execute_replacements": false,
    "execute_commit": false
  },
  "commands": [
    {"command": "npm install", "scope": "repo"},
    {"command": "npm test", "scope": "repo"},
    {"command": "docker-compose build", "scope": "parent"},
    {"command": "docker-compose up -d", "scope": "parent"}
  ]
}
```

Note: `npm install` and `npm test` execute in each repo; `docker-compose` commands execute once in parent directory.

### Scenario 4: Recreate Existing Branch
```json
{
  "global": {
    "branch_exists_strategy": "recreate"
  },
  "personal_branch": "feature/daily-update"
}
```

### Scenario 5: Commands Only (No Code Changes)
```json
{
  "global": {
    "show_command_output": true
  },
  "execution": {
    "replacements": false,
    "commit": false
  },
  "commands": [
    "python -m pytest tests/",
    "python -m mypy ."
  ]
}
```

### Scenario 6: Skip Clone Step (Local Code Already Exists)
```json
{
  "execution": {
    "clone": false,
    "branch": false
  },
  "personal_branch": "current-branch"
}
```

## Log Output Examples

### Replacement Statistics Summary
```
============================================================
替换规则执行统计汇总
============================================================
规则 #1:
  - 成功修改仓库: 3 个
  - 零匹配仓库: 2 个
  - 修改文件数: 15
  - 替换总次数: 42
规则 #2:
  - 成功修改仓库: 5 个
  - 修改文件数: 23
  - 替换总次数: 87
------------------------------------------------------------
总计: 修改 38 个文件，共 129 处替换
============================================================
```

### Anomaly Detection
If a rule matched nothing across all repositories:
```
============================================================
警告: 以下规则在所有仓库中均未匹配到内容: [3]
请检查搜索字符串是否正确，或排除模式是否过于严格
============================================================
```

## File Exclusion Pattern Reference

| Pattern | Matches | Description |
|---------|---------|-------------|
| `*_test.py` | `foo_test.py` | Files ending with `_test.py` |
| `node_modules/*` | `node_modules/pkg/index.js` | Files under `node_modules/` |
| `*.min.js` | `app.min.js` | Minified JS files |
| `tests/**/*.py` | `tests/unit/test.py` | All `.py` files under tests/ |
| `dist/**` | `dist/a/b/c.js` | All files recursively under dist/ |
| `*.py` | All `.py` files | Match specific extension |

## Commit Message Placeholders

| Placeholder | Description | Example |
|-------------|-------------|---------|
| `{repo_name}` | Repository name | `my-project` |
| `{date}` | Date (YYYY-MM-DD) | `2024-01-15` |
| `{datetime}` | Full datetime | `2024-01-15 14:30:00` |
| `{timestamp}` | Unix timestamp | `1705300200` |
| `{replacement_count}` | Number of replacement rules | `3` |
| `{command_count}` | Number of commands | `2` |
| `{variable_name}` | Custom variable from `commit.variables` | - |

Example:
```json
{
  "commit": {
    "message": "Batch update: {task_id}\n\n- Applied {replacement_count} replacement rules\n- Executed {command_count} build commands\n- Automated commit on {date}",
    "variables": {
      "task_id": "TASK-1234"
    }
  }
}
```
