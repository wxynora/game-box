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
【通过】
【不通过】
【不通过：原因】
【Pass】
```

第一行之外的正文会被当成局内聊天内容。宿主保存聊天时，应该剥掉第一行命令。

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
