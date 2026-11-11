<div align="center">

<h1>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="web/public/brand/wordmark-white.svg" />
    <source media="(prefers-color-scheme: light)" srcset="web/public/brand/wordmark.svg" />
    <img src="web/public/brand/wordmark.svg" alt="WSARTEX" width="360" />
  </picture>
</h1>

[Chinese](README.md) · **English**

**An autonomous AI penetration testing system with a simple setup**

Self-hosted · Multi-agent collaboration · Asset discovery · Vulnerability management

<p>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-AGPL--3.0--or--later-18181b?style=flat-square" alt="License: AGPL-3.0-or-later" /></a>
  <a href="third_party/norma/README.md"><img src="https://img.shields.io/badge/norma-Built--in-238636?style=flat-square" alt="norma: Built-in" /></a>
  <a href="#quick-start"><img src="https://img.shields.io/badge/Deploy-Self--hosted-3578db?style=flat-square" alt="Deploy: Self-hosted" /></a>
</p>

[Quick start](#quick-start) · [Documentation (Chinese)](README.detailed.md) · [Report an issue](https://github.com/willsurpass/WSARTEX/issues) · [Website](https://willsurpass.com)

</div>

---

<table>
  <tr>
    <td width="50%" valign="top">
      <img src=".github/readme/feature-norma-en-2563eb.svg" alt="norma included. Ready to use." />
      <p>The norma SDK source is bundled with the project. No separate download or integration is needed. Configure your LLM to get started.</p>
    </td>
    <td width="50%" valign="top">
      <img src=".github/readme/feature-easy-start-en-2563eb.svg" alt="Easy setup. Simple startup." />
      <p><strong>Deploy directly without Docker.</strong> Run <code>start.py</code> and follow the prompts to install dependencies. The launcher builds the application and opens the panel.</p>
    </td>
  </tr>
</table>

## Quick start

Install Python, then run the following files from the project directory:

| Start | Stop |
| :--- | :--- |
| Run `start.py` | Run `quit.py` |

The first launch needs an internet connection to install dependencies. The `data/` directory, local configuration, and login signing key are generated automatically.

## First use

The panel currently uses Chinese labels. Menu names below are English translations for reference.

1. **Set your login password** — Create a password with at least **8 characters**. The username is **`WSARTEX`**.
2. **Configure your LLM** — Open **System → LLM**. Enter your provider, model, and API Key, set a Base URL if needed, save, and activate the profile.
3. **Create a task** — Open **Tasks**, specify the target, scope, and constraints for your isolated local lab, then start the task.
4. **Review results** — View the execution history, exploration graph, and findings in the task details.

<details>
<summary><strong>Clear data and restore the initial state</strong></summary>

Open **System → Settings → Clear all data**, enter your current login password, and confirm. The application returns to the initial password setup state. Data is **permanently deleted, without being moved to the trash or backed up automatically**.

</details>

## Documentation and credits

For features, configuration, updates, and architecture, see the [detailed README (Chinese)](README.detailed.md). This project is based on **ARTEX**. See [NOTICE.md](NOTICE.md) for upstream credits and third-party notices.

**WSARTEX is fully open source** under [AGPL-3.0-or-later](LICENSE). The maintainers commit to never adding backdoors. We welcome review of the source code, startup scripts, and dependencies.

Start with an isolated local lab. Any real-world use must comply with applicable laws and obtain the necessary authorization.

## Support and feedback

If WSARTEX has helped you or inspired an idea, consider giving the project a **Star**. Bug reports and suggestions for improvement are always welcome in [Issues](https://github.com/willsurpass/WSARTEX/issues).
