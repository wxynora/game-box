import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

export type Actor = "player" | "ai";

export type BoardCell = {
  position: number;
  kind?: string;
  name?: string;
  slot?: string;
  reward?: string;
  steps?: number;
};

export type StatusItem = {
  id?: string;
  slot?: string;
  label?: string;
  value?: string;
  duration_type?: string;
  remaining_actions?: number;
  blocks_action?: boolean;
  level?: number;
};

export type PendingChoice = {
  id?: string;
  label?: string;
  effect?: Record<string, unknown>;
};

export type PendingEvent = {
  id?: string;
  type?: "review" | "choice" | string;
  name?: string;
  actor?: Actor;
  reviewer?: Actor;
  phase?: "assigned" | "submitted" | string;
  task?: string;
  prompt?: string;
  submission?: string;
  submission_text?: string;
  pass_result?: string;
  reject_prompt?: string;
  pass_allowed?: boolean;
  cell?: number;
  theme?: string;
  reject_count?: number;
  choices?: PendingChoice[];
};

export type SeseBoardState = {
  board_size?: number;
  positions?: Partial<Record<Actor, number>>;
  turn_actor?: Actor;
  statuses?: Partial<Record<Actor, StatusItem[]>>;
  hands?: Partial<Record<Actor, Partial<Record<"pass", number>>>>;
  pending_event?: PendingEvent | null;
  theme_profile?: {
    id?: string;
    theme?: string;
    lead?: Actor | string;
    direction?: Actor | string;
    direction_label?: string;
  } | null;
  cell_events?: BoardCell[];
  game_over?: boolean;
  winner?: Actor | "";
  result?: string;
};

export type SeseBoardPayload = {
  ok?: boolean;
  game_id?: string;
  command?: string;
  text?: string;
  player_text?: string;
  ai_text?: string;
  board?: {
    size?: number;
    cells?: BoardCell[];
  };
  state?: SeseBoardState;
  game_over?: boolean;
  winner?: Actor | "";
  result?: string;
  error?: string;
};

export type AssistantContext = {
  mode: "turn" | "chat";
  message?: string;
};

export type SeseBoardLabels = Partial<Record<Actor, string>> & {
  title?: string;
  roll?: string;
  restart?: string;
  chat?: string;
  theme?: string;
  lead?: string;
  turn?: string;
  runAssistant?: string;
  usePass?: string;
  waitingFor?: string;
  waitingReview?: string;
  waitingSubmission?: string;
  approve?: string;
  reject?: string;
  submit?: string;
  noStatus?: string;
  message?: string;
  noAssistant?: string;
  back?: string;
  close?: string;
  gameBoard?: string;
  gameChat?: string;
  system?: string;
  noMessages?: string;
  start?: string;
  finish?: string;
  empty?: string;
  passCard?: string;
  actionLeft?: string;
  choicePenalty?: string;
  choosePenalty?: string;
  reviewTask?: string;
  rejectReason?: string;
  submitResponse?: string;
  ready?: string;
  gameOver?: string;
  noLead?: string;
  assistantCommandMissing?: string;
};

export type SeseBoardGameProps = {
  executeCommand: (command: string) => Promise<SeseBoardPayload> | SeseBoardPayload;
  sendToAssistant?: (payload: SeseBoardPayload, context: AssistantContext) => Promise<string> | string;
  labels?: SeseBoardLabels;
  title?: string;
  autoRunAssistant?: boolean;
  onBack?: () => void;
  className?: string;
};

type ChatMessage = {
  id: string;
  speaker: Actor | "system";
  text: string;
};

