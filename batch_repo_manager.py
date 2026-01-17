#!/usr/bin/env python3
"""
BatchGitOps - 批量Git仓库操作工具
支持批量拉取代码、创建分支、修改代码、执行命令、提交推送
"""

import logging
import os
import re
import subprocess
import fnmatch
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import json
from dotenv import load_dotenv


# ============================================================================
# 日志管理模块
# ============================================================================

class LogManager:
    """日志管理器，负责初始化和配置日志系统"""

    def __init__(self, log_dir: str, log_level: str = "INFO"):
        """
        初始化日志管理器

        Args:
            log_dir: 日志文件目录
            log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.log_dir = Path(log_dir)
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self._setup()

    def _setup(self):
        """设置日志系统"""
        # 创建日志目录
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 生成日志文件名（带时间戳）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.log_dir / f"batchgitops_{timestamp}.log"

        # 配置根日志记录器
        logging.basicConfig(
            level=self.log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )

    def get_logger(self, name: str) -> logging.Logger:
        """
        获取命名日志记录器

        Args:
            name: 日志记录器名称

        Returns:
            配置好的日志记录器实例
        """
        return logging.getLogger(name)


# ============================================================================
# 配置加载模块
# ============================================================================

class ConfigLoader:
    """配置文件加载器，负责解析和验证JSON配置"""

    def __init__(self, config_path: str):
        """
        初始化配置加载器

        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def load(self) -> Dict[str, Any]:
        """
        加载并解析配置文件

        Returns:
            解析后的配置字典

        Raises:
            FileNotFoundError: 配置文件不存在
            json.JSONDecodeError: JSON解析错误
            ValueError: 配置验证失败
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        # 展开环境变量
        self.config = self._expand_env_vars_recursive(self.config)

        # 验证配置
        self.validate()

        return self.config

    def _expand_env_vars_recursive(self, data: Any) -> Any:
        """
        递归展开配置中的环境变量

        Args:
            data: 配置数据（任意类型）

        Returns:
            展开环境变量后的数据
        """
        if isinstance(data, str):
            # 匹配 ${VAR_NAME} 格式的环境变量
            pattern = r'\$\{([^}]+)\}'

            def replace_env(match):
                var_name = match.group(1)
                return os.getenv(var_name, match.group(0))

            return re.sub(pattern, replace_env, data)
        elif isinstance(data, dict):
            return {k: self._expand_env_vars_recursive(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._expand_env_vars_recursive(item) for item in data]
        return data

    def validate(self):
        """验证配置文件的完整性和正确性"""
        required_keys = ['repositories', 'personal_branch', 'commit']

        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"配置文件缺少必需的键: {key}")

        if not self.config['repositories']:
            raise ValueError("repositories 配置不能为空")

        # 验证全局配置中的 source_branch
        if 'global' not in self.config:
            self.config['global'] = {}
        if 'source_branch' not in self.config['global']:
            self.config['global']['source_branch'] = 'main'

        for idx, repo in enumerate(self.config['repositories']):
            if 'name' not in repo or 'url' not in repo:
                raise ValueError(f"仓库配置 #{idx} 缺少必需字段 (name, url)")


# ============================================================================
# Git操作模块
# ============================================================================

class GitOperations:
    """Git操作封装类，处理所有Git相关操作"""

    def __init__(self, git_token: Optional[str] = None):
        """
        初始化Git操作器

        Args:
            git_token: HTTPS访问的Git token（可选）
        """
        self.git_token = git_token
        self.logger = logging.getLogger(self.__class__.__name__)

    def clone_or_pull(self, repo_url: str, target_dir: Path, source_branch: str) -> bool:
        """
        克隆仓库或拉取最新代码

        Args:
            repo_url: 仓库URL
            target_dir: 目标目录
            source_branch: 源分支名称

        Returns:
            操作是否成功
        """
        target_dir = Path(target_dir)

        try:
            if target_dir.exists():
                self.logger.info(f"仓库已存在，拉取最新代码: {target_dir}")
                return self._pull_existing_repo(target_dir, source_branch)
            else:
                self.logger.info(f"克隆新仓库: {repo_url} -> {target_dir}")
                return self._clone_new_repo(repo_url, target_dir, source_branch)
        except Exception as e:
            self.logger.error(f"Git操作失败: {e}")
            return False

    def _clone_new_repo(self, repo_url: str, target_dir: Path, source_branch: str) -> bool:
        """克隆新仓库"""
        try:
            # 注入token到URL（如果提供了）
            url_with_auth = self._inject_token_to_url(repo_url)

            # 克隆仓库
            result = subprocess.run(
                ['git', 'clone', url_with_auth, str(target_dir)],
                capture_output=True,
                text=True,
                check=True
            )

            # 切换到源分支
            if source_branch:
                self._checkout_branch(target_dir, source_branch)

            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"克隆失败: {e.stderr}")
            return False

    def _pull_existing_repo(self, repo_dir: Path, source_branch: str) -> bool:
        """拉取已存在仓库的更新"""
        try:
            # Fetch远程更新
            subprocess.run(
                ['git', 'fetch', 'origin'],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=True
            )

            # 切换到源分支并拉取
            if source_branch:
                self._checkout_branch(repo_dir, source_branch)

            # 拉取最新代码
            subprocess.run(
                ['git', 'pull', 'origin', source_branch],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=True
            )

            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"拉取失败: {e.stderr}")
            return False

    def _checkout_branch(self, repo_dir: Path, branch_name: str):
        """切换到指定分支"""
        try:
            subprocess.run(
                ['git', 'checkout', branch_name],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError:
            # 如果分支不存在，尝试从远程创建
            subprocess.run(
                ['git', 'checkout', '-b', branch_name, f'origin/{branch_name}'],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=True
            )

    def create_personal_branch(self, repo_dir: Path, source_branch: str,
                               personal_branch: str) -> bool:
        """
        从源分支创建并切换到个人分支

        Args:
            repo_dir: 仓库目录
            source_branch: 源分支名称
            personal_branch: 个人分支名称

        Returns:
            操作是否成功
        """
        try:
            # 确保在源分支上
            self._checkout_branch(repo_dir, source_branch)

            # 拉取最新代码
            subprocess.run(
                ['git', 'pull', 'origin', source_branch],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=True
            )

            # 创建并切换到个人分支
            subprocess.run(
                ['git', 'checkout', '-b', personal_branch],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=True
            )

            self.logger.info(f"创建个人分支: {personal_branch}")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"创建分支失败: {e.stderr}")
            return False

    def has_changes(self, repo_dir: Path) -> bool:
        """
        检查仓库是否有未提交的更改

        Args:
            repo_dir: 仓库目录

        Returns:
            是否有未提交的更改
        """
        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=True
            )
            return len(result.stdout.strip()) > 0
        except subprocess.CalledProcessError:
            return False

    def commit_and_push(self, repo_dir: Path, branch_name: str,
                        commit_message: str) -> bool:
        """
        提交更改并推送到远程

        Args:
            repo_dir: 仓库目录
            branch_name: 分支名称
            commit_message: 提交信息

        Returns:
            操作是否成功
        """
        try:
            # 检查是否有更改
            if not self.has_changes(repo_dir):
                self.logger.info(f"没有需要提交的更改: {repo_dir}")
                return True

            # 添加所有更改
            subprocess.run(
                ['git', 'add', '.'],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=True
            )

            # 提交更改
            subprocess.run(
                ['git', 'commit', '-m', commit_message],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=True
            )

            self.logger.info(f"提交成功: {repo_dir}")

            # 推送到远程
            url_with_auth = self._inject_token_to_url_url_if_needed(
                repo_dir, branch_name
            )

            subprocess.run(
                ['git', 'push', '-u', 'origin', branch_name],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=True
            )

            self.logger.info(f"推送成功: {branch_name}")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"提交或推送失败: {e.stderr}")
            return False

    def _inject_token_to_url(self, url: str) -> str:
        """
        在HTTPS URL中注入认证token

        Args:
            url: 原始URL

        Returns:
            带token的URL（如果配置了token）
        """
        if not self.git_token or not url.startswith('https://'):
            return url

        # 解析URL并插入token
        # https://github.com/user/repo.git -> https://token@github.com/user/repo.git
        parts = url.split('://')
        if len(parts) == 2:
            return f"{parts[0]}://{self.git_token}@{parts[1]}"
        return url

    def _inject_token_to_url_url_if_needed(self, repo_dir: Path,
                                           branch_name: str) -> str:
        """配置远程URL（如果需要token认证）"""
        if not self.git_token:
            return ""

        try:
            # 获取当前远程URL
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=True
            )
            current_url = result.stdout.strip()

            # 如果是HTTPS且没有token，更新URL
            if current_url.startswith('https://') and self.git_token not in current_url:
                new_url = self._inject_token_to_url(current_url)
                subprocess.run(
                    ['git', 'remote', 'set-url', 'origin', new_url],
                    cwd=repo_dir,
                    capture_output=True,
                    text=True,
                    check=True
                )
                return new_url
        except subprocess.CalledProcessError:
            pass
        return ""


# ============================================================================
# 代码修改模块
# ============================================================================

class CodeModifier:
    """代码修改器，负责应用全局替换规则"""

    def __init__(self):
        """初始化代码修改器"""
        self.logger = logging.getLogger(self.__class__.__name__)

    def apply_replacements(self, repo_dir: Path,
                           replacements: List[Dict[str, Any]]) -> int:
        """
        应用所有替换规则到仓库

        Args:
            repo_dir: 仓库目录
            replacements: 替换规则列表

        Returns:
            修改的文件总数
        """
        modified_count = 0

        for rule in replacements:
            search = rule.get('search')
            replace = rule.get('replace')
            is_regex = rule.get('is_regex', False)
            include_exts = rule.get('include_extensions', [])
            exclude_patterns = rule.get('exclude_patterns', [])

            if not search:
                continue

            self.logger.info(f"应用替换规则: {'(正则)' if is_regex else ''} {search[:50]}...")

            # 遍历所有文件
            for file_path in self._get_files_to_process(
                repo_dir, include_exts, exclude_patterns
            ):
                if self._apply_single_replacement(
                    file_path, search, replace, is_regex
                ):
                    modified_count += 1

        self.logger.info(f"共修改 {modified_count} 个文件")
        return modified_count

    def _get_files_to_process(self, repo_dir: Path,
                               include_exts: List[str],
                               exclude_patterns: List[str]) -> List[Path]:
        """
        获取需要处理的所有文件

        Args:
            repo_dir: 仓库目录
            include_exts: 包含的文件扩展名（空列表表示全部）
            exclude_patterns: 排除的文件模式

        Returns:
            需要处理的文件列表
        """
        files = []
        exclude_patterns = exclude_patterns or []

        for file_path in repo_dir.rglob('*'):
            # 跳过目录和 .git 目录
            if not file_path.is_file():
                continue
            if '.git' in file_path.parts:
                continue

            # 检查排除模式
            if self._matches_exclude_pattern(file_path, exclude_patterns):
                continue

            # 检查包含扩展名（如果指定了）
            if include_exts:
                if file_path.suffix not in include_exts:
                    continue

            files.append(file_path)

        return files

    def should_process_file(self, file_path: Path, include_exts: List[str],
                            exclude_patterns: List[str]) -> bool:
        """
        判断文件是否需要处理

        Args:
            file_path: 文件路径
            include_exts: 包含的文件扩展名（空列表表示全部）
            exclude_patterns: 排除的文件模式

        Returns:
            是否需要处理
        """
        # 检查排除模式
        if self._matches_exclude_pattern(file_path, exclude_patterns):
            return False

        # 检查包含扩展名
        if include_exts:
            return file_path.suffix in include_exts

        return True

    def _apply_single_replacement(self, file_path: Path, search: str,
                                   replace: str, is_regex: bool) -> bool:
        """
        对单个文件应用替换规则

        Args:
            file_path: 文件路径
            search: 搜索字符串/正则表达式
            replace: 替换字符串
            is_regex: 是否使用正则表达式

        Returns:
            文件是否被修改
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 执行替换
            if is_regex:
                new_content, count = re.subn(search, replace, content, flags=re.MULTILINE)
            else:
                count = content.count(search)
                new_content = content.replace(search, replace)

            # 如果有替换，写回文件
            if count > 0 and new_content != content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                self.logger.debug(f"修改文件: {file_path} ({count} 处替换)")
                return True

            return False
        except Exception as e:
            self.logger.warning(f"处理文件失败 {file_path}: {e}")
            return False

    def _matches_exclude_pattern(self, file_path: Path,
                                  exclude_patterns: List[str]) -> bool:
        """
        检查文件是否匹配排除模式

        Args:
            file_path: 文件路径
            exclude_patterns: 排除模式列表（支持通配符）

        Returns:
            是否匹配排除模式
        """
        for pattern in exclude_patterns:
            # 将路径转换为相对路径进行匹配
            rel_path = str(file_path)

            # 支持 * 和 ** 通配符
            if fnmatch.fnmatch(rel_path, pattern):
                return True
            # 也匹配文件名
            if fnmatch.fnmatch(file_path.name, pattern):
                return True

        return False


