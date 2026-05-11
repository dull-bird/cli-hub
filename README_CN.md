# cli-hub

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
     │  cli-hub    │  ← 只有一个 Skill
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
openclaw skills install cli-hub

# 或手动安装
git clone https://github.com/dull-bird/cli-hub.git
cp -r cli-hub ~/.agents/skills/cli-hub
```

## 30 秒演示

```bash
# 1. 一键发现系统里所有 CLI 工具
$ python3 cli-registry.py discover

Found: jq ...    Registered: jq (15 subcommands, 8 flags)
Found: fzf ...   Registered: fzf (3 subcommands, 6 flags)
Found: gh ...    Registered: gh (25 subcommands, 0 flags)
Found: rg ...    Registered: rg (10 subcommands, 8 flags)
Found: mihomo ...Registered: mihomo (official skill: takes priority)
Found: opencli ..Registered: opencli (official skill: takes priority)
...

Registered 13 new CLI tools.

# 2. 查看注册了哪些工具
$ python3 cli-registry.py list

NAME          BINARY       OFFICIAL  SUBS  DESCRIPTION
─────────────────────────────────────────────────────────
curl          curl         -           0   External CLI: curl
gh            gh           -          25   External CLI: gh
git           git          -          19   Distributed version control
jq            jq           -          15   External CLI: jq
mihomo        mihomo       yes         0   External CLI: mihomo
opencli       opencli      yes         0   External CLI: opencli
...

# 3. 查看某个工具（子命令、参数、help）
$ python3 cli-registry.py lookup gh

# CLI: gh
Binary: gh

## Subcommands (25)
  auth              Authenticate gh with GitHub
  browse            Open the repository in the browser
  codespace         Connect to and manage codespaces
  gist              Manage gists
  issue             Manage issues
  pr                Manage pull requests
  release           Manage releases
  repo              Manage repositories
...
```

## Agent 实际交互演示

```
 👤 User:    "用 jq 把 data.json 里的所有 name 字段提取出来"
            ─────────────────────────────────────────────
 🤖 Agent:  [检查: ~/.agents/skills/jq/SKILL.md → 不存在]
            [查注册表: jq.json → 找到, 15 个子命令]
            [执行: jq '.[].name' data.json]
            ─────────────────────────────────────────────
            ["Alice", "Bob", "Charlie"]

 👤 User:    "用 gh 看看我 open 的 PR"
            ─────────────────────────────────────────────
 🤖 Agent:  [检查: ~/.agents/skills/gh/SKILL.md → 不存在]
            [查注册表: gh.json → 找到, 有 'pr' 子命令]
            [执行: gh pr list --state open]
            ─────────────────────────────────────────────
            #1 Add login page   about 2 hours ago
            #3 Fix navbar       about 1 day ago

 👤 User:    "切到日本节点"
            ─────────────────────────────────────────────
 🤖 Agent:  [检查: mihomo/SKILL.md → 存在!]
            [官方 Skill 优先]
            [执行: mihomo start; mihomo switch-node "日本 1 | SS | ZJ"]
```

## 优先级在行动

```
用户: "切到日本节点"
        │
        ├─ mihomo/SKILL.md  存在 → ✅ 直接用
        │  (手写的 Skill，知道 start/stop/sub/specific scripts)
        │
用户: "gh pr list"
        │
        ├─ gh/SKILL.md  不存在 → 跳过
        │  └─ registry/gh.json  存在 → ✅ 用注册表
        │     (缓存了 25 个 --help 子命令)
        │
用户: "xsv select name data.csv"
        │
        ├─ xsv/SKILL.md  不存在 → 跳过
        │  └─ registry/xsv.json  不存在 → 跳过
        │     └─ xsv --help  → ✅ 现场学习
        │        (解析输出，构造命令，顺手注册)
```

## 注册表格式

工具以简单 JSON 存在 `~/.openclaw/cli-registry/`：

```json
{
  "name": "jq",
  "binary": "jq",
  "description": "JSON 处理器",
  "official_skill": null,
  "auto_discovered": {
    "subcommands": [
      {"name": "filter", "desc": "Apply a filter to the input JSON"},
      {"name": "map", "desc": "Transform each element of an array"}
    ],
    "flags": [
      {"flag": "-r", "desc": "Raw output (no JSON quoting)"},
      {"flag": "-c", "desc": "Compact output"}
    ],
    "help_raw": "jq - commandline JSON processor ..."
  }
}
```

不用 YAML，不用 markdown。纯粹的机器可读数据，几百个工具也毫无压力。

完整示例见 [examples/registry-entry.json](examples/registry-entry.json)。

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
