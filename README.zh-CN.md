# openclaw-bindings-status

[English](./README.md)

`openclaw-bindings-status` 是一个轻量的 OpenClaw skill，用来把 `openclaw agents list --bindings` 的输出整理成更直观的状态看板。

它的目标不是让用户硬读原始 CLI 返回值，而是让用户直接用自然语言提问，例如哪个 agent 绑定了哪个 channel、单聊和群聊分别怎么路由、当前有哪些 workspace 正在参与绑定。

## 功能

- 用紧凑看板汇总 agent 和 workspace 状态
- 按 channel、account、peer scope 汇总绑定关系
- 输出可读性更好的 Markdown 表格
- 生成 Mermaid 连线图，便于快速查看路由关系
- 尽量少依赖，只使用 Python 标准库

## 适合的提问方式

- “帮我看一下 OpenClaw bindings 状态”
- “哪个 agent 绑定了 Telegram 群聊？”
- “把 OpenClaw agent 和 channel 的绑定关系可视化”
- “解释一下 `openclaw agents list --bindings` 的结果”

## 安装

把仓库 clone 到你的 skills 目录，并保留目录名 `openclaw-bindings-status`：

```bash
git clone https://github.com/sleep9ull/openclaw-bindings-status.git "${CODEX_HOME:-$HOME/.codex}/skills/openclaw-bindings-status"
```

## 使用方式

这个 skill 优先使用 JSON 输出，因为这样解析更稳定：

```bash
openclaw agents list --bindings --json
```

本地调试时，可以直接运行渲染脚本：

```bash
python3 scripts/render_openclaw_bindings.py
```

如果你已经拿到了 JSON 输出，也可以通过 stdin 输入：

```bash
openclaw agents list --bindings --json | python3 scripts/render_openclaw_bindings.py --stdin
```

也支持直接读取本地 JSON 文件：

```bash
python3 scripts/render_openclaw_bindings.py --from-json ./bindings.json
```

## 输出内容

渲染脚本会输出一个小型 Markdown 看板，包含：

- `Summary`：agent 数量、bindings 数量、channel 数量、通配绑定、peer scope 绑定等摘要
- `Agent Table`：每个 agent 的 workspace、是否默认、绑定数量、覆盖 channel
- `Wiring View`：逐行可读的路由关系
- `Mermaid`：可选的 `flowchart LR` 图
- `Notes`：对通配绑定、元数据缺失、未绑定 agent 的提示

## 限制说明

- 当前脚本最适合配合支持 JSON 输出的 `openclaw` 版本使用。
- 如果 `openclaw` 不在 `PATH` 中，可以改用 `--stdin` 或 `--from-json`。
- 不同 OpenClaw 版本的 JSON 字段名可能略有差异，后续可以基于真实输出继续微调映射规则。

## 仓库结构

- `SKILL.md`：skill 的触发条件和工作流说明
- `agents/openai.yaml`：skill 的 UI 元信息
- `scripts/render_openclaw_bindings.py`：OpenClaw bindings 渲染脚本

## License

[MIT](./LICENSE)