# ============================================================================
# 命令执行模块
# ============================================================================

class CommandExecutor:
    """命令执行器，在仓库目录中执行自定义命令"""

    def __init__(self, on_error: str = "continue"):
        """
        初始化命令执行器

        Args:
            on_error: 错误处理策略 ("continue" | "stop")
        """
        self.on_error = on_error
        self.logger = logging.getLogger(self.__class__.__name__)

    def execute_in_repo(self, repo_dir: Path,
                        commands: List[str]) -> Tuple[int, int]:
        """
        在仓库根目录执行命令列表

        Args:
            repo_dir: 仓库目录
            commands: 命令列表

        Returns:
            (成功数量, 失败数量)
        """
        success_count = 0
        fail_count = 0

        for cmd in commands:
            result = self.execute_single_command(repo_dir, cmd)
            if result:
                success_count += 1
            else:
                fail_count += 1
                if self.on_error == "stop":
                    self.logger.error(f"命令执行失败，中止后续命令")
                    break

        return success_count, fail_count

    def execute_single_command(self, repo_dir: Path, command: str) -> bool:
        """
        执行单个命令并返回结果

        Args:
            repo_dir: 仓库目录
            command: 要执行的命令

        Returns:
            是否成功
        """
        try:
            self.logger.info(f"执行命令: {command}")

            result = subprocess.run(
                command,
                shell=True,
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )

            if result.stdout:
                self.logger.debug(f"命令输出:\n{result.stdout}")
            if result.stderr:
                self.logger.warning(f"错误输出:\n{result.stderr}")

            if result.returncode == 0:
                self.logger.info(f"命令执行成功: {command}")
                return True
            else:
                self.logger.error(f"命令执行失败 (退出码: {result.returncode}): {command}")
                return False
        except subprocess.TimeoutExpired:
            self.logger.error(f"命令执行超时: {command}")
            return False
        except Exception as e:
            self.logger.error(f"命令执行异常: {e}")
            return False


