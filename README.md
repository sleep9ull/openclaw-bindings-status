# openclaw-bindings-status

一个面向 OpenClaw 的轻量 skill，用自然语言触发 `openclaw agents list --bindings` / `openclaw agents bindings`，把原始 CLI 输出整理成更直观的绑定状态看板。

## 能力

- 展示 agent 与 workspace 的概览
- 按 channel / account / peer scope 汇总绑定关系
- 输出易读的 Markdown 表格
- 生成可复制的 Mermaid 连线图
- 仅依赖 Python 标准库

## 适合的提问方式

- “帮我看看 OpenClaw 现在哪些 agent 绑定了哪些 channel”
- “把我的 openclaw bindings 状态可视化”
- “我想知道单聊、群聊分别路由到哪个 agent”
- “解释一下 `openclaw agents list --bindings` 现在的配置”

## 安装

把这个仓库放到你的 skills 目录，并保留目录名为 `openclaw-bindings-status`：

```bash
git clone <your-repo-url> "${CODEX_HOME:-$HOME/.codex}/skills/openclaw-bindings-status"
```

## 本地调试

如果本机 `openclaw` 已可用，直接运行：

```bash
python3 scripts/render_openclaw_bindings.py
```

如果你已经拿到了 JSON 输出，也可以走 stdin：

```bash
openclaw agents list --bindings --json | python3 scripts/render_openclaw_bindings.py --stdin
```

如果组合命令更稳定，也可以分两步让脚本自己回退：

```bash
python3 scripts/render_openclaw_bindings.py
```

## 仓库结构

- `SKILL.md`: skill 触发描述与工作流
- `agents/openai.yaml`: UI 元信息
- `scripts/render_openclaw_bindings.py`: 绑定状态渲染器
