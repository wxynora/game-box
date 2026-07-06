# Sese Board Game / 涩涩走格棋

一个可以嵌进聊天产品、小游戏大厅或独立网页里的成人向走格棋。

它的核心不是绑定某个私有后端，而是提供一套可移植的规则引擎：

- Python 规则引擎负责掷骰、格子事件、卡池、待处理任务、状态、终局小纸条。
- React UI 负责棋盘、骰子、抽卡、任务弹窗、聊天入口、终局弹窗。
- 接入方只需要提供一个 `executeCommand(command)`，把前端命令交给自己的后端执行。
- AI 玩家可以通过普通聊天回复第一行指令，不强制走工具调用。

这个仓库里的内容是开源样例版。它不包含私有聊天系统、记忆系统、身体状态系统、部署路由、账号配置、私有名字或私有频道逻辑。

## 适合什么场景

- 两个真人玩家，用前端按钮轮流操作。
- 真人 + AI 玩家，真人点按钮，AI 在聊天回复里发游戏指令。
- 自己的后端已经有聊天链路，只想嵌一个小游戏。
- 想把规则引擎接成工具调用，但前端仍然由玩家操作。
- 想替换成自己的主题、任务、道具、状态文案。

## 项目结构

```text
games/sese-board-game/
  README.md
  manifest.json
  preview_server.py
  sese_board_game/
    __init__.py
    cards.py
    engine.py
    tool_adapter.py
  frontend/
    README.md
    SeseBoardGame.tsx
    preview/
      index.html
      package.json
      src/main.tsx
      vite.config.mjs
  tests/
    test_engine.py
```

核心文件：

- `sese_board_game/engine.py`: 游戏规则、存档、命令入口。
- `sese_board_game/cards.py`: 主题、道具、限制、任务、卡池语料。
- `sese_board_game/tool_adapter.py`: 可选工具适配层。
- `frontend/SeseBoardGame.tsx`: 可复用 React 组件。
- `preview_server.py`: 本地预览 API，不是生产后端。

## 本地预览

在游戏目录启动 Python 预览 API：

```bash
cd games/sese-board-game
python3 preview_server.py
```

另开一个终端启动前端预览：

```bash
cd games/sese-board-game/frontend/preview
npm install
npm run dev
```

打开：

```text
http://127.0.0.1:5176/
```

如果你已经有一个装好 React/Vite 的 `node_modules`，可以复用它，不必重复安装：

```bash
cd games/sese-board-game
SESE_BOARD_NODE_MODULES=/path/to/node_modules \
  /path/to/node_modules/.bin/vite \
  --config frontend/preview/vite.config.mjs \
  --host 127.0.0.1 \
  --port 5176
```

预览 API 默认保存到系统临时目录：

```text
<tmp>/sese-board-game-preview.json
```

这只是方便试玩。生产接入时请自己决定每局游戏的存档路径或数据库结构。

## Python 规则引擎

最小用法：

```python
from sese_board_game.engine import run_command

save_path = "./demo-game.json"

payload = run_command("new_game seed=demo", save_path=save_path)
print(payload["text"])

payload = run_command("roll 4", save_path=save_path)
print(payload["state"]["positions"])
```

如果只想拿一段可读文本，可以用 `cmd()`：

```python
from sese_board_game.engine import cmd

print(cmd("status", save_path="./demo-game.json"))
```

常用命令：

```text
status
open
new_game
new_game seed=demo
new_game seed=demo size=36
roll
roll 3
submit <内容>
approve
reject
reject <原因>
choose <选项id>
pass
append_final_status prop <道具名>
remove_final_status prop <道具名>
final_note_sent
end_game
```

说明：