# ============================================================================
# 主程序流程
# ============================================================================

class BatchRepoManager:
    """批量代码仓库管理器，协调所有模块执行完整流程"""

    def __init__(self, config_path: str):
        """
        初始化批量管理器

        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self.logger: logging.Logger = None

        # 组件实例
        self.git_ops: GitOperations = None
        self.code_modifier: CodeModifier = None
        self.command_executor: CommandExecutor = None

        # 工作目录
        self.work_dir = self.config_path.parent / "repos"

    def run(self):
        """执行完整的批量管理流程"""
        try:
            # 1. 加载配置
            self._load_config()

            # 2. 初始化组件
            self._init_components()

            # 3. 处理所有仓库
            success_count = 0
            fail_count = 0

            for repo_config in self.config['repositories']:
                if self.process_repository(repo_config):
                    success_count += 1
                else:
                    fail_count += 1
                    if self.config.get('global', {}).get('on_error') == 'stop':
                        self.logger.error("仓库处理失败，中止后续处理")
                        break

            # 4. 输出总结
            self.logger.info("=" * 60)
            self.logger.info(f"批量处理完成: 成功 {success_count}, 失败 {fail_count}")
            self.logger.info("=" * 60)

        except Exception as e:
            self.logger.error(f"程序执行失败: {e}", exc_info=True)
            raise

    def _load_config(self):
        """加载配置文件"""
        # 加载环境变量
        load_dotenv()

        # 加载配置
        loader = ConfigLoader(self.config_path)
        self.config = loader.load()
        # 注意：此时logger可能还未初始化，不在记录日志

    def _init_components(self):
        """初始化所有组件"""
        # 初始化日志
        global_config = self.config.get('global', {})
        log_dir = global_config.get('log_dir', './logs')
        log_level = global_config.get('log_level', 'INFO')

        log_manager = LogManager(log_dir, log_level)
        self.logger = log_manager.get_logger('BatchRepoManager')

        # 初始化Git操作器
        git_token = global_config.get('git_token')
        self.git_ops = GitOperations(git_token)

        # 初始化代码修改器
        self.code_modifier = CodeModifier()

        # 初始化命令执行器
        on_error = global_config.get('on_error', 'continue')
        self.command_executor = CommandExecutor(on_error)

        # 创建工作目录
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def process_repository(self, repo_config: Dict[str, Any]) -> bool:
        """
        处理单个仓库的完整流程

        Args:
            repo_config: 仓库配置

        Returns:
            是否处理成功
        """
        name = repo_config['name']
        url = repo_config['url']
        source_branch = self.config.get('global', {}).get('source_branch', 'main')

        self.logger.info("=" * 60)
        self.logger.info(f"开始处理仓库: {name}")
        self.logger.info("=" * 60)

        try:
            # 1. 克隆或拉取代码
            repo_dir = self.work_dir / name
            if not self.git_ops.clone_or_pull(url, repo_dir, source_branch):
                self.logger.error(f"克隆/拉取失败: {name}")
                return False

            # 2. 创建个人分支
            personal_branch = self.config.get('personal_branch', 'feature/batch-update')
            if not self.git_ops.create_personal_branch(
                repo_dir, source_branch, personal_branch
            ):
                self.logger.error(f"创建分支失败: {name}")
                return False

            # 3. 批量修改代码
            replacements = self.config.get('replacements', [])
            if replacements:
                self.logger.info(f"应用 {len(replacements)} 条替换规则...")
                self.code_modifier.apply_replacements(repo_dir, replacements)

            # 4. 执行自定义命令
            commands = self.config.get('commands', [])
            if commands:
                self.logger.info(f"执行 {len(commands)} 条命令...")
                self.command_executor.execute_in_repo(repo_dir, commands)

            # 5. 提交并推送
            commit_message = self.format_commit_message(
                self.config['commit']['message'],
                name
            )
            if not self.git_ops.commit_and_push(
                repo_dir, personal_branch, commit_message
            ):
                self.logger.warning(f"提交/推送失败: {name}")
                # 不返回False，因为前面的操作已经成功

            self.logger.info(f"仓库处理完成: {name}")
            return True

        except Exception as e:
            self.logger.error(f"处理仓库失败 {name}: {e}", exc_info=True)
            return False

    def format_commit_message(self, template: str, repo_name: str) -> str:
        """
        格式化提交信息，替换占位符

        Args:
            template: 提交信息模板
            repo_name: 仓库名称

        Returns:
            格式化后的提交信息
        """
        now = datetime.now()
        variables = self.config.get('commit', {}).get('variables', {})

        # 获取统计信息
        replacement_count = len(self.config.get('replacements', []))
        command_count = len(self.config.get('commands', []))

        # 替换占位符
        message = template.format(
            repo_name=repo_name,
            date=now.strftime('%Y-%m-%d'),
            datetime=now.strftime('%Y-%m-%d %H:%M:%S'),
            timestamp=str(int(now.timestamp())),
            replacement_count=replacement_count,
            command_count=command_count,
            **variables
        )

        return message


# ============================================================================
# 程序入口
# ============================================================================

def main():
    """程序入口"""
    import sys

    # 获取配置文件路径
    config_path = sys.argv[1] if len(sys.argv) > 1 else 'config.json'

    print("=" * 60)
    print("BatchGitOps - 批量Git仓库操作工具")
    print("=" * 60)
    print(f"配置文件: {config_path}")
    print()

    try:
        manager = BatchRepoManager(config_path)
        manager.run()
        print("\n执行完成!")
    except Exception as e:
        print(f"\n执行失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
