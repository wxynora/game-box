# React UI

`SeseBoardGame.tsx` 是涩涩走格棋的开源 React UI 组件。

它不依赖任何私有 app 代码。宿主应用只需要提供一个命令执行函数：

```tsx
import { SeseBoardGame, createHttpExecutor } from "./SeseBoardGame";

const executeCommand = createHttpExecutor("/api/games/sese-board-game");

export function GamePage() {
  return <SeseBoardGame executeCommand={executeCommand} />;
}
```

## Props

```ts
type SeseBoardGameProps = {
  executeCommand: (command: string) => Promise<SeseBoardPayload> | SeseBoardPayload;
  sendToAssistant?: (payload: SeseBoardPayload, context: AssistantContext) => Promise<string> | string;
  labels?: { title?: string };
  onBack?: () => void;
  className?: string;
  autoRunAssistant?: boolean;
};
```

必须提供：

- `executeCommand`: 把 `roll`、`choose xxx`、`submit xxx` 等命令交给宿主后端。

可选：

- `sendToAssistant`: 把 `payload.ai_text` 交给 AI 玩家，并返回 AI 回复。
  - `state_update` / 打回重写这类同步说明会拼进 `payload.ai_text` 的“本次说明”，宿主只发 `payload.ai_text` 即可，不要只发 `state`。
- `labels.title`: 自定义标题。
- `onBack`: 返回按钮。
- `autoRunAssistant`: 是否在预览/宿主里自动模拟 AI 操作。生产接入建议谨慎使用。

## AI 回复格式

组件会解析 AI 回复的第一行命令：

```text
【掷骰】
【选择：add_prop】
【剪刀石头布：石头】
【提交】
【真心话出题：题目内容】
【真心话回答：回答内容】
【描述：提交内容】
【通过：反馈内容】
【打回：反馈内容】
【Pass】
```

第一行之外的正文会被当成局内聊天内容。宿主保存聊天时，应该剥掉指令行。
`【描述：...】`、`【真心话出题：...】`、`【真心话回答：...】` 可以跨多行，组件会把后续正文一并当作提交内容，并剥掉末尾的 `】`。

验收规则：

- AI 打回真人提交时，回复 `【打回：反馈内容】`，真人重新提交后再交给 AI 验收。
- AI 通过真人提交时，回复两行：第一行 `【通过：反馈内容】`，第二行 `【掷骰】`。组件会先执行 `approve <反馈内容>`，再执行 AI 的 `roll`。
- 真人审批 AI 提交时，可以在任务弹窗里写一句反馈；通过反馈会在下次真人掷骰同步时顺带说明，打回反馈会立即同步给 AI。
- `【描述：...】` 只用于需要长篇正文的提交类惩罚；普通聊天、掷骰、选择、出拳、Pass 不要套 `【描述】`。

## Local Preview

预览目录在：

```text
frontend/preview
```

启动方式：

```bash
cd games/sese-board-game
python3 preview_server.py
```

另开终端：

```bash
cd games/sese-board-game/frontend/preview
npm install
npm run dev
```

打开：

```text
http://127.0.0.1:5176/
```

如果你不想重复安装 React/Vite，可以复用已有 `node_modules`：

```bash
cd games/sese-board-game
SESE_BOARD_NODE_MODULES=/path/to/node_modules \
  /path/to/node_modules/.bin/vite \
  --config frontend/preview/vite.config.mjs \
  --host 127.0.0.1 \
  --port 5176
```