- `roll`: 当前行动者掷骰。
- `roll 3`: 指定骰子点数，适合测试。
- `submit`: 提交惩罚任务、真心话回答或出题内容。
- `approve`: 验收通过。
- `reject`: 打回任务，对方需要重新提交。
- `choose`: 选择惩罚、剪刀石头布出拳都走这个命令。
- `pass`: 使用 Pass 卡跳过一个惩罚任务。
- `append_final_status`: 终局小纸条阶段给目标玩家追加道具。
- `final_note_sent`: 宿主应用把终局小纸条发给 AI/对方后，可调用它标记已发送。

## 返回 Payload

`run_command()` 返回结构化 payload，前端和后端都应该读这个，而不是解析大段文本。

主要字段：

```python
{
    "ok": True,
    "game_id": "sese_board_game",
    "command": "roll",
    "text": "...",
    "player_text": "...",
    "ai_text": "...",
    "board": {
        "size": 36,
        "cells": [...]
    },
    "state": {
        "board_size": 36,
        "positions": {"player": 0, "ai": 0},
        "turn_actor": "player",
        "statuses": {"player": [], "ai": []},
        "final_note_items": [],
        "hands": {"player": {"pass": 0}, "ai": {"pass": 0}},
        "pass_skips_used": 0,
        "pending_event": None,
        "theme_profile": {...},
        "theme_options": [...],
        "cell_events": [...],
        "game_over": False,
        "winner": "",
        "final_note": None
    }
}
```

字段用途：

- `text`: 默认视角文本。
- `player_text`: 给真人玩家看的文本。
- `ai_text`: 给 AI 玩家看的文本，名称和视角会换成 AI 视角。
- `board.cells`: 完整棋盘，包含空格、起点、终点。
- `state.cell_events`: 非空事件格，适合前端渲染格子类型。
- `state.pending_event`: 当前待处理任务，例如选择、验收、出题、剪刀石头布。
- `state.final_note`: 终局小纸条，游戏结束后生成。

不要把 `board`、`state`、工具结果、完整 prompt 直接塞进普通聊天记录或长期记忆。它们是游戏控制上下文，不是普通对话。

## 棋盘规则

默认棋盘是 36 格，1 是起点，36 是终点。

当前默认布局：

```text
1  起点
2  空
3  道具停步
4  惩罚任务
5  奖励抽卡
6  限制拖回
7  空
8  解除状态
9  选择惩罚
10 自己后退
11 惩罚任务
12 奖励前进
13 对方后退
14 状态延长
15 位置交换
16 空
17 道具停步
18 替换地点
19 空
20 惩罚任务
21 选择惩罚
22 奖励抽卡
23 解除状态
24 最终姿势
25 空
26 惩罚任务
27 重回起点
28 空
29 状态延长
30 选择惩罚
31 限制拖回
32 奖励抽卡
33 终局惩罚
34 道具停步
35 最终整理
36 终点
```

目前空格是 6 个：`2, 7, 16, 19, 25, 28`。

如果两名玩家落在同一格，会触发剪刀石头布对抗：

- 真人先在前端选 `石头 / 剪刀 / 布`。
- 后端把待处理事件交给 AI 玩家。
- AI 回复 `【剪刀石头布：石头】` 这类指令。
- 系统判定胜负。
- 赢方前进 3 格，输方后退 3 格。

## 卡池和状态

### 奖励卡

当前奖励卡池主要是 Pass 卡。

Pass 卡规则：

- 玩家可以持有 Pass 卡。
- 每局最多只能成功跳过 1 次惩罚任务。
- 没有 Pass 卡时不能使用。
- 成功使用后会消耗一张 Pass 卡。

### 惩罚任务

惩罚任务会创建 `pending_event`，一般需要提交内容，部分任务需要对方验收。

常见流程：

```text
roll -> 触发惩罚任务 -> submit <内容> -> 对方 approve/reject
```

如果对方 `reject`，任务不会结束，需要重新 `submit`。
如果对方 `approve` 后轮到对方继续行动，对方应该在同一条回复里继续给出 `roll` 指令。

真心话类任务有出题阶段：

