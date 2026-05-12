# cli-hub

> 一个 Skill。系统里所有 CLI 工具。零配置。

```mermaid
graph LR
    CH["🔄 cli-hub<br/>一个 Skill<br/>管理所有 CLI"] --> git["🔀 git"]
    CH --> gh["🐙 gh"]
    CH --> docker["🐳 docker"]
    CH --> kubectl["☸️ kubectl"]
    CH --> ffmpeg["🎬 ffmpeg"]
    CH --> jq["🧩 jq"]
    CH --> curl["🌐 curl"]
    CH --> rg["🔎 rg"]
    CH --> python3["🐍 python3"]
    CH --> node["💚 node"]
    CH --> ssh["🔐 ssh"]
    CH --> more["📦 +50 more"]

    style CH fill:#4f46e5,color:#fff,stroke:#312e81
    style git fill:#f0fdf4,stroke:#22c55e,color:#166534
    style gh fill:#f0fdf4,stroke:#22c55e,color:#166534
    style docker fill:#f0fdf4,stroke:#22c55e,color:#166534
    style kubectl fill:#f0fdf4,stroke:#22c55e,color:#166534
    style ffmpeg fill:#f0fdf4,stroke:#22c55e,color:#166534
    style jq fill:#f0fdf4,stroke:#22c55e,color:#166534
    style curl fill:#f0fdf4,stroke:#22c55e,color:#166534
    style rg fill:#f0fdf4,stroke:#22c55e,color:#166534
    style python3 fill:#f0fdf4,stroke:#22c55e,color:#166534
    style node fill:#f0fdf4,stroke:#22c55e,color:#166534
    style ssh fill:#f0fdf4,stroke:#22c55e,color:#166534
    style more fill:#fef3c7,stroke:#f59e0b,color:#92400e
```

## 安装

```bash
npx skills add dull-bird/cli-hub
```

搞定。你的 AI Agent 从此知道怎么用系统里任何 CLI 工具。

兼容 55+ Agent：OpenClaw、Claude Code、Cursor、Gemini CLI、Copilot、Windsurf、Warp 等。

## 使用

你说话，Agent 自己找工具。

```
 👤  "统计 data.json 里还有几个没完成的待办"
 🤖  [cli-hub: 搜索 "json count filter" → jq]
     [cli-hub: jq 有 15 条命令, 关键词: json, filter, transform]
     > jq '[.[] | select(.completed==false)] | length' data.json
     3

 👤  "看看 docker 在跑什么容器"
 🤖  [cli-hub: 搜索 "container running" → docker]
     [cli-hub: docker 有 36 条命令, 关键词: container, image, run]
     > docker ps
     CONTAINER ID  IMAGE         STATUS       NAMES
     a1b2c3d4e5f6  nginx:latest  Up 2 hours   web

 👤  "切到日本节点"
 🤖  [cli-hub: mihomo/SKILL.md 存在 — 官方 Skill]
     [交给官方 Skill 处理]
     ✓ 已切换到 日本 1 | SS | ZJ
```

不需要配置。第一次用到某个工具时，Agent 当场通过 `--help` 学会并缓存。

> **可选：** 跑一次 `discover` 预先扫描 PATH 并预热缓存。不跑也能用——只是首次使用时稍慢一点。

---

## 原理（用户视角）

cli-hub 做三件事：

| 步骤 | 说明 |
|------|------|
| **1. 关键词匹配** | "提取 json" → 查 `~/.openclaw/cli-registry/.keywords.json` → 找到 jq |
| **2. 查手册** | 查 `jq.json` → 描述、子命令、参数、help 原文 |
| **3. 执行命令** | 拼出正确命令 + 参数，运行 |

如果工具还没注册，第 3 步退化为现场跑 `--help`，Agent 读完输出后当场学习。

## 架构（开发者视角）

### 三层知识系统