const DEFAULT_LABELS: Required<SeseBoardLabels> = {
  player: "你",
  ai: "对方",
  title: "涩涩走格棋",
  roll: "掷骰子",
  restart: "重新开始",
  chat: "交流",
  theme: "主题",
  lead: "主导方",
  turn: "轮到",
  runAssistant: "让对方行动",
  usePass: "使用 Pass 卡",
  waitingFor: "等待",
  waitingReview: "等待验收",
  waitingSubmission: "等待提交",
  approve: "通过",
  reject: "驳回",
  submit: "提交",
  noStatus: "无状态",
  message: "输入消息",
  noAssistant: "未接入对方适配器",
  back: "返回",
  close: "关闭",
  gameBoard: "棋盘",
  gameChat: "局内交流",
  system: "系统",
  noMessages: "暂无局内消息",
  start: "起点",
  finish: "终点",
  empty: "空",
  passCard: "Pass 卡",
  actionLeft: "剩余行动",
  choicePenalty: "选择惩罚",
  choosePenalty: "选择一项惩罚。",
  reviewTask: "验收任务",
  rejectReason: "可选：驳回理由",
  submitResponse: "提交内容",
  ready: "准备好了。",
  gameOver: "游戏结束。",
  noLead: "待定",
  assistantCommandMissing: "对方回复里没有可执行的括号指令。",
};

const STYLE_ID = "sese-board-game-style";

export function createHttpExecutor(endpoint: string, saveId = "default") {
  return async function executeCommand(command: string): Promise<SeseBoardPayload> {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command, save_id: saveId }),
    });
    if (!response.ok) {
      throw new Error(`Game request failed: ${response.status}`);
    }
    return (await response.json()) as SeseBoardPayload;
  };
}

export function parseAssistantCommand(text: string): string | null {
  const firstLine = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find(Boolean);
  if (!firstLine) return null;

  const bracket = firstLine.match(/^(?:\[([^\]]+)\]|【([^】]+)】)\s*(.*)$/);
  if (!bracket) return null;
  const raw = String(bracket[1] || bracket[2] || "").trim().toLowerCase();
  const arg = String(bracket[3] || "").trim();
  const normalized = raw.replace(/[：:]\s*$/, "");

  if (["roll", "dice", "掷骰", "掷骰子"].includes(normalized)) return arg ? `roll ${arg}` : "roll";
  if (["submit", "提交"].includes(normalized)) return `submit ${arg}`.trim();
  if (["approve", "通过"].includes(normalized)) return "approve";
  if (["reject", "驳回", "不通过"].includes(normalized)) return `reject ${arg}`.trim();
  if (["choose", "选择"].includes(normalized)) return `choose ${arg}`.trim();
  if (["pass", "跳过"].includes(normalized)) return "pass";

  const inlineChoice = raw.match(/^(choose|选择)\s*[:：]\s*(.+)$/);
  if (inlineChoice) return `choose ${inlineChoice[2]}`.trim();
  return null;
}