```text
roll -> 触发真心话 -> 对方 submit <题目> -> 玩家 submit <回答>
```

### 选择惩罚

选择惩罚会给出多个选项，当前行动者使用：

```text
choose <选项id>
```

选项可能包括追加道具、追加限制、调整现有状态等。某些选项会根据当前状态动态过滤，例如没有可调档位的状态时，不会提供档位上调。

### 状态

状态分几类：

- `prop`: 道具状态。
- `limit`: 限制状态。
- `place`: 最终地点素材。
- `pose`: 最终姿势素材。

`place` 和 `pose` 不是某个玩家身上的状态，它们用于终局小纸条。

## 终局小纸条

谁先到终点，谁获胜。

终局规则：

- 获胜者的位置固定为终点。
- 获胜者身上的状态会清空。
- 系统会根据另一名玩家身上的状态、最终地点、最终姿势、当前主题生成 `final_note`。
- 前端应该用弹窗展示终局小纸条。
- 宿主应用点击发送后，可以调用 `final_note_sent` 标记已发送。

如果真人玩家获胜，且对方没有足够状态，前端可以允许真人在终局小纸条里追加道具状态：

```text
append_final_status prop 眼罩
append_final_status prop 跳蛋:2
remove_final_status prop 眼罩
```

开源 UI 里提供了一个简单的玩具控制台示例。宿主可以替换成自己的道具选择器。

## 推荐 AI 聊天接入方式

最顺的方式不是让 AI 每次都自动工具循环，而是让 AI 在普通聊天里用第一行自然文字指令。

推荐循环：

1. 真人在前端点击按钮，例如掷骰。
2. 前端调用宿主后端。
3. 宿主后端执行 `run_command("roll", save_path=...)`。
4. 前端用 `payload.state` 刷新 UI。
5. 如果轮到 AI 或需要 AI 处理任务，把 `payload["ai_text"]` 发进 AI 的下一轮上下文。
6. AI 回复时，第一行必须是游戏指令，后面才是普通聊天。
7. 宿主通常只解析第一行指令；唯一例外是 AI 验收通过真人任务时，可以同条回复 `【通过】` 和 `【掷骰】`，宿主应先执行 `approve` 再执行 `roll`。
8. 保存局内聊天时，把第一行指令剥掉，只保存正文。
9. 如果执行后轮到真人，就停下来等真人。
10. 如果 AI 因暂停状态连续无法行动，宿主可以继续执行 `roll` 消耗停步，直到轮到真人或 AI 恢复行动。

AI 回复示例：

```text
【掷骰】
这次轮到我了，我先走。
```

应该保存为局内聊天的只有：

```text
这次轮到我了，我先走。
```

不要把 `【掷骰】` 存进普通聊天。

### 支持的 AI 指令

```text
【掷骰】
【选择：add_prop】
【剪刀石头布：石头】
【剪刀石头布：剪刀】
【剪刀石头布：布】
【提交】
【真心话出题：题目内容】
【真心话回答：回答内容】
【描述：提交内容】
【通过】
【打回】
【Pass】
```

说明：

- `【提交】` 后面的正文会作为 `submit <正文>`。
- `【真心话出题：...】` 和 `【真心话回答：...】` 会作为 `submit ...`，用于真心话出题和回答。
- `【描述：...】` 只用于需要长篇正文的提交类惩罚，例如 `反向诱惑`、`全部暴露！`、`羞耻台词大放送`、`自慰陈述`。
- `【打回】` 会作为 `reject`；打回后对方需要重新提交，不掷骰。
- AI 验收真人提交时，如果通过，应回复两行：第一行 `【通过】`，第二行 `【掷骰】`；宿主先执行 `approve`，再执行 `roll`。
- `【选择：...】` 会作为 `choose ...`。
- `【剪刀石头布：...】` 也是 `choose ...`，只是用于对抗事件。

如果第一行不是合法指令，不要改变游戏状态，只当普通局内聊天处理。

