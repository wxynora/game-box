import React from "react";
import { createRoot } from "react-dom/client";
import { SeseBoardGame, type AssistantContext, type SeseBoardPayload } from "../../SeseBoardGame";

const API_BASE = "http://127.0.0.1:8766";
const RPS = ["石头", "剪刀", "布"];

async function executeCommand(command: string): Promise<SeseBoardPayload> {
  const response = await fetch(`${API_BASE}/command`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command }),
  });
  return response.json();
}

function fakeAssistant(payload: SeseBoardPayload, context: AssistantContext): string {
  const pending = payload.state?.pending_event;
  if (context.mode === "final_note") return "收到了，准备按终局小纸条继续。";
  if (context.mode === "chat") return "收到，这里是开源预览里的对方回复。";
  if (pending?.type === "duel") {
    const pick = RPS[Math.floor(Math.random() * RPS.length)];
    return `【剪刀石头布：${pick}】\n【描述：预览对方出拳。】`;
  }
  if (pending?.type === "choice") {
    const choice = pending.choices?.[0]?.id || pending.choices?.[0]?.label || "";
    return `【选择：${choice}】\n【描述：预览对方选择。】`;
  }
  if (pending?.type === "review") {
    if (pending.phase === "questioning") {
      return "【提交】\n【描述：你现在最想知道对方哪件没说出口的事？】";
    }
    if (pending.phase === "submitted") return "【通过】\n【描述：预览对方通过。】";
    return "【提交】\n【描述：我按当前主题完成了任务，提交给对方验收。】";
  }
  if (payload.state?.turn_actor === "ai") return "【掷骰】\n【描述：预览对方掷骰。】";
  return "现在轮到你操作。";
}

function App() {
  return (
    <SeseBoardGame
      executeCommand={executeCommand}
      sendToAssistant={fakeAssistant}
      autoRunAssistant={false}
      labels={{ title: "涩涩走格棋 开源预览" }}
    />
  );
}

createRoot(document.getElementById("root")!).render(<App />);