export function SeseBoardGame({
  executeCommand,
  sendToAssistant,
  labels,
  title,
  autoRunAssistant = true,
  onBack,
  className,
}: SeseBoardGameProps) {
  const mergedLabels: Required<SeseBoardLabels> = { ...DEFAULT_LABELS, ...labels, title: title || labels?.title || DEFAULT_LABELS.title };
  const [payload, setPayload] = useState<SeseBoardPayload | null>(null);
  const [busy, setBusy] = useState(false);
  const [rolling, setRolling] = useState(false);
  const [dice, setDice] = useState(1);
  const [reviewText, setReviewText] = useState("");
  const [rejectText, setRejectText] = useState("");
  const [chatOpen, setChatOpen] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const lastAssistantTurnKey = useRef("");

  useEffect(() => {
    ensureStyles();
  }, []);

  const run = useCallback(
    async (command: string, options: { animateDice?: boolean } = {}) => {
      setBusy(true);
      if (options.animateDice) {
        setRolling(true);
        setDice((value) => (value % 6) + 1);
      }
      try {
        const result = await executeCommand(command);
        setPayload(result);
        const diceMatch = String(result.text || "").match(/(?:掷出|rolled)\s+(\d+)/i);
        if (diceMatch) setDice(Number(diceMatch[1] || 1));
        if (!result.ok && result.text) {
          appendMessage(setMessages, "system", result.text);
        }
        return result;
      } finally {
        globalThis.setTimeout(() => setRolling(false), 360);
        setBusy(false);
      }
    },
    [executeCommand]
  );

  useEffect(() => {
    void run("status");
  }, [run]);

  const state = payload?.state;
  const pending = state?.pending_event || null;
  const turnActor = state?.turn_actor || "player";
  const boardSize = state?.board_size || payload?.board?.size || 36;
  const cells = payload?.board?.cells || state?.cell_events || [];
  const playerPos = clampPosition(state?.positions?.player, boardSize);
  const aiPos = clampPosition(state?.positions?.ai, boardSize);
  const playerPass = Number(state?.hands?.player?.pass || 0);
  const aiPass = Number(state?.hands?.ai?.pass || 0);

  const rows = useMemo(() => makeRows(cells, boardSize, 6), [cells, boardSize]);

  useEffect(() => {
    if (!sendToAssistant || !autoRunAssistant || busy || !payload?.state || payload.state.game_over) return;
    if (payload.state.pending_event && payload.state.pending_event.actor !== "ai" && payload.state.pending_event.reviewer !== "ai") return;
    if (payload.state.turn_actor !== "ai") return;
    const key = JSON.stringify({
      turn: payload.state.turn_actor,
      pos: payload.state.positions,
      pending: payload.state.pending_event?.id,
      phase: payload.state.pending_event?.phase,
    });
    if (lastAssistantTurnKey.current === key) return;
    lastAssistantTurnKey.current = key;
    void askAssistantForTurn(payload);
  }, [autoRunAssistant, busy, payload, sendToAssistant]);

  const askAssistantForTurn = useCallback(
    async (currentPayload: SeseBoardPayload) => {
      if (!sendToAssistant) return;
      setBusy(true);
      try {
        const reply = await sendToAssistant(currentPayload, { mode: "turn" });
        appendMessage(setMessages, "ai", reply);
        const command = parseAssistantCommand(reply);
        if (command) {
          await run(command, { animateDice: command.startsWith("roll") });
        } else {
          appendMessage(setMessages, "system", mergedLabels.assistantCommandMissing);
        }
      } finally {
        setBusy(false);
      }
    },
    [run, sendToAssistant]
  );

  const sendChat = useCallback(async () => {
    if (!sendToAssistant || !payload || !chatInput.trim()) return;
    const message = chatInput.trim();
    setChatInput("");
    appendMessage(setMessages, "player", message);
    setBusy(true);
    try {
      const reply = await sendToAssistant(payload, { mode: "chat", message });
      appendMessage(setMessages, "ai", reply);
    } finally {
      setBusy(false);
    }
  }, [chatInput, payload, sendToAssistant]);

  const canRoll = !busy && !state?.game_over && !pending && turnActor === "player";
  const canAskAi = Boolean(sendToAssistant && !busy && !state?.game_over && turnActor === "ai");

  return (
    <section className={["sbg-root", className || ""].filter(Boolean).join(" ")}>
      <header className="sbg-header">
        <div className="sbg-header-actions">
          {onBack ? (
            <button className="sbg-icon-button" type="button" onClick={onBack} aria-label={mergedLabels.back}>
              <BackIcon />
            </button>
          ) : (
            <span />
          )}
          <h1>{mergedLabels.title}</h1>
          <button className="sbg-icon-button" type="button" onClick={() => setChatOpen(true)} aria-label={mergedLabels.chat}>
            <ChatIcon />
          </button>
        </div>
        <div className="sbg-score">
          <InfoBlock label={mergedLabels.theme} value={state?.theme_profile?.theme || "未触发"} />
          <InfoBlock label={mergedLabels.lead} value={leadLabel(state, mergedLabels)} />
          <InfoBlock label={mergedLabels.player} value={`${playerPos}/${boardSize}`} />
          <InfoBlock label={mergedLabels.ai} value={`${aiPos}/${boardSize}`} />
          <div className="sbg-turn">
            {mergedLabels.turn}: {actorName(turnActor, mergedLabels)}
          </div>
        </div>
      </header>

      <main className="sbg-main">
        <div className="sbg-board" aria-label={mergedLabels.gameBoard}>
          {rows.map((row, rowIndex) => (
            <div className="sbg-row" key={`row-${rowIndex}`}>
              {row.map((cell) => (
                <BoardTile
                  key={cell.position}
                  cell={cell}
                  boardSize={boardSize}
                  hasPlayer={pieceOnCell(playerPos, cell.position)}
                  hasAi={pieceOnCell(aiPos, cell.position)}
                  labels={mergedLabels}
                />
              ))}
            </div>
          ))}
        </div>

        <div className="sbg-status-grid">
          <StatusCard actor="player" labels={mergedLabels} statuses={state?.statuses?.player || []} passCount={playerPass} />
          <StatusCard actor="ai" labels={mergedLabels} statuses={state?.statuses?.ai || []} passCount={aiPass} />
        </div>

        {pending ? (
          <PendingPanel
            pending={pending}
            labels={mergedLabels}
            reviewText={reviewText}
            rejectText={rejectText}
            playerPass={playerPass}
            busy={busy}
            onReviewText={setReviewText}
            onRejectText={setRejectText}
            onRun={async (command) => {
              const result = await run(command);
              if (command.startsWith("submit")) setReviewText("");
              if (command.startsWith("reject")) setRejectText("");
              return result;
            }}
          />
        ) : null}

        {state?.game_over ? <div className="sbg-result">{state.result || mergedLabels.gameOver}</div> : null}

        <div className="sbg-controls">
          <div className={["sbg-dice", rolling ? "is-rolling" : ""].join(" ")} aria-label={`${mergedLabels.roll} ${dice}`}>
            {dice}
          </div>
          <button className="sbg-primary" type="button" disabled={!canRoll} onClick={() => run("roll", { animateDice: true })}>
            {mergedLabels.roll}
          </button>
          {canAskAi ? (
            <button className="sbg-secondary" type="button" onClick={() => payload && askAssistantForTurn(payload)}>
              {mergedLabels.runAssistant}
            </button>
          ) : null}
          <button className="sbg-secondary" type="button" disabled={busy} onClick={() => run("new_game")}>
            {mergedLabels.restart}
          </button>
        </div>

        <p className="sbg-recent">{recentLine(payload?.text, mergedLabels.ready)}</p>
      </main>

      {chatOpen ? (
        <div className="sbg-modal" role="dialog" aria-modal="true" aria-label={mergedLabels.gameChat}>
          <div className="sbg-chat">
            <div className="sbg-chat-head">
              <strong>{mergedLabels.chat}</strong>
              <button className="sbg-icon-button" type="button" onClick={() => setChatOpen(false)} aria-label={mergedLabels.close}>
                <CloseIcon />
              </button>
            </div>
            <div className="sbg-chat-body">
              {messages.length ? (
                messages.map((message) => (
                  <div className={`sbg-message is-${message.speaker}`} key={message.id}>
                    <span>{message.speaker === "system" ? mergedLabels.system : actorName(message.speaker, mergedLabels)}</span>
                    <p>{message.text}</p>
                  </div>
                ))
              ) : (
                <p className="sbg-empty">{mergedLabels.noMessages}</p>
              )}
            </div>
            <div className="sbg-chat-input">
              <input
                value={chatInput}
                onChange={(event) => setChatInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void sendChat();
                }}
                disabled={!sendToAssistant || busy}
                placeholder={sendToAssistant ? mergedLabels.message : mergedLabels.noAssistant}
              />
              <button className="sbg-icon-button is-solid" type="button" disabled={!sendToAssistant || busy || !chatInput.trim()} onClick={() => void sendChat()}>
                <SendIcon />
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="sbg-info">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function BoardTile({
  cell,
  boardSize,
  hasPlayer,
  hasAi,
  labels,
}: {
  cell: BoardCell;
  boardSize: number;
  hasPlayer: boolean;
  hasAi: boolean;
  labels: Required<SeseBoardLabels>;
}) {
  const kind = cell.position === 1 ? "start" : cell.position === boardSize ? "finish" : cell.kind || "empty";
  return (
    <div className={`sbg-tile kind-${kind}`}>
      <span className="sbg-tile-index">{cell.position}</span>
      <span className="sbg-tile-icon">{tileIcon(kind)}</span>
      <span className="sbg-tile-name">{cell.position === 1 ? labels.start : cell.position === boardSize ? labels.finish : cell.name || labels.empty}</span>
      <div className="sbg-pieces">
        {hasPlayer ? <span className="sbg-piece is-player">{shortName(labels.player)}</span> : null}
        {hasAi ? <span className="sbg-piece is-ai">{shortName(labels.ai)}</span> : null}
      </div>
    </div>
  );
}

function StatusCard({
  actor,
  labels,
  statuses,
  passCount,
}: {
  actor: Actor;
  labels: Required<SeseBoardLabels>;
  statuses: StatusItem[];
  passCount: number;
}) {
  return (
    <section className="sbg-status-card">
      <h2>{actorName(actor, labels)}状态</h2>
      <div className="sbg-tags">
        <span className="sbg-tag">
          {labels.passCard} x{passCount}
        </span>
        {statuses.length ? (
          statuses.map((item, index) => (
            <span className="sbg-tag" key={item.id || `${item.slot}-${index}`}>
              {formatStatusItem(item)}
            </span>
          ))
        ) : (
          <span className="sbg-tag">{labels.noStatus}</span>
        )}
      </div>
    </section>
  );
}

function PendingPanel({
  pending,
  labels,
  reviewText,
  rejectText,
  playerPass,
  busy,
  onReviewText,
  onRejectText,
  onRun,
}: {
  pending: PendingEvent;
  labels: Required<SeseBoardLabels>;
  reviewText: string;
  rejectText: string;
  playerPass: number;
  busy: boolean;
  onReviewText: (value: string) => void;
  onRejectText: (value: string) => void;
  onRun: (command: string) => Promise<SeseBoardPayload>;
}) {
  const pendingActor = pending.actor || "player";
  const reviewer = pending.reviewer || "ai";
  const playerCanPass = pending.pass_allowed && pendingActor === "player" && playerPass > 0;

  if (pending.type === "choice") {
    return (
      <section className="sbg-pending">
        <h2>{pending.name || labels.choicePenalty}</h2>
        <p>{pending.prompt || labels.choosePenalty}</p>
        <div className="sbg-choice-list">
          {(pending.choices || []).map((choice) => (
            <button key={choice.id || choice.label} type="button" disabled={busy || pendingActor !== "player"} onClick={() => onRun(`choose ${choice.id || choice.label}`)}>
              {choice.label || choice.id}
            </button>
          ))}
          {playerCanPass ? (
            <button type="button" disabled={busy} onClick={() => onRun("pass")}>
              {labels.usePass}
            </button>
          ) : null}
        </div>
        {pendingActor !== "player" ? (
          <p className="sbg-muted">
            {labels.waitingFor} {actorName(pendingActor, labels)}
          </p>
        ) : null}
      </section>
    );
  }

  return (
    <section className="sbg-pending">
      <h2>{pending.name || labels.reviewTask}</h2>
      <p>{pending.task}</p>
      {pending.phase === "submitted" ? (
        <>
          <blockquote>{pending.submission_text}</blockquote>
          {reviewer === "player" ? (
            <>
              <input value={rejectText} onChange={(event) => onRejectText(event.target.value)} placeholder={labels.rejectReason} />
              <div className="sbg-choice-list">
                <button type="button" disabled={busy} onClick={() => onRun("approve")}>
                  {labels.approve}
                </button>
                <button type="button" disabled={busy} onClick={() => onRun(`reject ${rejectText}`.trim())}>
                  {labels.reject}
                </button>
              </div>
            </>
          ) : (
            <p className="sbg-muted">
              {labels.waitingReview}: {actorName(reviewer, labels)}
            </p>
          )}
        </>
      ) : pendingActor === "player" ? (
        <>
          <textarea value={reviewText} onChange={(event) => onReviewText(event.target.value)} placeholder={pending.submission || labels.submitResponse} />
          <div className="sbg-choice-list">
            <button type="button" disabled={busy || !reviewText.trim()} onClick={() => onRun(`submit ${reviewText}`)}>
              {labels.submit}
            </button>
            {playerCanPass ? (
              <button type="button" disabled={busy} onClick={() => onRun("pass")}>
                {labels.usePass}
              </button>
            ) : null}
          </div>
        </>
      ) : (
        <p className="sbg-muted">
          {labels.waitingSubmission}: {actorName(pendingActor, labels)}
        </p>
      )}
    </section>
  );
}

function formatStatusItem(item: StatusItem) {
  const title = statusTitle(item);
  const value = item.value || "未指定";
  const details: string[] = [];
  if (item.level && item.level > 1) details.push(`${item.level}档`);
  const duration = statusDuration(item);
  if (duration) details.push(duration);
  return `${title}：${value}${details.length ? `（${details.join("，")}）` : ""}`;
}

function statusTitle(item: StatusItem) {
  if (item.slot === "prop") return "道具惩罚";
  if (item.slot === "limit") return "限制";
  if (item.slot === "task") return "任务状态";
  if (item.slot === "pose") return "姿势锁定";
  if (item.slot === "place") return "地点状态";
  return item.label || item.slot || "状态";
}

function statusDuration(item: StatusItem) {
  if (item.duration_type === "actions") return `停步剩余 ${Math.max(0, Number(item.remaining_actions || 0))} 次`;
  if (item.duration_type === "until_clear") return "待解除";
  if (item.duration_type === "until_finish") return "到终点前有效";
  return "";
}

function makeRows(cells: BoardCell[], boardSize: number, columns: number) {
  const source = cells.length
    ? cells
    : Array.from({ length: boardSize }, (_, index) => ({ position: index + 1, kind: "empty", name: "" }));
  const rows: BoardCell[][] = [];
  for (let index = 0; index < source.length; index += columns) {
    const row = source.slice(index, index + columns);
    if (rows.length % 2 === 1) row.reverse();
    rows.push(row);
  }
  return rows.reverse();
}

function clampPosition(value: unknown, boardSize: number) {
  const numeric = Math.floor(Number(value || 0));
  return Math.max(0, Math.min(boardSize, numeric || 0));
}

function pieceOnCell(position: number, cellPosition: number) {
  if (position <= 0) return cellPosition === 1;
  return position === cellPosition;
}

function actorName(actor: Actor | string, labels: Required<SeseBoardLabels>) {
  return actor === "ai" ? labels.ai : labels.player;
}

function leadLabel(state: SeseBoardState | undefined, labels: Required<SeseBoardLabels>) {
  const lead = state?.theme_profile?.lead || state?.theme_profile?.direction;
  if (!lead) return labels.noLead;
  return actorName(String(lead), labels);
}

function shortName(name: string) {
  return name.trim().slice(0, 2).toUpperCase();
}

function tileIcon(kind: string) {
  if (kind === "start") return "S";
  if (kind === "finish") return "F";
  if (kind === "reward" || kind === "clear_reward") return "+";
  if (kind === "penalty_choice" || kind === "penalty_review") return "!";
  if (kind === "move" || kind === "move_reward") return "<";
  if (kind === "swap_positions") return "=";
  if (kind === "clear_status") return "*";
  if (kind === "extend_status") return "^";
  if (kind === "block") return "X";
  if (kind === "add_status" || kind === "replace_status") return "#";
  return "";
}

function recentLine(text: string | undefined, fallback: string) {
  const line = String(text || "")
    .split(/\r?\n/)
    .map((item) => item.trim())
    .find((item) => item && !item.startsWith("Progress:") && !item.startsWith("进度："));
  return line || fallback;
}

function appendMessage(setter: React.Dispatch<React.SetStateAction<ChatMessage[]>>, speaker: ChatMessage["speaker"], text: string) {
  setter((items) => [
    ...items,
    {
      id: `${speaker}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      speaker,
      text,
    },
  ]);
}

function BackIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M15 18 9 12l6-6" />
    </svg>
  );
}

function ChatIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M21 12a8 8 0 0 1-8 8H7l-4 3 1.4-5.2A8 8 0 1 1 21 12Z" />
      <path d="M8 11h8M8 15h5" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m4 11 16-7-7 16-2-7-7-2Z" />
      <path d="m11 13 9-9" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

function ensureStyles() {
  if (typeof document === "undefined" || document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
.sbg-root{min-height:100%;background:#f9e7ee;color:#4a3140;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.sbg-header{background:#eca9c2;padding:calc(18px + env(safe-area-inset-top,0px)) 18px 22px}
.sbg-header-actions{display:grid;grid-template-columns:44px 1fr 44px;align-items:center;gap:10px}
.sbg-header h1{margin:0;text-align:center;color:#fff;font-size:28px;line-height:1.1;font-weight:800;letter-spacing:0}
.sbg-icon-button{width:42px;height:42px;border:0;border-radius:999px;background:rgba(255,255,255,.32);color:#fff;display:grid;place-items:center;cursor:pointer}
.sbg-icon-button svg{width:24px;height:24px;fill:none;stroke:currentColor;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
.sbg-icon-button:disabled{opacity:.45;cursor:not-allowed}
.sbg-icon-button.is-solid{background:#c34d7b}
.sbg-score{margin-top:18px;border-radius:24px;background:rgba(255,255,255,.82);padding:18px;display:grid;grid-template-columns:1fr 1fr;gap:12px}
.sbg-info span{display:block;color:#aa61a9;font-weight:700;font-size:13px}
.sbg-info strong{display:block;color:#7e4678;font-size:20px;line-height:1.2;word-break:break-word}
.sbg-turn{grid-column:1/-1;border-radius:999px;background:#fff8b8;color:#8a4a8b;text-align:center;font-size:18px;font-weight:800;padding:12px 16px}
.sbg-main{padding:18px;max-width:900px;margin:0 auto}
.sbg-board{background:rgba(255,255,255,.82);border-radius:26px;padding:10px;display:grid;gap:8px;box-shadow:0 16px 40px rgba(144,70,101,.13)}
.sbg-row{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px}
.sbg-tile{position:relative;aspect-ratio:1/1;border-radius:14px;background:#f1e4f1;box-shadow:inset 0 0 0 1px rgba(125,83,132,.06),0 4px 12px rgba(75,38,66,.08);padding:7px;display:grid;grid-template-rows:auto 1fr auto;color:#7d4f82;overflow:hidden}
.sbg-tile.kind-start{background:#fff1a9}.sbg-tile.kind-finish{background:#bfe8e0}.sbg-tile.kind-penalty_choice,.sbg-tile.kind-penalty_review{background:#f4b5ce}.sbg-tile.kind-add_status,.sbg-tile.kind-replace_status{background:#d9f1f7}.sbg-tile.kind-block{background:#e6d8f5}
.sbg-tile-index{font-size:13px;color:#b487b9;font-weight:800}
.sbg-tile-icon{font-size:18px;font-weight:900;text-align:center;align-self:end}
.sbg-tile-name{font-size:12px;text-align:center;font-weight:700;line-height:1.2;min-height:28px;display:grid;place-items:center;word-break:break-word}
.sbg-pieces{position:absolute;left:7px;right:7px;bottom:6px;display:flex;gap:4px;justify-content:center;pointer-events:none}
.sbg-piece{width:30px;height:30px;border-radius:999px;display:grid;place-items:center;color:white;font-size:11px;font-weight:900;border:3px solid white;box-shadow:0 5px 12px rgba(0,0,0,.18)}
.sbg-piece.is-player{background:#de4f85}.sbg-piece.is-ai{background:#7859c9}
.sbg-status-grid{margin-top:18px;display:grid;grid-template-columns:1fr 1fr;gap:14px}
.sbg-status-card,.sbg-pending{background:rgba(255,255,255,.9);border-radius:20px;padding:16px;box-shadow:0 10px 24px rgba(144,70,101,.1)}
.sbg-status-card h2,.sbg-pending h2{margin:0 0 12px;color:#7c3e76;font-size:18px;line-height:1.2}
.sbg-tags{display:flex;flex-wrap:wrap;gap:8px}
.sbg-tag{border-radius:8px;background:#f0e0ee;border:1px solid #dfc8dd;padding:7px 10px;color:#805086;font-size:13px;font-weight:700;line-height:1.2}
.sbg-pending{margin-top:18px;border:2px solid #efa4c1}
.sbg-pending p{margin:0 0 12px;line-height:1.5}
.sbg-pending blockquote{margin:0 0 12px;border-left:4px solid #d0618e;padding:8px 12px;background:#fff5f8;border-radius:8px}
.sbg-pending textarea,.sbg-pending input,.sbg-chat-input input{width:100%;box-sizing:border-box;border:1px solid #e1c6db;border-radius:12px;background:#fff;padding:12px 14px;color:#4a3140;font:inherit;outline:none}
.sbg-pending textarea{min-height:92px;resize:vertical}
.sbg-choice-list{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}
.sbg-choice-list button,.sbg-primary,.sbg-secondary{border:0;border-radius:999px;padding:12px 18px;font:inherit;font-weight:900;cursor:pointer;min-height:44px}
.sbg-choice-list button,.sbg-primary{background:#eaa5bd;color:#fff;box-shadow:0 5px 0 #bd3367}
.sbg-secondary{background:#fff;color:#854b7f;border:1px solid #e1c6db}
.sbg-choice-list button:disabled,.sbg-primary:disabled,.sbg-secondary:disabled{opacity:.45;cursor:not-allowed;box-shadow:none}
.sbg-muted,.sbg-empty,.sbg-recent{color:#9b7598}
.sbg-result{margin-top:18px;border-radius:16px;background:#fff8b8;color:#7c3e76;padding:14px;font-weight:900;text-align:center}
.sbg-controls{margin-top:18px;border-radius:26px;background:rgba(255,255,255,.78);padding:14px;display:grid;grid-template-columns:72px 1fr auto auto;gap:12px;align-items:center}
.sbg-dice{width:64px;height:64px;border-radius:18px;background:#fff;color:#7f467a;display:grid;place-items:center;font-size:34px;font-weight:900;box-shadow:0 8px 20px rgba(60,35,62,.16)}
.sbg-dice.is-rolling{animation:sbg-shake .36s linear infinite}
.sbg-primary{font-size:22px;min-height:62px}
.sbg-recent{text-align:center;margin:16px 0 0;font-size:14px}
.sbg-modal{position:fixed;inset:0;background:rgba(43,23,40,.28);display:grid;place-items:center;padding:20px;z-index:40}
.sbg-chat{width:min(520px,100%);max-height:min(720px,88vh);background:#fff;border-radius:22px;display:grid;grid-template-rows:auto 1fr auto;overflow:hidden;box-shadow:0 24px 70px rgba(45,24,39,.35)}
.sbg-chat-head{padding:14px 16px;background:#eca9c2;color:#fff;display:flex;align-items:center;justify-content:space-between}
.sbg-chat-body{padding:16px;overflow:auto;display:grid;gap:12px;align-content:start}
.sbg-message span{display:block;color:#9b7598;font-size:12px;font-weight:800;margin-bottom:4px}
.sbg-message p{margin:0;border-radius:14px;padding:10px 12px;background:#f7edf4;white-space:pre-wrap;line-height:1.45}
.sbg-message.is-player p{background:#f9d8e5}.sbg-message.is-ai p{background:#e8e0fb}.sbg-message.is-system p{background:#f0edf1}
.sbg-chat-input{display:grid;grid-template-columns:1fr 46px;gap:10px;padding:14px;border-top:1px solid #f0d9e4}
@keyframes sbg-shake{0%{transform:rotate(0)}25%{transform:rotate(8deg) scale(1.03)}50%{transform:rotate(-8deg) scale(.98)}100%{transform:rotate(0)}}
@media (max-width:640px){.sbg-header{padding-left:12px;padding-right:12px}.sbg-header h1{font-size:24px}.sbg-main{padding:12px}.sbg-board{gap:6px;padding:8px}.sbg-row{gap:6px}.sbg-tile{border-radius:10px;padding:5px}.sbg-tile-name{font-size:10px;min-height:24px}.sbg-tile-icon{font-size:15px}.sbg-piece{width:24px;height:24px;font-size:9px}.sbg-status-grid{grid-template-columns:1fr}.sbg-controls{grid-template-columns:64px 1fr;}.sbg-secondary{grid-column:1/-1}.sbg-primary{font-size:19px}}
`;
  document.head.appendChild(style);
}
