# external-cli

> 一个 Skill 管所有 CLI。

一个 [OpenClaw AgentSkill](https://agentskills.io)，让 AI Agent 用统一接口操作**任何**系统里的 CLI 工具——不用再为每个工具手写 Skill。

**痛点：** 每个 CLI 工具都要一个 `SKILL.md`，Agent 才会用。20 个工具 = 20 个 Skill = 维护噩梦。

**方案：** 一个 Skill + 轻量注册表。Agent 按优先级查询：**官方 Skill → 注册表 → 实时 `--help`**。官方 Skill 永远优先，其他全部自动发现。

## 工作原理

```
用户: "用 jq 提取 name 字段"
              │
              ▼
     ┌─────────────────┐
     │  external-cli    │  ← 只有一个 Skill
     └────────┬────────┘
              │
     ┌────────▼──────────┐
     │ 1. 官方 Skill？    │  ~/.agents/skills/<tool>/SKILL.md 存在？
     │    → 优先使用      │
     ├────────────────────┤
     │ 2. 注册表 JSON？   │  ~/.openclaw/cli-registry/<tool>.json
     │    → 缓存的 help   │
     ├────────────────────┤
     │ 3. 现场 --help     │  跑 <tool> --help 当场学
     └────────────────────┘
```

## 安装

```bash
# 通过 ClawHub（推荐）
openclaw skills install external-cli

# 或手动安装
git clone https://github.com/dull-bird/external-cli.git
cp -r external-cli ~/.agents/skills/external-cli
```

## 快速上手

```bash
# 自动扫描系统中的所有 CLI 工具
python3 ~/.agents/skills/external-cli/scripts/cli-registry.py discover

# 注册指定工具
python3 ~/.agents/skills/external-cli/scripts/cli-registry.py register jq --desc "JSON 处理器"

# 列出已注册的工具
python3 ~/.agents/skills/external-cli/scripts/cli-registry.py list

# 查看工具详情（命令、参数、help）
python3 ~/.agents/skills/external-cli/scripts/cli-registry.py lookup git
```

## 优先级机制

| 优先级 | 来源 | 条件 |
|--------|------|------|
| 🥇 最高 | 官方 `SKILL.md` | `~/.agents/skills/<tool>/SKILL.md` 存在 |
| 🥈 中等 | 注册表 JSON | 工具已注册且缓存了 help |
| 🥉 最低 | 实时 `--help` | 任何未注册的工具都能现场学 |

官方 Skill 永远优先。CLI 作者以后出了官方 Skill，注册表自动退让，无需额外清理。

## 注册表格式

工具以简单 JSON 存在 `~/.openclaw/cli-registry/`：

```json
{
  "name": "jq",
  "binary": "jq",
  "description": "JSON 处理器",
  "official_skill": null,
  "auto_discovered": {
    "subcommands": [...],
    "flags": [...],
    "help_raw": "..."
  }
}
```

没有 YAML，没有 markdown，纯粹的机器可读数据。轻量到可以管理几百个工具。

## 命令一览

| 命令 | 说明 |
|------|------|
| `register <name>` | 注册 CLI 工具（自动提取 help、子命令、参数） |
| `list` | 列出所有已注册工具 |
| `lookup <name>` | 查看工具详细信息 |
| `discover` | 自动扫描已知路径并注册 |
| `remove <name>` | 从注册表移除 |
| `help <name>` | 实时获取 `--help` 输出 |

## 为什么不写 N 个 Skill？

- **爆炸：** 20 个 CLI = 20 个 Skill 文件，维护成本太高
- **过时：** 工具更新后 Skill 滞后 → `--help` 永远是最新的
- **官方优先：** CLI 作者可能推出更好的官方 Skill → 优先级机制自动适配
- **零门槛：** 装完跑一次 `discover`，所有工具当场可用

可以理解为 `opencli external register` 的 AI Agent 版本。

## 相关链接

- [OpenClaw Skills 文档](https://docs.openclaw.ai/tools/skills)
- [AgentSkills 规范](https://agentskills.io)
- [ClawHub](https://clawhub.ai)
- 灵感来源：[prefrontalsys/register-tool](https://github.com/prefrontalsys/register-tool)（Claude Code 版）
