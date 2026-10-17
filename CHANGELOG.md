# 更新日志

本项目的重要变更记录在此文件中，格式参考 Keep a Changelog。

## [Unreleased]

### 项目定位

WSARTEX 是一套**本地运行**的 LLM 多 agent 自主渗透测试系统：Go 单体后端（内嵌 Next.js 前端）+ PostgreSQL。
仅面向本地隔离靶场与学习研究使用，详见[详细说明中的「许可与免责声明」](README.detailed.md#许可与免责声明)。

### 本地化改造

- **依赖全部本地化**：Go 依赖已收进 `vendor/`，`go build` 不再联网拉取；前端依赖在 `web/node_modules`，
  并带项目内缓存 `web/.npm-cache`，`npm ci --offline` 可直接离线重装。构建与运行全程不需要外部网络。
- **核心 SDK 收编为本地模块**：`norma` 的完整源码（206 个 Go 文件）已复制进 `third_party/norma`，
  模块名改为 `wsartex/norma`，并在 `go.mod` 中以 `replace wsartex/norma => ./third_party/norma` 指向本地。
  全项目 172 个文件的导入路径随之更新，源码中不再存在任何外部仓库地址。
  注意：修改 `third_party/norma` 后需重跑 `go mod vendor` 才会生效。
- **移除全部容器化内容**：删除 Dockerfile、docker-compose、.dockerignore、.env.example，
  以及基于 Docker 的安装脚本与更新脚本。
- **移除联网自动更新**：删除自更新包、`/api/update/*` 接口、设置页「版本与更新」卡片与顶栏更新提示。
  程序不会向任何远程地址检查版本或下载更新。
- **移除 CI 配置**：不再包含 GitHub Actions 工作流。
- **安装路径收敛为一条**：README 只保留「一键启动器」这一种安装方式；原先的「从源码编译单二进制」
  与「构建跨平台 Release 压缩包」两节已删除，仅用于打 Release 包的 `build.sh` 一并移除。
  需要重新构建时，直接重新运行 `start.py`（自动判断哪些步骤需要重做），或参照「更新」一节的命令。
- **跨平台一键启动与退出**：新增 `start.py` 与 `quit.py` 两个入口，macOS / Linux / Windows 通用。
  `start.py` 会识别操作系统、检测外部依赖（Go / Node / npm / PostgreSQL，以及可选的 nmap、ripgrep），
  缺失时让用户选择「退出自行安装」或「自动安装」（按系统分别使用 Homebrew / apt·dnf·pacman / winget·choco·scoop），
  随后准备 PostgreSQL、构建前后端、后台启动服务并自动打开浏览器；已完成的步骤重复运行时自动跳过。
  `quit.py` 结束全部 WSARTEX 相关进程并确认端口释放。前置条件只有一个：本机已装 Python 3.8+。
  原来的 `启动WSARTEX.command`、`停止WSARTEX.command`、`start_wsartex.py`（仅 macOS）已移除。
- **密码重置**：`reset-password.sh` 保留纯本地模式——直接连 PostgreSQL 用 pgcrypto 重置管理员密码，无需重启服务。

### 许可

本项目采用 **GNU Affero General Public License v3.0（AGPL-3.0）** 授权，完整条款见根目录 [LICENSE](LICENSE)。