```
┌──────────────────────────────────────────────────┐
│ P0: 内建知识库                                     │
│     50+ 工具，手写描述 + 任务关键词                   │
│     （json → jq, http → curl, container → docker）│
├──────────────────────────────────────────────────┤
│ P1: 智能 help 提取                                │
│     _extract_summary() 解析 --help 输出            │
│     生成: summary, commands_text, options_text    │
├──────────────────────────────────────────────────┤
│ P2: 关键词反向索引                                 │
│     .keywords.json 映射 任务词 → 工具名             │
│     "video" → ffmpeg, "container" → docker       │
│     从 P0 + 描述分词自动构建                        │
└──────────────────────────────────────────────────┘
```

### 注册表条目结构

```json
{
  "name": "jq",
  "description": "命令行 JSON 处理器 — 过滤、转换、查询 JSON 数据",
  "keywords": ["json", "filter", "transform", "query"],
  "auto_discovered": {
    "version": "1.7.1",
    "summary": "Command-line JSON processor",
    "usage": "jq [options...] filter [files...]",
    "commands_text": "filter — 应用过滤器\nmap — 转换数组元素...",
    "options_text": "-r — 原始输出\n-c — 紧凑输出",
    "help_raw": "(清洗后的 --help 全文, 最多 5000 字符)",
    "subcommands": { "filter": {...}, "map": {...} }
  }
}
```

### 决策流程

```
用户: "提取 JSON 里的字段"
        │
    ┌───▼────────────────────────────┐
    │ 1. 明确提到了工具名？            │  "用 jq 提取..." → 跳步骤 3
    ├────────────────────────────────┤
    │ 2. 关键词搜索                   │  "json extract" → jq (匹配2), yq (1)
    │    → 匹配任务到工具              │
    ├────────────────────────────────┤
    │ 3. 检查官方 Skill              │  ~/.agents/skills/jq/SKILL.md?
    │    → 有则交给它                 │
    ├────────────────────────────────┤
    │ 4. 查注册表                     │  jq.json: 描述, 命令, help_raw
    │    → 构造命令                   │  未知工具则直接解析 help_raw
    ├────────────────────────────────┤
    │ 5. 现场 --help（兜底）          │  什么都没缓存 → 现场跑 --help
    │    → 学习 + 自动注册            │
    └────────────────────────────────┘
```

### 版本追踪

每个注册工具存储版本号（从 `<tool> --version` 提取）。`check-stale` 检测已过期的工具：

```bash
python3 cli-registry.py check-stale          # 列出过期工具
python3 cli-registry.py check-stale --update # 自动重注册
```

### 脚本命令

| 命令 | 说明 |
|------|------|
| `discover` | 扫描 PATH，注册所有已知工具 |
| `list` | 列出已注册工具及描述 |
| `lookup <名称>` | 完整信息：描述、关键词、命令、选项、help |
| `search <关键词>` | 按任务搜索工具（如 `search json extract`） |
| `check-stale` | 检测已更新的工具 |
| `register <名称>` | 手动注册 CLI 工具 |
| `remove <名称>` | 从注册表移除 |

### 未知工具的 help 解析

对于不在知识库（P0）中的工具，Agent 依赖 `help_raw`。SKILL.md 教会了 LLM 如何解析 help 输出：

1. 找到 usage 行（`tool [OPTIONS] COMMAND [ARGS]`）
2. 扫描命令区块（以 `:` 结尾的标题 + 缩进块）
3. 识别选项（`-x` 或 `--option` 开头的行）
4. 提取描述（第一个非 flag 的实质句子）

`commands_text` 和 `options_text` 提供了预解析的结构化摘要，大部分情况下 LLM 不需要从零解析原始 help。

## 相关链接

- [AgentSkills 规范](https://agentskills.io)
- [Vercel Skills](https://github.com/vercel-labs/skills) — `npx skills`
- 灵感来源：[prefrontalsys/register-tool](https://github.com/prefrontalsys/register-tool)
