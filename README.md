<div align="center">

<h1>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="web/public/brand/wordmark-white.svg" />
    <source media="(prefers-color-scheme: light)" srcset="web/public/brand/wordmark.svg" />
    <img src="web/public/brand/wordmark.svg" alt="WSARTEX" width="360" />
  </picture>
</h1>

**简体中文** · [English](README.en.md)

**开箱即用的 AI 自主渗透测试系统**

本地部署 · 多 Agent 协作 · 资产探索 · 漏洞管理

<p>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-AGPL--3.0--or--later-18181b?style=flat-square" alt="License: AGPL-3.0-or-later" /></a>
  <a href="third_party/norma/README.md"><img src="https://img.shields.io/badge/norma-Built--in-238636?style=flat-square" alt="norma: Built-in" /></a>
  <a href="README.detailed.md#安装"><img src="https://img.shields.io/badge/Deploy-Self--hosted-3578db?style=flat-square" alt="Deploy: Self-hosted" /></a>
</p>

[快速开始](#快速开始) · [详细文档](README.detailed.md) · [问题反馈](https://github.com/willsurpass/WSARTEX/issues) · [网站](https://willsurpass.com)

</div>

---

<table>
  <tr>
    <td width="50%" valign="top">
      <img src=".github/readme/feature-norma-2563eb.svg" alt="已内置 norma，开箱即用。" />
      <p>norma 核心 SDK 源码已随项目提供，无需单独下载或接入。配置 LLM 后即可开始使用。</p>
    </td>
    <td width="50%" valign="top">
      <img src=".github/readme/feature-easy-start-2563eb.svg" alt="上手容易，启动简单。" />
      <p><strong>无需 Docker，可直接部署。</strong> 运行 <code>start.py</code>，按提示安装依赖，启动器会构建前后端并打开面板。</p>
    </td>
  </tr>
</table>

## 快速开始

装好 Python 后，在项目目录中运行：

| 启动 | 停止 |
| :--- | :--- |
| 运行 `start.py` | 运行 `quit.py` |

首次启动需要联网安装依赖；`data/`、本地配置和登录签名密钥会自动生成。

## 首次使用

1. **设置登录密码** — 创建至少 **8 位**的密码，用户名固定为 **`WSARTEX`**。
2. **配置 LLM** — 打开「系统 → LLM」，填写服务商、模型和 API Key，按需填写 Base URL，保存后点击「设为激活」。
3. **创建任务** — 打开「任务」，填写本地隔离靶场的目标、范围和约束，然后启动。
4. **查看结果** — 在任务详情中查看执行过程、探索链路与发现。

## 文档与来源

功能介绍、配置、更新和技术架构见[详细版 README](README.detailed.md)。原项目参考 **ARTEX**，完整来源与第三方版权见 [NOTICE.md](NOTICE.md)。

**WSARTEX 完全开源**，采用 [AGPL-3.0-or-later](LICENSE)。维护者承诺不在项目中植入后门，欢迎审阅源码、启动脚本和依赖。

建议在本地隔离环境中学习与验证，实际使用须遵守法律并取得必要授权。

## 支持与反馈

如果 WSARTEX 对你有所帮助，或为你带来了灵感，欢迎点亮一颗 **Star**。也欢迎通过 [Issues](https://github.com/willsurpass/WSARTEX/issues) 反馈问题、提出优化建议，一起让项目变得更好。
