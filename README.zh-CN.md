<p align="center">
  <img src="assets/logo.svg" width="112" alt="Git Hook Doctor 标志">
</p>

<h1 align="center">Git Hook Doctor</h1>

<p align="center"><strong>解释一个 Git Hook 为什么会运行，或者为什么根本不会运行。</strong></p>

<p align="center">只读 · 离线 · 零运行时依赖 · 支持 Windows、macOS 和 Linux</p>

![Git Hook Doctor 演示](assets/demo.svg)

Git Hook 经常“静默失效”：文件装在了错误目录，linked worktree 改变了相对 `core.hooksPath` 的解析位置，Windows 检出把 shebang 变成 CRLF，POSIX 执行位丢失，或当前 Git 版本根本不认识配置式 Hook。

Git Hook Doctor 直接询问 Git 的**有效路径与配置来源**，再检查真正会被 Git 找到的文件。它不会执行 Hook，也不会修改仓库。

## 安装

推荐通过 pipx 安装版本化 wheel：

```console
pipx install https://github.com/cuijialin8888-code/git-hook-doctor/releases/download/v0.1.0/git_hook_doctor-0.1.0-py3-none-any.whl
```

也可从发布标签安装：

```console
python -m pip install "git+https://github.com/cuijialin8888-code/git-hook-doctor.git@v0.1.0"
```

要求：Python 3.10+，Git 2.31+。

## 快速使用

```console
# 解释为什么 pre-commit 没运行
git-hook-doctor explain pre-commit

# 检查当前仓库已发现的 Hook
git-hook-doctor check

# 只检查点名事件
git-hook-doctor check pre-commit commit-msg pre-push

# 输出 JSON / SARIF / Markdown / GitHub Actions 注释
git-hook-doctor check --format sarif --output hook-report.sarif
```

也可以使用 `git-hook-doctor check --format github` 输出 GitHub Actions 原生工作流命令注释；它仍然只读，也不会把 hook 正文复制到注释中。

如果电脑上有多个 Git，可用 `--git <路径>` 指定 IDE 或其他客户端实际使用的 Git 二进制。

## 检查范围

| 范围 | 证据 |
|---|---|
| 有效路径 | `git rev-parse --git-path hooks`、bare 仓库、linked worktree、客户端/接收端事件工作目录、相对/绝对 `core.hooksPath` |
| 传统 Hook | 精确文件名、Git for Windows `.exe` 回退、`.sample`、错误扩展名、文件/软链接、POSIX 执行位、空文件 |
| 启动条件 | shebang、UTF-8 BOM、首行 CRLF、解释器是否能解析、Git for Windows 自带 shell |
| 配置式 Hook | `hook.<name>.event/command/enabled`、事件开关、配置 scope 与 origin |
| 版本兼容 | Git 2.54 前不支持配置式 Hook；Git 2.55 前不支持事件开关和并行配置 |
| 安装错位 | 默认 hooks 目录、`.husky`、`.githooks`、`.git-hooks` 与 Git 有效目录不一致 |

每个问题都有稳定的 `GHD###` 规则号、严重级别、证据和局部修复建议。详见[规则表](docs/rules.md)。

## 与其他工具的边界

- `git hook list`：列出当前事件注册了哪些 Hook。
- Husky、Lefthook、pre-commit：安装和管理各自框架的 Hook。
- Hook 安全扫描器：分析脚本内容是否危险或不可移植。
- **Git Hook Doctor**：解释在当前仓库、worktree、操作系统和 Git 版本下，Hook 为什么无法启动。

本项目不执行 Hook、不自动修复、不修改权限或换行符，也不把“能启动”误写成“脚本安全”。

## Git 2.54+ 配置式 Hook

[Git 2.54](https://github.com/git/git/blob/master/Documentation/RelNotes/2.54.0.adoc) 新增配置式 Hook：可用 `hook.<friendly-name>.event` 和 `hook.<friendly-name>.command` 给同一事件挂载多个命令；传统 Hook 文件仍在最后执行。Git 2.55 又加入事件开关和并行控制。

Git Hook Doctor 同时理解两套模型，并在配置比 Git 二进制更新时给出明确提示。详见[配置式 Hook 指南](docs/configured-hooks.md)。

## 安全边界

工具只运行只读 Git 查询，并读取有限范围的配置与 Hook 文件。它不会调用 `git hook run`，不会 source 或执行脚本，不会改 Git 配置、权限、换行符或文件，不联网，也不发送遥测。报告只显示可静态确定的首个命令目标；参数、环境赋值和 shell 正文不会写进 JSON/SARIF，避免把配置中嵌入的令牌复制到诊断报告。

静态检查无法复现 IDE 私有环境、未来 PATH 变化、`noexec` 挂载或 Hook 的运行时退出行为。详见[限制说明](docs/limitations.md)。

## 许可证

MIT © 2026 Jialin Cui
