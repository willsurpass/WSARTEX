# 来源、修改与第三方版权

## ARTEX

WSARTEX 是基于 **ARTEX** 修改的衍生项目，并非从零编写的独立实现。原始代码的版权归原作者及其贡献者所有；更改项目名称、模块路径或标识不改变原始代码的版权归属。

- 原始项目地址：[Autumn-27/ARTEX](https://github.com/Autumn-27/ARTEX)。该地址当前不可访问。
- 后续上游地址：[mhtsec/ARTEX](https://github.com/mhtsec/ARTEX)。该地址当前访问情况可能变化。
- 许可核对参考：[ARTEX 公开备份的 LICENSE](https://github.com/bookSiYi1412/ARTEX/blob/main/LICENSE)。该链接用于核对上游许可证，不表示本项目由该备份直接派生。
- 本项目继续采用 AGPL 许可体系，授权为 **AGPL-3.0-or-later**，完整条款见 [LICENSE](LICENSE)。

## WSARTEX 修改

Copyright (C) 2026 WSARTEX

上述版权声明仅针对 WSARTEX 贡献者拥有版权的新增和修改部分，不替代上游或第三方的版权声明。

截至 2026-10-18，本版本相对 ARTEX 的修改包括 WSARTEX 品牌与模块路径调整、启动和停止脚本、本地依赖组织、密码及数据清除流程、界面调整，以及文档整理。具体修改记录见本仓库 Git 历史和 [CHANGELOG.md](CHANGELOG.md)。

## 第三方组件

以下说明不替代组件随附的许可证；分发时应保留各组件要求的版权、许可及通知文件。

- **前端模板**：保留 [web/LICENSE](web/LICENSE) 中的 MIT License 与 `Copyright (c) 2024 Mohammed Arham Khan`。该许可证适用于相应的原始模板代码，并不表示整个 WSARTEX 前端均单独以 MIT 授权。
- **norma**：本项目包含 `third_party/norma/` 中的 SDK 源码，并修改了本地模块路径。原模块路径为 `github.com/Autumn-27/norma`；现有模块路径和目录位置不构成对原作者版权的转移。
- **acp-kernel**：WSARTEX 使用了 [acp-kernel](https://github.com/ranxianglei/acp-kernel) 衍生的上下文压缩实现及提示词，位于 `third_party/norma/noa/`。源码保留 `Copyright (c) 2026 ranxianglei`，完整上游许可及产品署名条款见 [LICENSE.acp-kernel](third_party/norma/noa/LICENSE.acp-kernel)。
- **Go 依赖**：`vendor/` 内各组件继续适用其随附的 LICENSE、COPYING、NOTICE 等文件。
- **npm 依赖**：按各依赖包自身的许可证使用和分发；根目录许可证不覆盖第三方包的独立授权。
