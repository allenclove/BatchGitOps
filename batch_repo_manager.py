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

        # 创建根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)

        # 清除现有的处理器
        root_logger.handlers.clear()

        # 统一的日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # 文件处理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

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

    def __init__(self, git_token: Optional[str] = None,
                 git_account: Optional[str] = None,
                 branch_exists_strategy: str = "checkout"):
        """
        初始化Git操作器

        Args:
            git_token: HTTPS访问的Git token（可选）
            git_account: Git账号，用于token认证（可选）
            branch_exists_strategy: 分支已存在时的处理策略
                - "checkout": 直接检出远程已存在的分支
                - "recreate": 删除本地分支并重新创建
                - "reset": 检出分支并重置到源分支
        """
        self.git_token = git_token
        self.git_account = git_account
        self.branch_exists_strategy = branch_exists_strategy
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
                encoding='utf-8',
                errors='replace',
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
                encoding='utf-8',
                errors='replace',
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
                encoding='utf-8',
                errors='replace',
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
                encoding='utf-8',
                errors='replace',
                check=True
            )
        except subprocess.CalledProcessError:
            # 如果分支不存在，尝试从远程创建
            subprocess.run(
                ['git', 'checkout', '-b', branch_name, f'origin/{branch_name}'],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
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
                encoding='utf-8',
                errors='replace',
                check=True
            )

            # 检查本地分支是否已存在
            if self._local_branch_exists(repo_dir, personal_branch):
                self.logger.info(f"本地分支 '{personal_branch}' 已存在")
                return self._handle_existing_branch(repo_dir, source_branch, personal_branch)

            # 检查远程分支是否存在
            remote_exists = self._remote_branch_exists(repo_dir, personal_branch)
            if remote_exists:
                self.logger.info(f"远程分支 '{personal_branch}' 已存在")
                if self.branch_exists_strategy == "checkout":
                    # 直接检出远程分支
                    subprocess.run(
                        ['git', 'checkout', '-b', personal_branch,
                         f'origin/{personal_branch}'],
                        cwd=repo_dir,
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        check=True
                    )
                    self.logger.info(f"检出远程分支: {personal_branch}")
                    return True
                elif self.branch_exists_strategy == "reset":
                    # 检出远程分支并重置到源分支
                    subprocess.run(
                        ['git', 'checkout', '-b', personal_branch,
                         f'origin/{personal_branch}'],
                        cwd=repo_dir,
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        check=True
                    )
                    subprocess.run(
                        ['git', 'reset', '--hard', f'origin/{source_branch}'],
                        cwd=repo_dir,
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        check=True
                    )
                    self.logger.info(f"检出远程分支并重置: {personal_branch}")
                    return True

            # 创建并切换到个人分支
            subprocess.run(
                ['git', 'checkout', '-b', personal_branch],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=True
            )

            self.logger.info(f"创建个人分支: {personal_branch}")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"创建分支失败: {e.stderr}")
            return False

    def _local_branch_exists(self, repo_dir: Path, branch_name: str) -> bool:
        """检查本地分支是否存在"""
        try:
            result = subprocess.run(
                ['git', 'branch', '--list', branch_name],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=True
            )
            return bool(result.stdout.strip())
        except subprocess.CalledProcessError:
            return False

    def _remote_branch_exists(self, repo_dir: Path, branch_name: str) -> bool:
        """检查远程分支是否存在"""
        try:
            result = subprocess.run(
                ['git', 'ls-remote', '--heads', 'origin', branch_name],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=True
            )
            return bool(result.stdout.strip())
        except subprocess.CalledProcessError:
            return False

    def _handle_existing_branch(self, repo_dir: Path, source_branch: str,
                                personal_branch: str) -> bool:
        """
        处理已存在的本地分支

        Args:
            repo_dir: 仓库目录
            source_branch: 源分支名称
            personal_branch: 个人分支名称

        Returns:
            操作是否成功
        """
        strategy = self.branch_exists_strategy

        if strategy == "checkout":
            # 直接切换到已存在的分支
            subprocess.run(
                ['git', 'checkout', personal_branch],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=True
            )
            self.logger.info(f"切换到已存在的分支: {personal_branch}")
            return True

        elif strategy == "recreate":
            # 删除本地分支并重新创建
            # 先切换到源分支
            subprocess.run(
                ['git', 'checkout', source_branch],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=True
            )
            # 删除本地分支
            subprocess.run(
                ['git', 'branch', '-D', personal_branch],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=True
            )
            # 重新创建分支
            subprocess.run(
                ['git', 'checkout', '-b', personal_branch],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=True
            )
            self.logger.info(f"重新创建分支: {personal_branch}")
            return True

        elif strategy == "reset":
            # 切换到分支并重置到源分支
            subprocess.run(
                ['git', 'checkout', personal_branch],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=True
            )
            subprocess.run(
                ['git', 'reset', '--hard', f'origin/{source_branch}'],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=True
            )
            self.logger.info(f"重置分支 {personal_branch} 到 {source_branch}")
            return True

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
                encoding='utf-8',
                errors='replace',
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
                encoding='utf-8',
                errors='replace',
                check=True
            )

            # 提交更改
            subprocess.run(
                ['git', 'commit', '-m', commit_message],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
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
                encoding='utf-8',
                errors='replace',
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
        # https://github.com/user/repo.git -> https://account:token@github.com/user/repo.git
        # 如果没有配置 account，则 -> https://token@github.com/user/repo.git
        parts = url.split('://')
        if len(parts) == 2:
            if self.git_account:
                return f"{parts[0]}://{self.git_account}:{self.git_token}@{parts[1]}"
            else:
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
                encoding='utf-8',
                errors='replace',
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
                    encoding='utf-8',
                    errors='replace',
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
        # 统计信息结构：
        # {
        #   rule_index: {
        #     'modified_repos': set(),      # 有修改的仓库
        #     'zero_match_repos': set(),    # 零匹配的仓库
        #     'files': [],                   # 修改的文件列表
        #     'replacement_counts': {},      # {repo_name: 替换次数}
        #     'total_replacements': 0        # 总替换次数
        #   }
        # }
        self.rule_stats = {}

    def apply_replacements(self, repo_dir: Path,
                           replacements: List[Dict[str, Any]],
                           repo_name: str = "") -> int:
        """
        应用所有替换规则到仓库

        Args:
            repo_dir: 仓库目录
            replacements: 替换规则列表
            repo_name: 仓库名称（用于统计）

        Returns:
            修改的文件总数
        """
        modified_count = 0

        for idx, rule in enumerate(replacements):
            search = rule.get('search')
            replace = rule.get('replace')
            is_regex = rule.get('is_regex', False)
            include_exts = rule.get('include_extensions', [])
            exclude_patterns = rule.get('exclude_patterns', [])

            if not search:
                continue

            # 初始化规则统计
            if idx not in self.rule_stats:
                self.rule_stats[idx] = {
                    'modified_repos': set(),
                    'zero_match_repos': set(),
                    'files': [],
                    'replacement_counts': {},
                    'total_replacements': 0
                }

            self.logger.info(f"应用替换规则 #{idx + 1}: {'(正则)' if is_regex else ''} {search[:50]}...")

            # 遍历所有文件
            files_to_process = self._get_files_to_process(repo_dir, include_exts, exclude_patterns)
            file_modified_count = 0
            repo_replacement_count = 0

            for file_path in files_to_process:
                result = self._apply_single_replacement(file_path, search, replace, is_regex)
                if result and result['modified']:
                    modified_count += 1
                    file_modified_count += 1
                    repo_replacement_count += result['count']
                    self.rule_stats[idx]['files'].append(str(file_path))

            # 记录统计信息
            if file_modified_count > 0:
                self.rule_stats[idx]['modified_repos'].add(repo_name)
                self.rule_stats[idx]['replacement_counts'][repo_name] = repo_replacement_count
                self.rule_stats[idx]['total_replacements'] += repo_replacement_count
                self.logger.info(f"  -> 规则 #{idx + 1} 在 [{repo_name}] 中修改了 {file_modified_count} 个文件，共 {repo_replacement_count} 处替换")
            else:
                self.rule_stats[idx]['zero_match_repos'].add(repo_name)
                self.logger.info(f"  -> 规则 #{idx + 1} 在 [{repo_name}] 中未匹配到任何内容")

        if modified_count > 0:
            self.logger.info(f"仓库 [{repo_name}] 共修改 {modified_count} 个文件")
        return modified_count

    def print_summary(self):
        """
        打印所有替换规则的统计摘要
        """
        if not self.rule_stats:
            self.logger.info("未执行任何替换规则")
            return

        self.logger.info("=" * 60)
        self.logger.info("替换规则执行统计汇总")
        self.logger.info("=" * 60)

        # 汇总统计
        total_modified_files = 0
        total_replacements = 0
        zero_match_rules = []

        for idx, stats in self.rule_stats.items():
            modified_repos = len(stats['modified_repos'])
            zero_match_repos = len(stats['zero_match_repos'])
            affected_files = len(stats['files'])
            replacements = stats['total_replacements']

            total_modified_files += affected_files
            total_replacements += replacements

            self.logger.info(f"规则 #{idx + 1}:")
            self.logger.info(f"  - 成功修改仓库: {modified_repos} 个")
            if zero_match_repos > 0:
                self.logger.info(f"  - 零匹配仓库: {zero_match_repos} 个")
            self.logger.info(f"  - 修改文件数: {affected_files}")
            self.logger.info(f"  - 替换总次数: {replacements}")

            # 检测异常：零匹配规则
            if modified_repos == 0:
                zero_match_rules.append(idx + 1)

        # 总体统计
        self.logger.info("-" * 60)
        self.logger.info(f"总计: 修改 {total_modified_files} 个文件，共 {total_replacements} 处替换")

        # 异常检测
        if zero_match_rules:
            self.logger.warning("=" * 60)
            self.logger.warning(f"警告: 以下规则在所有仓库中均未匹配到内容: {zero_match_rules}")
            self.logger.warning("请检查搜索字符串是否正确，或排除模式是否过于严格")

        self.logger.info("=" * 60)

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
                                   replace: str, is_regex: bool) -> Optional[Dict[str, Any]]:
        """
        对单个文件应用替换规则

        Args:
            file_path: 文件路径
            search: 搜索字符串/正则表达式
            replace: 替换字符串
            is_regex: 是否使用正则表达式

        Returns:
            None 表示处理失败或无替换，否则返回 {'modified': True, 'count': 替换次数}
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
                return {'modified': True, 'count': count}

            return None
        except Exception as e:
            self.logger.warning(f"处理文件失败 {file_path}: {e}")
            return None

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

    def __init__(self, on_error: str = "continue", show_output: bool = True):
        """
        初始化命令执行器

        Args:
            on_error: 错误处理策略 ("continue" | "stop")
            show_output: 是否显示命令输出内容
        """
        self.on_error = on_error
        self.show_output = show_output
        self.logger = logging.getLogger(self.__class__.__name__)

    def _normalize_commands(self, commands: List[Any]) -> List[Dict[str, str]]:
        """
        标准化命令配置格式，支持新旧两种格式

        Args:
            commands: 命令列表（可以是字符串或字典）

        Returns:
            标准化后的命令列表，每个元素为 {"command": str, "scope": str}
        """
        normalized = []
        for cmd in commands:
            if isinstance(cmd, str):
                # 旧格式：字符串，默认为 repo 级别
                normalized.append({"command": cmd, "scope": "repo"})
            elif isinstance(cmd, dict):
                # 新格式：对象
                command = cmd.get("command", "")
                scope = cmd.get("scope", "repo")
                normalized.append({"command": command, "scope": scope})
            else:
                self.logger.warning(f"忽略无效的命令配置: {cmd}")
        return normalized

    def execute_repo_commands(self, repo_dir: Path,
                             commands: List[Any]) -> Tuple[int, int]:
        """
        执行仓库级别的命令（scope="repo"）

        Args:
            repo_dir: 仓库目录
            commands: 命令列表（支持新旧格式）

        Returns:
            (成功数量, 失败数量)
        """
        normalized = self._normalize_commands(commands)
        repo_commands = [cmd for cmd in normalized if cmd["scope"] == "repo"]

        if not repo_commands:
            return 0, 0

        self.logger.info(f"在仓库目录执行 {len(repo_commands)} 条命令: {repo_dir}")

        success_count = 0
        fail_count = 0

        for cmd_config in repo_commands:
            command = cmd_config["command"]
            result = self.execute_single_command(repo_dir, command)
            if result:
                success_count += 1
            else:
                fail_count += 1
                if self.on_error == "stop":
                    self.logger.error(f"命令执行失败，中止后续命令")
                    break

        return success_count, fail_count

    def execute_parent_commands(self, parent_dir: Path,
                                commands: List[Any]) -> Tuple[int, int]:
        """
        在父目录执行一次所有父级别命令（scope="parent"）

        Args:
            parent_dir: 父目录
            commands: 命令列表（支持新旧格式）

        Returns:
            (成功数量, 失败数量)
        """
        normalized = self._normalize_commands(commands)
        parent_commands = [
            cmd for cmd in normalized
            if cmd["scope"] == "parent"
        ]

        if not parent_commands:
            return 0, 0

        self.logger.info(f"在父目录执行 {len(parent_commands)} 条命令: {parent_dir}")

        success_count = 0
        fail_count = 0

        for cmd_config in parent_commands:
            command = cmd_config["command"]
            result = self.execute_single_command(parent_dir, command)
            if result:
                success_count += 1
            else:
                fail_count += 1
                if self.on_error == "stop":
                    self.logger.error(f"命令执行失败，中止后续命令")
                    break

        return success_count, fail_count

    def execute_single_command(self, exec_dir: Path, command: str) -> bool:
        """
        执行单个命令并返回结果

        Args:
            exec_dir: 执行命令的目录
            command: 要执行的命令

        Returns:
            是否成功
        """
        try:
            self.logger.info(f"执行命令: {command}")

            result = subprocess.run(
                command,
                shell=True,
                cwd=exec_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',  # 替换无法解码的字符
                timeout=300  # 5分钟超时
            )

            # 显示命令输出
            if self.show_output:
                if result.stdout:
                    # 使用 INFO 级别显示标准输出，确保用户能看到
                    output_lines = result.stdout.strip().split('\n')
                    self.logger.info(f"命令输出 ({len(output_lines)} 行):")
                    for line in output_lines:
                        self.logger.info(f"  {line}")
                if result.stderr:
                    # 错误输出使用 WARNING 级别
                    error_lines = result.stderr.strip().split('\n')
                    self.logger.warning(f"错误输出 ({len(error_lines)} 行):")
                    for line in error_lines:
                        self.logger.warning(f"  {line}")

            if result.returncode == 0:
                self.logger.info(f"命令执行成功 (退出码: 0)")
                return True
            else:
                self.logger.error(f"命令执行失败 (退出码: {result.returncode})")
                return False
        except subprocess.TimeoutExpired:
            self.logger.error(f"命令执行超时: {command}")
            return False
        except Exception as e:
            self.logger.error(f"命令执行异常: {e}")
            return False


# ============================================================================
# 执行统计模块
# ============================================================================

class ExecutionStats:
    """执行统计器，追踪和展示各节点的执行情况"""

    def __init__(self, steps: Dict[str, bool]):
        """
        初始化执行统计器

        Args:
            steps: 执行步骤配置 {step_name: enabled}
        """
        self.steps = steps
        self.stats = {
            'clone': {'enabled': steps.get('clone', True), 'executed': 0, 'skipped': 0, 'success': 0, 'failed': 0},
            'branch': {'enabled': steps.get('branch', True), 'executed': 0, 'skipped': 0, 'success': 0, 'failed': 0},
            'replacements': {'enabled': steps.get('replacements', True), 'executed': 0, 'skipped': 0, 'success': 0, 'failed': 0},
            'commands': {'enabled': steps.get('commands', True), 'executed': 0, 'skipped': 0, 'success': 0, 'failed': 0},
            'commit': {'enabled': steps.get('commit', True), 'executed': 0, 'skipped': 0, 'success': 0, 'failed': 0},
        }
        self.logger = logging.getLogger(self.__class__.__name__)

    def record_skip(self, step: str):
        """记录跳过的步骤"""
        if step in self.stats:
            self.stats[step]['skipped'] += 1

    def record_execute(self, step: str, success: bool):
        """记录执行的步骤"""
        if step in self.stats:
            self.stats[step]['executed'] += 1
            if success:
                self.stats[step]['success'] += 1
            else:
                self.stats[step]['failed'] += 1

    def print_summary(self):
        """打印执行统计摘要"""
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("执行节点统计汇总")
        self.logger.info("=" * 60)

        # 定义步骤显示名称和图标
        step_names = {
            'clone': ('克隆/拉取', '📥'),
            'branch': ('创建分支', '🌿'),
            'replacements': ('代码替换', '✏️'),
            'commands': ('执行命令', '⚙️'),
            'commit': ('提交推送', '📤'),
        }

        for step_key, step_data in self.stats.items():
            name, icon = step_names.get(step_key, (step_key, '•'))
            enabled = step_data['enabled']
            executed = step_data['executed']
            skipped = step_data['skipped']
            success = step_data['success']
            failed = step_data['failed']

            if not enabled:
                status = "❌ 已禁用"
            elif executed == 0 and skipped == 0:
                status = "⏭️ 未执行"
            elif failed == 0:
                status = f"✅ 成功 ({executed}/{executed + skipped})"
            else:
                status = f"⚠️ 部分失败 (成功: {success}, 失败: {failed})"

            self.logger.info(f"{icon} {name:12s} {status}")

        self.logger.info("=" * 60)


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
        self.execution_stats: ExecutionStats = None

        # 工作目录
        self.work_dir = self.config_path.parent / "repos"

    def run(self):
        """执行完整的批量管理流程"""
        try:
            # 1. 加载配置
            self._load_config()

            # 2. 初始化组件
            self._init_components()

            # 3. 初始化执行统计
            self.execution_stats = ExecutionStats(self.execution_steps)

            # 4. 处理所有仓库
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

            # 5. 执行父级命令（在所有仓库处理完后）
            commands = self.config.get('commands', [])
            if commands and self._should_execute('commands'):
                self.logger.info("=" * 60)
                self.logger.info("执行父级命令")
                self.logger.info("=" * 60)
                self.command_executor.execute_parent_commands(self.work_dir, commands)

            # 6. 输出总结
            self.logger.info("=" * 60)
            self.logger.info(f"批量处理完成: 成功 {success_count}, 失败 {fail_count}")
            self.logger.info("=" * 60)

            # 7. 输出执行节点统计
            self.execution_stats.print_summary()

            # 8. 输出替换规则统计
            self.code_modifier.print_summary()

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
        git_account = global_config.get('git_account')
        branch_exists_strategy = global_config.get('branch_exists_strategy', 'checkout')
        self.git_ops = GitOperations(git_token, git_account, branch_exists_strategy)

        # 初始化代码修改器
        self.code_modifier = CodeModifier()

        # 初始化命令执行器
        on_error = global_config.get('on_error', 'continue')
        show_command_output = global_config.get('show_command_output', True)
        self.command_executor = CommandExecutor(on_error, show_command_output)

        # 初始化执行步骤配置
        self._init_execution_steps()

        # 创建工作目录
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def _init_execution_steps(self):
        """初始化执行步骤配置"""
        # 优先从独立的 execution 实体读取，保持向后兼容
        execution_config = self.config.get('execution', {})
        global_config = self.config.get('global', {})

        # 默认所有步骤都执行
        self.execution_steps = {
            'clone': self._get_execution_flag(execution_config, global_config, 'clone', 'execute_clone'),
            'branch': self._get_execution_flag(execution_config, global_config, 'branch', 'execute_branch'),
            'replacements': self._get_execution_flag(execution_config, global_config, 'replacements', 'execute_replacements'),
            'commands': self._get_execution_flag(execution_config, global_config, 'commands', 'execute_commands'),
            'commit': self._get_execution_flag(execution_config, global_config, 'commit', 'execute_commit'),
        }

    def _get_execution_flag(self, execution_config: Dict, global_config: Dict,
                           new_key: str, old_key: str) -> bool:
        """
        获取执行步骤标志，支持新旧两种配置格式

        Args:
            execution_config: execution 实体配置
            global_config: global 实体配置
            new_key: 新格式的键名 (如 'clone')
            old_key: 旧格式的键名 (如 'execute_clone')

        Returns:
            是否执行该步骤
        """
        # 优先从 execution 实体读取（新格式）
        if new_key in execution_config:
            return execution_config[new_key]
        # 其次从 global 实体读取（旧格式，向后兼容）
        if old_key in global_config:
            return global_config[old_key]
        # 默认执行
        return True

    def _should_execute(self, step: str) -> bool:
        """
        判断某个步骤是否应该执行

        Args:
            step: 步骤名称

        Returns:
            是否应该执行
        """
        return self.execution_steps.get(step, True)

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
            if self._should_execute('clone'):
                result = self.git_ops.clone_or_pull(url, repo_dir, source_branch)
                self.execution_stats.record_execute('clone', result)
                if not result:
                    self.logger.error(f"克隆/拉取失败: {name}")
                    return False
            else:
                self.execution_stats.record_skip('clone')
                self.logger.info(f"跳过克隆/拉取步骤: {name}")
                if not repo_dir.exists():
                    self.logger.error(f"仓库目录不存在且跳过克隆: {name}")
                    return False

            # 2. 创建个人分支
            personal_branch = self.config.get('personal_branch', 'feature/batch-update')
            if self._should_execute('branch'):
                result = self.git_ops.create_personal_branch(
                    repo_dir, source_branch, personal_branch
                )
                self.execution_stats.record_execute('branch', result)
                if not result:
                    self.logger.error(f"创建分支失败: {name}")
                    return False
            else:
                self.execution_stats.record_skip('branch')
                self.logger.info(f"跳过创建分支步骤: {name}")

            # 3. 批量修改代码
            replacements = self.config.get('replacements', [])
            if replacements and self._should_execute('replacements'):
                self.logger.info(f"应用 {len(replacements)} 条替换规则...")
                self.code_modifier.apply_replacements(repo_dir, replacements, name)
                self.execution_stats.record_execute('replacements', True)
            elif replacements:
                self.execution_stats.record_skip('replacements')
                self.logger.info(f"跳过代码替换步骤")
            else:
                # 没有替换规则时也算跳过
                if not replacements:
                    self.execution_stats.record_skip('replacements')

            # 4. 执行仓库级别的自定义命令（scope="repo"）
            commands = self.config.get('commands', [])
            if commands and self._should_execute('commands'):
                success, fail = self.command_executor.execute_repo_commands(repo_dir, commands)
                if success + fail > 0:
                    self.execution_stats.record_execute('commands', fail == 0)
                if success + fail == 0:
                    self.logger.info(f"没有需要在此仓库执行的命令")
            elif commands:
                self.execution_stats.record_skip('commands')
                self.logger.info(f"跳过命令执行步骤")

            # 5. 提交并推送
            if self._should_execute('commit'):
                commit_message = self.format_commit_message(
                    self.config['commit']['message'],
                    name
                )
                result = self.git_ops.commit_and_push(
                    repo_dir, personal_branch, commit_message
                )
                # commit 失败不记录为失败（因为前面的操作已经成功）
                self.execution_stats.record_execute('commit', True)
                if not result:
                    self.logger.warning(f"提交/推送失败: {name}")
            else:
                self.execution_stats.record_skip('commit')
                self.logger.info(f"跳过提交/推送步骤")

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
