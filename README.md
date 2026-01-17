# BatchGitOps

批量Git仓库操作工具 - 一个Python命令行工具，用于批量管理多个Git代码仓库，支持批量拉取代码、创建分支、修改代码、执行命令和提交推送。

## 功能特性

- **批量拉取代码**：自动克隆或更新多个代码仓库
- **批量创建分支**：从源分支批量创建个人分支
- **批量修改代码**：支持字符串替换和正则表达式替换
- **批量执行命令**：在各仓库根目录执行配置好的命令
- **批量提交推送**：自动提交并推送更改到远程仓库
- **详细日志记录**：生成带时间戳的日志文件

## 安装

### 1. 克隆或下载本项目

```bash
cd batch-gitops
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

## 配置

编辑 `config.json` 文件配置你的项目：

```json
{
  "global": {
    "on_error": "continue",
    "log_dir": "./logs",
    "log_level": "INFO",
    "git_token": "${GIT_TOKEN}",
    "source_branch": "main"
  },
  "repositories": [
    {
      "name": "repo1",
      "url": "https://github.com/user/repo1.git"
    },
    {
      "name": "repo2",
      "url": "https://github.com/user/repo2.git"
    }
  ],
  "personal_branch": "feature/batch-update",
  "replacements": [
    {
      "search": "old_string",
      "replace": "new_string",
      "is_regex": false,
      "include_extensions": [".py", ".js", ".ts"],
      "exclude_patterns": ["*_test.py", "node_modules/*"]
    }
  ],
  "commands": [
    "pip install -r requirements.txt",
    "pytest"
  ],
  "commit": {
    "message": "Batch update: {task_id}\n\n- Applied {replacement_count} replacement rules\n- Executed {command_count} build commands\n\nCo-Authored-By: Batch Tool <noreply@tool.com>",
    "variables": {
      "task_id": "TASK-1234"
    }
  }
}
```

## 环境变量

创建 `.env` 文件设置敏感信息：

```bash
GIT_TOKEN=your_git_token_here
```

## 使用方法

### 基本用法

```bash
python batch_repo_manager.py
```

### 指定配置文件

```bash
python batch_repo_manager.py /path/to/custom-config.json
```

## 配置说明

### 全局配置 (global)

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| on_error | string | 否 | 错误处理策略: "continue" 或 "stop"，默认 "continue" |
| log_dir | string | 否 | 日志目录，默认 "./logs" |
| log_level | string | 否 | 日志级别，默认 "INFO" |
| git_token | string | 否 | Git token（支持环境变量 ${GIT_TOKEN}） |
| source_branch | string | 否 | 所有仓库的源分支，默认 "main" |

### 仓库配置 (repositories)

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| name | string | 是 | 仓库名称，用作本地目录名 |
| url | string | 是 | Git仓库HTTPS URL |

### 个人分支配置 (personal_branch)

直接指定分支名称字符串，例如：
- `"feature/batch-update"`
- `"hotfix/fix-20240117"`
- `"dev/test-branch"`

### 代码替换规则 (replacements)

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| search | string | 是 | 搜索字符串或正则表达式 |
| replace | string | 是 | 替换字符串 |
| is_regex | boolean | 否 | 是否使用正则表达式，默认 false |
| include_extensions | list | 否 | 包含的文件扩展名，空列表表示全部 |
| exclude_patterns | list | 否 | 排除的文件模式（支持通配符） |

### 提交信息模板 (commit.message)

支持的占位符：
- `{repo_name}` - 仓库名称
- `{date}` - 日期
- `{datetime}` - 日期时间
- `{timestamp}` - Unix时间戳
- `{replacement_count}` - 替换规则数量
- `{command_count}` - 命令数量
- 自定义变量（在 `commit.variables` 中定义）

**注意**：JSON中换行符使用 `\n`，例如：
```json
"message": "第一行\n\n第二行\n\n第三行"
```

## 输出

程序会在以下位置生成文件：

- **日志文件**: `logs/batch_repo_YYYYMMDD_HHMMSS.log`
- **代码仓库**: `repos/<仓库名>/`

## 工作流程

```
1. 加载配置文件
   └── 解析JSON配置，展开环境变量

2. 初始化日志系统
   └── 创建日志目录和日志文件

3. 遍历每个仓库：
   ├─ 克隆或拉取最新代码
   ├─ 从全局配置的源分支创建个人分支
   ├─ 应用代码替换规则
   ├─ 执行自定义命令
   └─ 提交并推送更改

4. 输出执行总结
```

## 错误处理

根据 `global.on_error` 配置：
- `continue`: 遇到错误继续处理下一个仓库
- `stop`: 遇到错误立即停止

## 示例

### 示例1: 批量更新Python项目

```json
{
  "global": {
    "source_branch": "main"
  },
  "repositories": [
    {
      "name": "project1",
      "url": "https://github.com/user/project1.git"
    }
  ],
  "personal_branch": "feature/logging-refactor",
  "replacements": [
    {
      "search": "print(",
      "replace": "logger.info(",
      "is_regex": false,
      "include_extensions": [".py"],
      "exclude_patterns": ["*_test.py"]
    }
  ],
  "commands": [
    "python -m pytest tests/"
  ],
  "commit": {
    "message": "Refactor: Replace print with logging\n\n- Replaced print statements\n- Ran pytest for verification"
  }
}
```

### 示例2: 使用正则表达式批量替换

```json
{
  "replacements": [
    {
      "search": "\\bvar\\s+(\\w+)\\s*=",
      "replace": "const \\1 =",
      "is_regex": true,
      "include_extensions": [".js", ".ts"],
      "exclude_patterns": ["node_modules/*", "dist/*"]
    }
  ]
}
```

## 注意事项

1. **Git Token**: 使用HTTPS URL时，建议配置Git token以避免密码输入
2. **文件编码**: 程序假设所有文件使用UTF-8编码
3. **正则表达式**: JSON字符串中需要使用双反斜杠 `\\` 转义
4. **换行符**: JSON中换行符使用 `\n` 而不是实际换行
5. **备份**: 建议在执行前备份重要代码
6. **测试**: 先在测试仓库验证配置

## 故障排除

### 问题1: 克隆失败

```
错误: 克隆失败: fatal: Authentication failed
```

解决方案：配置正确的 `GIT_TOKEN` 环境变量

### 问题2: 分支已存在

```
错误: 创建分支失败: fatal: A branch named 'xxx' already exists
```

解决方案：删除本地和远程的已存在分支，或修改 `personal_branch` 配置

### 问题3: 命令执行超时

```
错误: 命令执行超时: pytest
```

解决方案：代码中默认超时为5分钟，可根据需要修改 `timeout` 参数

### 问题4: JSON解析错误

```
错误: Expecting property name enclosed in double quotes
```

解决方案：确保JSON格式正确，使用双引号，正确的转义字符

## 许可证

MIT License

Copyright (c) 2025 BatchGitOps