### 最小宿主伪代码

```python
from sese_board_game.engine import run_command


def handle_human_roll(save_path, call_ai):
    payload = run_command("roll", save_path=save_path)
    show_frontend(payload["state"])

    if should_send_to_ai(payload):
        ai_message = call_ai(payload["ai_text"])
        return handle_ai_message(ai_message, save_path)

    return payload


def handle_ai_message(content, save_path):
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    first_line = lines[0] if lines else ""
    other_lines = lines[1:]
    chat_lines = [line for line in other_lines if line != "【掷骰】"]
    chat_text = "\n".join(chat_lines).strip()

    command = None
    if first_line == "【掷骰】":
        command = "roll"
    elif first_line.startswith("【选择：") and first_line.endswith("】"):
        command = "choose " + first_line.removeprefix("【选择：").removesuffix("】").strip()
    elif first_line.startswith("【剪刀石头布：") and first_line.endswith("】"):
        command = "choose " + first_line.removeprefix("【剪刀石头布：").removesuffix("】").strip()
    elif first_line.startswith("【真心话出题：") and first_line.endswith("】"):
        command = "submit " + first_line.removeprefix("【真心话出题：").removesuffix("】").strip()
    elif first_line.startswith("【真心话回答：") and first_line.endswith("】"):
        command = "submit " + first_line.removeprefix("【真心话回答：").removesuffix("】").strip()
    elif first_line.startswith("【描述：") and first_line.endswith("】"):
        command = "submit " + first_line.removeprefix("【描述：").removesuffix("】").strip()
    elif first_line == "【提交】":
        command = "submit " + chat_text
    elif first_line == "【通过】":
        command = "approve"
    elif first_line == "【打回】":
        command = "reject " + chat_text if chat_text else "reject"
    elif first_line in {"【Pass】", "【PASS】"}:
        command = "pass"

    if not command:
        save_ingame_chat(content)
        return run_command("status", save_path=save_path)

    payload = run_command(command, save_path=save_path)
    if first_line == "【通过】" and "【掷骰】" in other_lines and payload["state"]["turn_actor"] == "ai":
        payload = run_command("roll", save_path=save_path)
    if chat_text:
        save_ingame_chat(chat_text)
    return payload
```

关键点：

- 一条 AI 消息通常只执行一个游戏命令；唯一例外是 `【通过】` 后同条带 `【掷骰】`。
- 命令行要剥离，避免污染局内聊天。
- `payload["ai_text"]` 是游戏上下文，不等于普通聊天历史。
- 游戏日志、状态、棋盘 JSON 不要归档进普通近期记忆。
- 真正要进入普通聊天历史的，应该只是剥掉命令后的玩家可见聊天正文。

## React UI 接入

`frontend/SeseBoardGame.tsx` 导出：

```ts
SeseBoardGame
createHttpExecutor
parseAssistantTurn
parseAssistantCommand
```

最小接入：

```tsx
import { SeseBoardGame, createHttpExecutor } from "./SeseBoardGame";

const executeCommand = createHttpExecutor("/api/games/sese-board-game");

export function GamePage() {
  return <SeseBoardGame executeCommand={executeCommand} />;
}
```

如果宿主要接 AI 玩家：

```tsx
import {
  SeseBoardGame,
  type AssistantContext,
  type SeseBoardPayload,
} from "./SeseBoardGame";

async function executeCommand(command: string): Promise<SeseBoardPayload> {
  const response = await fetch("/api/games/sese-board-game/command", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command, save_id: "room-1" }),
  });
  return response.json();
}

async function sendToAssistant(payload: SeseBoardPayload, context: AssistantContext) {
  const response = await fetch("/api/assistant/game-message", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mode: context.mode,
      ai_text: payload.ai_text,
      state: payload.state,
    }),
  });
  const data = await response.json();
  return data.reply_text;
}

export function GamePage() {
  return (
    <SeseBoardGame
      executeCommand={executeCommand}
      sendToAssistant={sendToAssistant}
      labels={{ title: "涩涩走格棋" }}
    />
  );
}
```

