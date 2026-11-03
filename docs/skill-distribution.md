# Skill 分发说明

> 当前推荐使用 Web 管理台。本文件说明保留的兼容入口，其功能未随本次 Web 更新同步维护；使用前需核对实际代码，不应将参数或帮助检查通过视为平台流程可用。

## 当前已提供的内容

OmniPost 源码包含四个 CLI Skill：

| 平台 | 目录 | CLI |
| --- | --- | --- |
| 抖音 | `skills/douyin-upload/` | `sau douyin` |
| 快手 | `skills/kuaishou-upload/` | `sau kuaishou` |
| 小红书 | `skills/xiaohongshu-upload/` | `sau xiaohongshu` |
| Bilibili | `skills/bilibili-upload/` | `sau bilibili` |

视频号已有 `sau tencent` CLI，暂无独立 Skill。当前 CLI 没有 `skill` 子命令，也没有实现 `sau skill install`。源码安装、CLI 命令注册和 Skill 安装是不同步骤。

## 当前使用方式

1. 按 [README](../README.md#安装) 安装运行环境，确认目标平台的 CLI 帮助可用。
2. 在仓库内使用时，按需读取对应的 `SKILL.md`、运行前提、命令契约和故障排查参考。
3. 如果目标 Agent 支持从个人技能目录发现 Skill，可按该客户端的安装方式复制整个 Skill 目录；保留 `SKILL.md`、`references/` 和 `scripts/` 的相对结构。
4. 单独复制 Skill 不会安装 OmniPost、Chrome、Python 依赖或 CLI。Skill 仍需要可用的 `sau`，或者能在源码根目录通过 `uv run --no-sync sau ...` 调用。

现有 Skill 的脚本示例不是自动安装器。复制到仓库外之后，若要使用项目虚拟环境，应明确进入 OmniPost 源码根目录。

## 后续规划

以下内容尚未实现，不作为当前安装步骤：

- CLI 提供显式的 Skill 安装、更新和冲突处理子命令。
- 将 Skill 资源纳入可发布的软件包，并验证安装后仍可定位参考文件。
- 增加独立的视频号 Skill。
- 版本化 Skill 与 CLI 的兼容关系，并验证发行包安装流程。

当前文档仅承诺这里描述的源码安装方式，不将 PyPI 同名包作为当前源码的替代安装入口。实际发布包及安装器完成后，再补充经过验证的用户命令。
