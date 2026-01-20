# BatchGitOps

批量 Git 仓库操作工具 - 支持批量拉取代码、创建分支、修改代码、执行命令、提交推送

## 功能特性

- **批量仓库管理**: 同时操作多个 Git 仓库
- **代码批量替换**: 支持字符串和正则表达式替换
- **自定义命令执行**: 在每个仓库中执行自定义 Shell 命令
- **自动化提交**: 自动提交并推送更改到远程仓库
- **灵活的执行控制**: 可选择性地跳过某些执行步骤
- **彩色日志输出**: 清晰区分不同级别的日志信息
- **详细的统计报告**: 查看每个替换规则影响的仓库和文件数量
- **UTF-8 编码支持**: 正确处理中文等非 ASCII 字符

## 安装

### 要求

- Python 3.7+
- Git

### 依赖安装

```bash
pip install python-dotenv
```

## 快速开始

1. **创建配置文件** `config.json`:

```json
{
  "global": {
    "on_error": "continue",
    "log_dir": "./logs",
    "log_level": "INFO",
    "git_token": "${GIT_TOKEN}",
    "source_branch": "main"
  },
  "execution": {
    "clone": true,
    "branch": true,
    "replacements": true,
    "commands": true,
    "commit": true
  },
  "repositories": [
    {
      "name": "my-project",
      "url": "https://github.com/username/my-project.git"
    }
  ],
  "personal_branch": "feature/batch-update",
  "replacements": [],
  "commands": [],
  "commit": {
    "message": "Batch update: {date}",
    "variables": {}
  }
}
```

2. **运行工具**:

```bash
python batch_repo_manager.py
```

---

## 配置说明

### global - 全局配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `on_error` | string | "continue" | 错误处理策略：<br>- `"continue"`: 遇到错误继续处理下一个仓库<br>- `"stop"`: 遇到错误停止执行 |
| `log_dir` | string | "./logs" | 日志文件目录 |
| `log_level` | string | "INFO" | 日志级别：<br>- `"DEBUG"`: 详细调试信息<br>- `"INFO"`: 一般信息<br>- `"WARNING"`: 警告信息<br>- `"ERROR"`: 错误信息<br>- `"CRITICAL"`: 严重错误 |
| `git_token` | string | - | Git 访问令牌，支持环境变量引用如 `${GIT_TOKEN}` |
| `source_branch` | string | "main" | 源分支名称，用于克隆和创建个人分支 |
| `branch_exists_strategy` | string | "checkout" | 个人分支已存在时的处理策略：<br>- `"checkout"`: 直接检出远程已存在的分支<br>- `"recreate"`: 删除本地分支并重新创建<br>- `"reset"`: 检出分支并重置到源分支 |
| `show_command_output` | boolean | true | 是否显示命令执行的输出内容 |

**配置示例**:

```json
{
  "global": {
    "on_error": "continue",
    "log_dir": "./logs",
    "log_level": "INFO",
    "git_token": "${GIT_TOKEN}",
    "source_branch": "main",
    "branch_exists_strategy": "checkout",
    "show_command_output": true
  }
}
```

---

### execution - 执行步骤配置

控制各个执行步骤是否启用。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `clone` | boolean | true | 是否执行克隆/拉取步骤 |
| `branch` | boolean | true | 是否执行分支创建步骤 |
| `replacements` | boolean | true | 是否执行代码替换步骤 |
| `commands` | boolean | true | 是否执行自定义命令步骤 |
| `commit` | boolean | true | 是否执行提交/推送步骤 |

**配置示例**:

```json
{
  "execution": {
    "clone": true,
    "branch": true,
    "replacements": true,
    "commands": true,
    "commit": true
  }
}
```

> **注意**: 旧配置格式（在 `global` 中使用 `execute_clone` 等）仍然支持，但推荐使用新的 `execution` 实体。

---

### repositories - 仓库列表

数组，每个元素包含：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 是 | 仓库名称，将作为本地目录名 |
| `url` | string | 是 | 仓库的 Git URL |

**示例**:

```json
"repositories": [
  {
    "name": "project-a",
    "url": "https://github.com/username/project-a.git"
  },
  {
    "name": "project-b",
    "url": "git@github.com:username/project-b.git"
  }
]
```

---

### personal_branch - 个人分支名称

要创建的分支名称。

**示例**:

```json
"personal_branch": "feature/my-changes"
```

---

### replacements - 替换规则列表

数组，每个元素是一个替换规则：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `search` | string | 是 | 要搜索的字符串或正则表达式 |
| `replace` | string | 是 | 替换字符串 |
| `is_regex` | boolean | 否 | 是否使用正则表达式（默认 false） |
| `include_extensions` | array | 否 | 只处理指定扩展名的文件（空数组表示全部） |
| `exclude_patterns` | array | 否 | 排除的文件模式列表，支持通配符 |