`sendToAssistant` 可以不传。不传时，UI 只负责真人操作和显示当前游戏状态。

## HTTP 后端示例

下面是一个极简 Flask 示例，只演示命令转发。生产环境请自行处理用户、房间、鉴权和存档路径。

```python
from flask import Flask, jsonify, request
from sese_board_game.engine import run_command

app = Flask(__name__)


@app.post("/api/games/sese-board-game/command")
def sese_board_command():
    body = request.get_json(force=True, silent=True) or {}
    save_id = str(body.get("save_id") or "default")
    command = str(body.get("command") or "status")
    save_path = f"./data/sese-board-game/{save_id}.json"
    return jsonify(run_command(command, save_path=save_path))
```

如果你的前端使用 `createHttpExecutor(endpoint, saveId)`，接口需要接受：

```json
{
  "command": "roll",
  "save_id": "default"
}
```

并返回 `run_command()` 的 payload。

## 可选 Tool Adapter

如果你确实想把游戏接成模型工具，可以使用：

```python
from sese_board_game.tool_adapter import get_tools_for_inject, execute_tool

tools = get_tools_for_inject()
text_for_ai = execute_tool({
    "command": "roll",
    "save_path": "./demo-game.json",
})
```

注意：

- `execute_tool()` 返回的是给 AI 看的文本，不是完整 UI payload。
- 前端需要结构化状态时，请直接用 `run_command()`。
- 工具循环要小心结束条件。不要让 AI 连续工具调用把真人回合吃掉。
- 对真人玩家来说，前端按钮才是主要操作入口。

## 内容包怎么改

主要改 `sese_board_game/cards.py`。

常见修改点：

- `THEME_PROFILES`: 主题和主导方。
- `PROP_POOL`: 道具池。
- `LIMIT_POOL_BY_THEME`: 主题适用限制。
- `COMMON_LIMIT_POOL`: 通用限制。
- `PLACE_POOL`: 最终地点。
- `POSE_POOL`: 最终姿势。
- `REVIEW_PENALTY_CARDS`: 需要提交/验收的惩罚任务。
- `CHOICE_PENALTY_CARDS`: 选择类惩罚。

建议：

- 主题适用限制不要混用到无关主题。
- 地点和姿势是终局素材，不要当成某个玩家身上的普通状态。
- 道具是否有档位，应该由内容池或前端控制台明确区分。
- Pass 卡数量和跳过次数不要过多，否则惩罚任务会失去存在感。
- 开源包里不要提交私人名字、聊天记录、账号、token、部署地址。

## 开发和测试

运行 Python 测试：

```bash
python3 games/sese-board-game/tests/test_engine.py
```

编译检查：

```bash
python3 -m py_compile \
  games/sese-board-game/sese_board_game/engine.py \
  games/sese-board-game/sese_board_game/cards.py \
  games/sese-board-game/sese_board_game/tool_adapter.py \
  games/sese-board-game/preview_server.py
```

前端预览转换检查：

```bash
curl -s -o /tmp/sese-board-component.js \
  -w '%{http_code}\n' \
  'http://127.0.0.1:5176/@fs/<absolute-path>/games/sese-board-game/frontend/SeseBoardGame.tsx'
```

返回 `200` 表示 Vite 能读取并转换组件。

## 不包含什么

这个开源版不包含：

- 私有聊天窗口或私有联系人。
- Telegram/QQ/Discord 等具体渠道接入。
- 动态记忆、长期记忆、身体状态、召回、归档。
- 私有后端路由。
- 私有部署配置。
- 私有账号、token、cookie、日志。

接入方可以自由把它接到自己的后端。这个仓库只提供游戏本体、样例 UI 和接入边界。

## License

MIT
