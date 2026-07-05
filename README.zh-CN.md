# Codex Reasoning Sentinel

[English](README.md) | [简体中文](README.zh-CN.md)

Codex Reasoning Sentinel 是一个非官方的本地 Codex 插件项目，用来给“疑似浅推理”的回合加保护栏。它会读取 Codex hook 事件和 transcript token telemetry，在回合看起来可疑时要求模型多做一轮验证，并在可疑状态未解除前阻止高风险写入操作。

当前内置插件是 **Reasoning Guard**。

## 为什么做这个

对复杂重构、迁移、调试、数学推导这类任务来说，一个过短但很自信的答案可能比没有答案更糟糕：它可能在方案没验证之前就开始改文件。

Reasoning Guard 不声称能证明模型的隐藏推理质量。它做的是把一些实用的风险信号变成可见、可中断、可补救的流程：

- `reasoning_output_tokens` 落在低位可疑边界，比如 `516`、`1034`、`1552`
- 复杂任务低于可配置的 reasoning-token 阈值就结束
- 可疑回合之后准备执行写文件、patch、危险 shell 或 git 变更

## 功能

- 为复杂或高风险 prompt 注入 slow-path 上下文。
- 从 Codex transcript telemetry 检测低位可疑 reasoning-token 边界。
- 通过 `Stop` 和 `SubagentStop` hook 自动要求多做一轮验证。
- 当浅推理或边界信号持续存在时，把当前 session 标记为可疑。
- 可疑状态下阻止 `apply_patch`、写入型 MCP、危险 shell、会改变 git 状态的命令。
- 允许只读检查和常见测试命令继续执行，方便 agent 安全验证。
- 提供明确的 bypass/clear 语句。

## 安装

克隆仓库：

```bash
git clone https://github.com/DrSmoothl/codex-reasoning-sentinel.git
cd codex-reasoning-sentinel
```

注册本地 marketplace 并安装插件：

```bash
codex plugin marketplace add "$PWD"
codex plugin add reasoning-guard@codex-reasoning-sentinel
```

然后新开一个 Codex 会话。Codex 会要求你检查并信任插件自带的 hooks。

## 使用

安装后 Reasoning Guard 会通过 Codex lifecycle hooks 自动运行，不需要手动调用。

如果某一回合被判断为可疑，Stop hook 会返回 continuation prompt，让 Codex 在最终回答或继续动手前多做一轮验证。如果 session 仍处于可疑状态，写入型工具会被阻止，直到推理被修复或用户显式清除保护状态。

清除当前 session 状态：

```text
reasoning-guard: allow
reasoning-guard: clear
```

## 配置

hook 脚本支持这些环境变量：

| 变量 | 默认值 | 含义 |
| --- | --- | --- |
| `REASONING_GUARD_MIN_COMPLEX_REASONING` | `2000` | 复杂 prompt 后期望的最低 reasoning tokens。 |
| `REASONING_GUARD_BOUNDARY_MAX` | `1999` | 会被标记的最高低位边界值；调高后可以标记更高的 `518n - 2` 值。 |
| `REASONING_GUARD_ENFORCE_COMPLEX_MIN` | `1` | 设为 `0` 时只检查边界，不检查复杂任务阈值。 |
| `REASONING_GUARD_TOOL_POLICY` | `block-writes` | 设为 `block-all-shell` 时，可疑状态下 shell 策略更严格。 |
| `REASONING_GUARD_STATE_TTL_SECONDS` | `43200` | 可疑状态的过期时间。 |
| `REASONING_GUARD_DATA` | 未设置 | 可选的状态目录，本地测试时有用。 |

## 项目结构

```text
.
├── marketplace.json
├── plugins/
│   └── reasoning-guard/
│       ├── .codex-plugin/plugin.json
│       ├── hooks/hooks.json
│       ├── scripts/reasoning_guard.py
│       ├── skills/reasoning-guard/SKILL.md
│       └── tests/fixtures/
└── docs/
```

## 开发

检查 Python hook 语法：

```bash
python3 -m py_compile plugins/reasoning-guard/scripts/reasoning_guard.py
```

解析测试 fixture：

```bash
python3 plugins/reasoning-guard/scripts/reasoning_guard.py analyze \
  plugins/reasoning-guard/tests/fixtures/suspect-516.jsonl
```

如果本机有 Codex plugin validator，可以校验插件 manifest：

```bash
uv run --with pyyaml python /path/to/validate_plugin.py plugins/reasoning-guard
```

## 限制

- 插件不能强制模型内部一定使用某个隐藏 reasoning-token 数量。
- 插件不能证明模型推理一定正确。
- 插件不能拦截所有可能产生副作用的路径。
- 它依赖 Codex transcript telemetry；这个接口对 hook 很方便，但不是长期稳定的公共格式。
- 这是非官方社区项目，与 OpenAI 没有关联。

## 许可证

MIT。见 [LICENSE](LICENSE)。