**示例**:

```json
"replacements": [
  {
    "search": "oldFunction",
    "replace": "newFunction",
    "is_regex": false,
    "include_extensions": [".js", ".ts"],
    "exclude_patterns": ["*_test.js", "node_modules/*", "*.min.js"]
  },
  {
    "search": "TODO:\\s*\\d+",
    "replace": "TODO: 2024-01-01",
    "is_regex": true,
    "include_extensions": [".md", ".txt"],
    "exclude_patterns": []
  }
]
```

---

### commands - 自定义命令列表

要在仓库中执行的 Shell 命令数组。支持两种格式：

#### 格式 1：字符串数组（旧格式，兼容）

```json
"commands": [
  "npm install",
  "npm run build"
]
```

字符串格式的命令默认在每个仓库根目录执行（`scope="repo"`）。

#### 格式 2：对象数组（新格式，推荐）

```json
"commands": [
  {
    "command": "npm install",
    "scope": "repo"
  },
  {
    "command": "docker-compose build",
    "scope": "parent"
  }
]
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `command` | string | 是 | 要执行的 Shell 命令 |
| `scope` | string | 否 | 执行范围：`"repo"`（每个仓库）或 `"parent"`（父目录一次），默认 `"repo"` |

**执行范围说明**:

| scope 值 | 执行位置 | 执行时机 |
|----------|----------|----------|
| `repo` | 每个仓库根目录 | 每个仓库处理时执行 |
| `parent` | 所有仓库的父目录 | 所有仓库处理完后执行一次 |

**示例**:

```json
"commands": [
  {
    "command": "npm install",
    "scope": "repo"
  },
  {
    "command": "npm run build",
    "scope": "repo"
  },
  {
    "command": "docker-compose up -d",
    "scope": "parent"
  }
]
```

---

### commit - 提交配置

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `message` | string | 是 | 提交信息模板 |
| `variables` | object | 否 | 自定义变量，可在 message 中引用 |

**支持的占位符**:

| 占位符 | 说明 | 示例 |
|--------|------|------|
| `{repo_name}` | 仓库名称 | `my-project` |
| `{date}` | 日期（YYYY-MM-DD） | `2024-01-15` |
| `{datetime}` | 日期时间 | `2024-01-15 14:30:00` |
| `{timestamp}` | Unix 时间戳 | `1705300200` |
| `{replacement_count}` | 替换规则数量 | `3` |
| `{command_count}` | 命令数量 | `2` |
| `{变量名}` | 自定义变量 | - |

**示例**:

```json
"commit": {
  "message": "Batch update: {task_id}\n\n- Applied {replacement_count} replacement rules\n- Executed {command_count} build commands\n- Automated commit on {date}\n\nCo-Authored-By: Batch Tool <noreply@tool.com>",
  "variables": {
    "task_id": "TASK-1234"
  }
}
```

---

## 使用场景

### 场景 1: 批量更新依赖版本

```json
{
  "global": {
    "on_error": "continue",
    "source_branch": "main"
  },
  "repositories": [
    {"name": "frontend", "url": "https://github.com/company/frontend.git"},
    {"name": "backend", "url": "https://github.com/company/backend.git"}
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
  "commands": ["npm install", "npm run build"],
  "commit": {
    "message": "chore: update React to v18.0.0\n\n- Update dependency across all projects\n- Run npm install and build\n\nAutomated on: {date}"
  }
}
```

### 场景 2: 修改代码注释（不执行命令和提交）

```json
{
  "global": {
    "show_command_output": true
  },
  "execution": {
    "commands": false,
    "commit": false
  },
  "repositories": [
    {"name": "project", "url": "https://github.com/user/project.git"}
  ],
  "personal_branch": "chore/update-copyright",
  "replacements": [
    {
      "search": "Copyright 2023",
      "replace": "Copyright 2024",
      "exclude_patterns": ["node_modules/*", "*.min.js"]
    }
  ],
  "commands": [],
  "commit": {
    "message": "chore: update copyright year to 2024"
  }
}
```

### 场景 3: 混合命令执行（仓库级 + 父级）

```json
{
  "execution": {
    "replacements": false,
    "commit": false
  },
  "repositories": [
    {"name": "service-a", "url": "..."},
    {"name": "service-b", "url": "..."}
  ],
  "personal_branch": "main",
  "commands": [
    {
      "command": "npm install",
      "scope": "repo"
    },
    {
      "command": "npm test",
      "scope": "repo"
    },
    {
      "command": "docker-compose build",
      "scope": "parent"
    },
    {
      "command": "docker-compose up -d",
      "scope": "parent"
    }
  ]
}
```

说明：
- `npm install` 和 `npm test` 会在每个仓库中执行
- `docker-compose build` 和 `docker-compose up -d` 只在父目录执行一次

### 场景 4: 分支已存在时重新创建

```json
{
  "global": {
    "branch_exists_strategy": "recreate"
  },
  "repositories": [...],
  "personal_branch": "feature/daily-update",
  "replacements": [...]
}
```

### 场景 5: 只执行命令，不做代码修改

```json
{
  "global": {
    "show_command_output": true
  },
  "execution": {
    "replacements": false,
    "commit": false
  },
  "repositories": [
    {"name": "project", "url": "..."}
  ],
  "personal_branch": "main",
  "commands": [
    "python -m pytest tests/",
    "python -m mypy ."
  ]
}
```

### 场景 6: 跳过克隆步骤（本地已有代码）

```json
{
  "execution": {
    "clone": false,
    "branch": false
  },
  "repositories": [
    {"name": "local-project", "url": "..."}
  ],
  "personal_branch": "current-branch",
  "replacements": [...]
}
```

---

## 日志输出

工具会产生两种日志：

1. **控制台输出** (带颜色):
   - DEBUG: 青色
   - INFO: 绿色
   - WARNING: 黄色
   - ERROR: 红色
   - CRITICAL: 紫色

2. **日志文件**: `logs/batchgitops_YYYYMMDD_HHMMSS.log`

### 替换规则统计示例

```
============================================================
替换规则执行统计汇总
============================================================
规则 #1:
  - 涉及代码仓: 5/5
  - 修改文件数: 23
规则 #2:
  - 涉及代码仓: 3/5
  - 修改文件数: 7
============================================================
```

---

## 环境变量

支持在配置文件中使用环境变量：

```json
{
  "global": {
    "git_token": "${GIT_TOKEN}"
  }
}
```

创建 `.env` 文件：

```bash
GIT_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```

---

## 文件排除模式

`exclude_patterns` 使用 `fnmatch` 风格的通配符：

| 模式 | 匹配 | 说明 |
|------|------|------|
| `*_test.py` | `foo_test.py` | 匹配以 `_test.py` 结尾的文件 |
| `node_modules/*` | `node_modules/pkg/index.js` | 匹配 `node_modules` 下的所有文件 |
| `*.min.js` | `app.min.js` | 匹配压缩的 JS 文件 |
| `tests/**/*.py` | `tests/unit/test.py` | 匹配 tests 目录下的所有 py 文件 |
| `dist/**` | `dist/a/b/c.js` | 递归匹配 dist 下的所有文件 |
| `*.py` | 所有 `.py` 文件 | 匹配指定扩展名的文件 |

---

## 命令行参数

```bash
# 使用默认配置 config.json
python batch_repo_manager.py

# 使用自定义配置文件
python batch_repo_manager.py /path/to/custom-config.json
```

---

## 注意事项

1. **编码**: 所有文件读写和命令执行都使用 UTF-8 编码
2. **超时**: 自定义命令有 5 分钟的超时限制
3. **二进制文件**: 二进制文件（图片等）会被跳过，不会尝试替换
4. **分支冲突**: 如果个人分支已存在，根据 `branch_exists_strategy` 策略处理
5. **工作目录**: 仓库会被克隆到配置文件所在目录的 `repos/` 子目录下
6. **正则表达式**: JSON 字符串中需要使用双反斜杠 `\\` 转义

---

## 故障排查

### 问题: Git token 认证失败

**解决方案**: 确保 `.env` 文件中的 `GIT_TOKEN` 有效，或在配置文件中直接设置。

### 问题: 替换没有生效

**解决方案**:
1. 检查 `exclude_patterns` 是否排除了目标文件
2. 检查 `include_extensions` 是否限制了文件类型
3. 将 `log_level` 设置为 `DEBUG` 查看详细信息

### 问题: 命令执行超时

**解决方案**: 命令执行超时为 5 分钟，如果需要更长时间，可以修改源代码中的 `timeout` 参数。

### 问题: 分支已存在报错

**解决方案**:
- 设置 `branch_exists_strategy` 为 `"checkout"` 直接检出已存在的分支
- 设置为 `"recreate"` 删除并重新创建
- 设置为 `"reset"` 重置到源分支

---

## 开发

### 项目结构

```
batch_repo_manager.py    # 主程序
config.json              # 配置文件示例
.env                     # 环境变量（需要自行创建）
logs/                    # 日志文件目录
repos/                   # 仓库克隆目录
```

### 代码架构

| 类 | 职责 |
|---|---|
| `ColorFormatter` | 彩色日志格式化器 |
| `LogManager` | 日志系统管理 |
| `ConfigLoader` | 配置加载和验证 |
| `GitOperations` | Git 操作封装 |
| `CodeModifier` | 代码替换执行 |
| `CommandExecutor` | 命令执行管理 |
| `BatchRepoManager` | 主流程协调 |

---

## 许可证

MIT License

---

## 贡献

欢迎提交 Issue 和 Pull Request！
