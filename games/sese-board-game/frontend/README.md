# React UI

`SeseBoardGame.tsx` is a reusable React component for the open-source Sese
Board Game engine.

It does not import any private app code. Host apps provide the bridge:

```tsx
import { SeseBoardGame, createHttpExecutor } from "./SeseBoardGame";

const executeCommand = createHttpExecutor("/api/games/sese-board-game");

export function GamePage() {
  return <SeseBoardGame executeCommand={executeCommand} />;
}
```

For an automated counterpart, pass `sendToAssistant`. The component accepts
natural model text, but only bracketed command lines are executed:

```text
[ROLL]
[SUBMIT] text
[APPROVE]
[REJECT] reason
[CHOOSE] add_prop
[PASS]
```

Chinese private-style brackets are also parsed for convenience:

```text
【掷骰】
【提交】文本
【通过】
【驳回】理由
【选择】add_prop
【PASS】
```
