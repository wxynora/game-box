import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";


function ChevronLeftIcon() {
  return <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6" /></svg>;
}

function MessageCircleIconMini({ className = "h-[19px] w-[19px] stroke-[2]" }: { className?: string } = {}) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z" /></svg>;
}

function SendIconMini() {
  return <svg className="h-[17px] w-[17px] stroke-[1.8]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 2 11 13" /><path d="m22 2-7 20-4-9-9-4 20-7Z" /></svg>;
}

export type Actor = "player" | "ai";

export type CellEvent = {
  position?: number;
  kind?: string;
  slot?: string;
  name?: string;
  effect?: string;
};

export type StatusItem = {
  slot?: string;
  label?: string;
  value?: string;
  duration_type?: string;
  remaining_actions?: number;
  minutes?: number;
  expires_at?: string;
  blocks_action?: boolean;
  level?: number;
};

type StatusDisplayGroup = {
  label: string;
  values: string[];
};

type RewardHand = Partial<Record<"pass", number>>;

export type PendingChoice = {
  id?: string;
  label?: string;
  effect?: Record<string, unknown>;
};

export type PendingEvent = {
  id?: string;
  type?: "review" | "choice" | "duel" | string;
  card_id?: string;
  name?: string;
  actor?: Actor;
  reviewer?: Actor;
  opponent?: Actor;
  current_actor?: Actor;
  phase?: "assigned" | "questioning" | "submitted" | string;
  task?: string;
  prompt?: string;
  submission?: string;
  submission_text?: string;
  question_prompt?: string;
  question_text?: string;
  waiting_task?: string;
  pass_result?: string;
  reject_prompt?: string;
  last_reject_reason?: string;
  pass_allowed?: boolean;
  cell?: number;
  theme?: string;
  reject_count?: number;
  choices?: PendingChoice[];
  picks?: Partial<Record<Actor, string>>;
};

export type FinalNote = {
  id?: string;
  winner?: Actor;
  target?: Actor;
  theme?: string;
  text?: string;
  ai_text?: string;
  target_status?: string;
  final_note_items?: string;
  final_place?: string;
  final_pose?: string;
  sent?: boolean;
  sent_at?: string;
};

export type SeseBoardState = {
  board_size?: number;
  positions?: Partial<Record<Actor, number>>;
  turn_actor?: Actor;
  statuses?: Partial<Record<Actor, StatusItem[]>>;
  final_note_items?: StatusItem[];
  hands?: Partial<Record<Actor, RewardHand>>;
  pass_skips_used?: number;
  pending_event?: PendingEvent | null;
  final_note?: FinalNote | null;
  theme_profile?: {
    theme?: string;
    direction?: string;
    direction_label?: string;
  };
  theme_options?: string[];
  cell_events?: CellEvent[];
  game_over?: boolean;
  winner?: Actor | "";
  result?: string;
  updated_at?: string;
};

export type SeseBoardPayload = {
  ok?: boolean;
  text?: string;
  ai_text?: string;
  player_text?: string;
  state?: SeseBoardState;
  game_over?: boolean;
  winner?: Actor | "";
  result?: string;
  error?: string;
};

type SeseBoardSyncPayload = {
  ok?: boolean;
  player_text?: string;
  state?: SeseBoardState;
  reply_text?: string;
  reply_preview?: string;
  applied_reply_commands?: Array<{ command?: string; ok?: boolean; error?: string }>;
  followup_wakeups?: Array<{ ok?: boolean; reply_preview?: string; error?: string }>;
  channel?: string;
  wakeup?: {
    error?: string;
    reply_text?: string;
    reply_preview?: string;
    channel?: string;
  };
  error?: string;
};

type SeseBoardSyncMode = "roll_result" | "state_update" | "chat" | "final_note";
type AssistantResponse = string | SeseBoardSyncPayload;
type FinalAppendSlot = "prop";

type MoveInfo = {
  actor: Actor;
  dice: number;
  from: number;
  to: number;
};

type EventPopup = {
  position: number;
  kicker?: string;
  actor?: Actor;
  actorLabel?: string;
  from?: number;
  to?: number;
  title: string;
  text: string;
  detail: string;
  kind: "event" | "draw";
  cardTitle?: string;
  cardType?: string;
  tone?: "reward" | "penalty" | "choice";
};

type ThemeDraw = {
  theme: string;
  direction: string;
  items: string[];
  spinKey: string;
};

type GameChatMessage = {
  id: string;
  speaker: Actor | "system";
  text: string;
};

const GAME_CHAT_STORAGE_KEY = "sese-board-game:chat:v1";
const GAME_CHAT_SPEAKERS = new Set<string>(["player", "ai", "system"]);
const DEFAULT_GAME_CHAT_MESSAGES: GameChatMessage[] = [
  {
    id: "system-ready",
    speaker: "system",
    text: "游戏内交流在这里。对方明确发送【掷骰】时，棋盘才会执行他的行动。",
  },
];

function defaultGameChatMessages(): GameChatMessage[] {
  return DEFAULT_GAME_CHAT_MESSAGES.map((message) => ({ ...message }));
}

function readStoredGameChatMessages(): GameChatMessage[] {
  if (typeof window === "undefined") return defaultGameChatMessages();
  try {
    const raw = window.localStorage.getItem(GAME_CHAT_STORAGE_KEY);
    if (!raw) return defaultGameChatMessages();
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return defaultGameChatMessages();
    const messages = parsed.flatMap((entry, index): GameChatMessage[] => {
      if (!entry || typeof entry !== "object") return [];
      const item = entry as Partial<Record<keyof GameChatMessage, unknown>>;
      const speaker = typeof item.speaker === "string" ? item.speaker : "";
      const text = typeof item.text === "string" ? item.text.trim() : "";
      if (!GAME_CHAT_SPEAKERS.has(speaker) || !text) return [];
      const rawId = typeof item.id === "string" ? item.id.trim() : "";
      return [{ id: rawId || `stored-${index}`, speaker: speaker as GameChatMessage["speaker"], text }];
    });
    return messages.length ? messages : defaultGameChatMessages();
  } catch {
    return defaultGameChatMessages();
  }
}

function writeStoredGameChatMessages(messages: GameChatMessage[]) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(GAME_CHAT_STORAGE_KEY, JSON.stringify(messages));
  } catch {
    // Ignore private-mode or quota failures; chat still works for the current view.
  }
}

const ACTORS: Actor[] = ["player", "ai"];
const ACTOR_LABEL: Record<Actor, string> = { player: "你", ai: "对方" };
const DEFAULT_POSITIONS: Record<Actor, number> = { player: 0, ai: 0 };
const RPS_UI_CHOICES = [
  { id: "scissors", label: "剪刀", icon: "✌️" },
  { id: "rock", label: "石头", icon: "👊" },
  { id: "paper", label: "布", icon: "✋" },
];
const RPS_BEATS: Record<string, string> = {
  rock: "scissors",
  scissors: "paper",
  paper: "rock",
};
const RPS_CHOICE_ALIASES: Record<string, string> = {
  scissors: "scissors",
  剪刀: "scissors",
  "✌️": "scissors",
  "✌": "scissors",
  rock: "rock",
  stone: "rock",
  石头: "rock",
  拳头: "rock",
  "👊": "rock",
  paper: "paper",
  布: "paper",
  包袱: "paper",
  "✋": "paper",
};

function normalizeRpsChoice(value: unknown): string {
  const raw = String(value || "").trim();
  if (!raw) return "";
  return RPS_CHOICE_ALIASES[raw] || raw;
}

function rpsChoiceLabel(value: unknown): string {
  const normalized = normalizeRpsChoice(value);
  return RPS_UI_CHOICES.find((choice) => choice.id === normalized)?.label || String(value || "").trim() || "未出拳";
}

function duelResultText(pending: PendingEvent | null | undefined, assistantChoice: string): string {
  const playerPick = normalizeRpsChoice(pending?.picks?.player);
  const assistantPick = normalizeRpsChoice(assistantChoice);
  if (!playerPick || !assistantPick) return "";
  const playerLabel = rpsChoiceLabel(playerPick);
  const assistantLabel = rpsChoiceLabel(assistantPick);
  if (playerPick === assistantPick) {
    return `你出了${playerLabel}，对方出了${assistantLabel}。平局，重新出拳。`;
  }
  const winner = RPS_BEATS[playerPick] === assistantPick ? "你赢" : "对方赢";
  return `你出了${playerLabel}，对方出了${assistantLabel}。${winner}。`;
}
const FINAL_MATERIAL_LABELS: Partial<Record<string, string>> = {
  place: "最终地点",
  pose: "最终姿势",
};
const FINAL_TOY_PROP_OPTIONS = ["跳蛋", "震动乳夹", "震动环", "乳夹", "锁精环", "飞机杯", "软绳", "手腕绑带", "眼罩", "口球", "春药"];
const LEVELABLE_PROP_PATTERNS = ["跳蛋", "震动", "按摩棒", "飞机杯", "吸乳器", "吸吮器"];
function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function displayText(value: unknown): string {
  return String(value || "");
}

function displaySystemText(value: unknown): string {
  return String(value || "")
    .replace(/你/g, "你")
    .replace(/(^|[^自])我/g, "$1你");
}

function plainText(value: unknown): string {
  return String(value || "");
}

function payloadFailureText(payload: SeseBoardPayload, fallback: string): string {
  const source = displayText(payload.player_text || payload.text || payload.error || "");
  const line = source
    .split(/\r?\n/)
    .map((item) => item.trim())
    .find((item) => item && !item.startsWith("【") && !/^(进度|主题|轮到|手牌|你的状态|对方状态|最终地点|最终姿势|待处理|可用命令)/.test(item));
  return line || fallback;
}

function makeChatId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function clampPosition(value: unknown, boardSize: number): number {
  const n = Math.floor(Number(value || 0));
  return Math.max(1, Math.min(boardSize, n || 1));
}

function progressPosition(value: unknown, boardSize: number): number {
  const n = Math.floor(Number(value || 0));
  return Math.max(0, Math.min(boardSize, n || 0));
}

function snakeOrder(boardSize: number, columns: number): number[] {
  const rows: number[][] = [];
  for (let start = 1; start <= boardSize; start += columns) {
    const row = Array.from({ length: Math.min(columns, boardSize - start + 1) }, (_, idx) => start + idx);
    if (rows.length % 2 === 1) row.reverse();
    rows.push(row);
  }
  return rows.reverse().flat();
}

function eventKind(event: CellEvent | undefined, position: number, boardSize: number): string {
  if (position === 1) return "start";
  if (position === boardSize) return "end";
  if (!event) return "empty";
  const raw = `${event.kind || ""} ${event.slot || ""}`.toLowerCase();
  if (/empty/.test(raw)) return "empty";
  if (/finish_self|finish-jump/.test(raw)) return "finish-jump";
  if (/reset/.test(raw)) return "reset";
  if (/swap/.test(raw)) return "swap";
  if (/move|back|forward/.test(raw)) return "move";
  if (/lock|pause|item/.test(raw)) return "item";
  if (/clear/.test(raw)) return "clear";
  if (/extend|time/.test(raw)) return "time";
  if (/limit/.test(raw)) return "limit";
  if (/place/.test(raw)) return "place";
  if (/pose/.test(raw)) return "pose";
  if (/theme/.test(raw)) return "theme";
  return "task";
}

function eventIcon(kind: string): string {
  if (kind === "start") return "🚩";
  if (kind === "end") return "🏆";
  if (kind === "place") return "🏫";
  if (kind === "item") return "🎁";
  if (kind === "move") return "⏪";
  if (kind === "reset") return "🔁";
  if (kind === "finish-jump") return "🏁";
  if (kind === "swap") return "🔄";
  if (kind === "clear") return "✨";
  if (kind === "time") return "⏳";
  if (kind === "limit") return "🚫";
  if (kind === "pose") return "◇";
  if (kind === "theme") return "🚩";
  if (kind === "task") return "📸";
  return "";
}

function tileName(event: CellEvent | undefined, position: number, boardSize: number): string {
  if (position === 1) return "起点";
  if (position === boardSize) return "终点";
  return displayText(event?.name || "空");
}

function parseMove(text: string): MoveInfo | null {
  const match = displayText(text).match(/(你|对方)掷出\s*(\d+)，从\s*(\d+)\s*走到\s*(\d+)/);
  if (!match) return null;
  return {
    actor: match[1] === "对方" ? "ai" : "player",
    dice: Number(match[2] || 1),
    from: Number(match[3] || 0),
    to: Number(match[4] || 0),
  };
}

function stripTrailingPunctuation(value: string): string {
  return value.replace(/[。.!！?？\s]+$/g, "").trim();
}

function eventEffectDetail(rawDetail: string, followingLines: string[], fallbackActorLabel: string, title: string): string {
  const candidates = [rawDetail, ...followingLines]
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item) => !/^下一次行动[:：]/.test(item) && !/^待处理[:：]/.test(item));
  const combined = candidates.join(" ");
  if (/双方回到起点/.test(combined)) return "双方回到起点";
  let match = combined.match(/(你|对方|双方)?\s*从\s*\d+\s*(前进|后退)\s*(\d+)\s*格(?:到|至)\s*\d+/);
  if (match) {
    const actor = match[1] || fallbackActorLabel || "玩家";
    return `${actor}${match[2]}了 ${match[3]} 格`;
  }
  match = combined.match(/(你|对方|双方)\s*(前进|后退)\s*(\d+)\s*格/);
  if (match) return `${match[1]}${match[2]}了 ${match[3]} 格`;
  match = combined.match(/(你|对方)\s*从\s*\d+\s*回到起点/);
  if (match) return `${match[1]}回到起点`;
  match = combined.match(/(你|对方)\s*从\s*\d+\s*直达终点/);
  if (match) return `${match[1]}直达终点`;
  if (stripTrailingPunctuation(rawDetail) === stripTrailingPunctuation(title)) return "";
  return rawDetail ? `触发：${rawDetail}` : "";
}

function parseEventPopup(text: string, move?: MoveInfo | null): EventPopup | null {
  const lines = displayText(text)
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
  const eventIndex = lines.findIndex((item) => /^第\s*\d+\s*格：/.test(item));
  const line = eventIndex >= 0 ? lines[eventIndex] : "";
  if (!line) return null;
  const match = line.match(/^第\s*(\d+)\s*格：([^，。]+)/);
  const title = match?.[2] || "格子事件";
  const drawnCard = line.match(/抽到「([^」]+)」/)?.[1] || "";
  const rewardCard = line.match(/获得\s*([^（，。]+)/)?.[1] || "";
  const isDraw = Boolean(drawnCard || rewardCard || /抽卡|惩罚任务|选择惩罚/.test(title));
  const tone: EventPopup["tone"] = /奖励|Pass卡|获得/.test(line) ? "reward" : /选择/.test(title) ? "choice" : "penalty";
  const position = Number(match?.[1] || 0);
  const actor = move?.actor;
  const rawDetail = line.replace(/^第\s*\d+\s*格：/, "").trim();
  const actorLabel = actor ? ACTOR_LABEL[actor] : "";
  const detail = eventEffectDetail(rawDetail, lines.slice(eventIndex + 1, eventIndex + 4), actorLabel, title);
  return {
    position,
    actor,
    actorLabel,
    from: move?.from,
    to: move?.to ?? position,
    title,
    text: line,
    detail,
    kind: isDraw ? "draw" : "event",
    cardTitle: drawnCard || rewardCard || title,
    cardType: tone === "reward" ? "奖励卡" : tone === "choice" ? "选择惩罚" : "惩罚任务",
    tone,
  };
}

function popupCardTypeText(popup: EventPopup): string {
  const type = displaySystemText(popup.cardType || "").trim();
  const title = displaySystemText(popup.cardTitle || popup.title).trim();
  const eventTitle = displaySystemText(popup.title).trim();
  if (!type || type === title || type === eventTitle) return "";
  return type;
}

function popupDetailText(popup: EventPopup): string {
  const detail = displaySystemText(popup.detail || "").trim();
  const title = displaySystemText(popup.title).trim();
  if (!detail) return "";
  if (stripTrailingPunctuation(detail.replace(/^触发[:：]\s*/, "")) === stripTrailingPunctuation(title)) return "";
  return detail;
}

function buildThemeDraw(theme: unknown, direction: unknown, options: unknown): ThemeDraw | null {
  const themeText = displayText(theme).trim();
  if (!themeText) return null;
  const source = Array.isArray(options) ? options.map((item) => displayText(item).trim()).filter(Boolean) : [];
  const unique = Array.from(new Set(source));
  const pool = unique.filter((item) => item !== themeText);
  const shuffled = [...pool].sort(() => Math.random() - 0.5);
  const items = [...shuffled.slice(0, 7), themeText];
  while (items.length < 8) items.unshift(themeText);
  return {
    theme: themeText,
    direction: displayText(direction || "待定"),
    items,
    spinKey: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  };
}

function statusDuration(item: StatusItem): string {
  const duration = String(item.duration_type || "");
  if (duration === "actions") {
    const count = Math.max(0, Number(item.remaining_actions || 0));
    return item.blocks_action ? `停步剩余 ${count} 次` : `剩余 ${count} 次行动`;
  }
  if (duration === "minutes") return `${Math.max(1, Number(item.minutes || 0))} 分钟`;
  if (duration === "until_finish") return "到终点前有效";
  if (duration === "until_clear") return "待解除";
  if (duration === "final_note") return "";
  return "";
}

function isFinalMaterialSlot(slot: unknown): boolean {
  return Boolean(FINAL_MATERIAL_LABELS[String(slot || "").trim()]);
}

function finalMaterialItemsFrom(items: StatusItem[] | undefined, note?: FinalNote | null): StatusDisplayGroup[] {
  const latest = new Map<string, string>();
  for (const item of items || []) {
    const slot = String(item?.slot || "").trim();
    if (!isFinalMaterialSlot(slot)) continue;
    const value = displayText(item?.value || "").trim();
    if (value) latest.set(slot, value);
  }
  const finalPlace = displayText(note?.final_place || "").trim();
  const finalPose = displayText(note?.final_pose || "").trim();
  if (finalPlace && !latest.has("place")) latest.set("place", finalPlace);
  if (finalPose && !latest.has("pose")) latest.set("pose", finalPose);
  return ["place", "pose"]
    .map((slot) => {
      const value = latest.get(slot);
      return value ? { label: FINAL_MATERIAL_LABELS[slot] || "终局素材", values: [value] } : null;
    })
    .filter((item): item is StatusDisplayGroup => Boolean(item));
}

function statusLabel(item: StatusItem): string {
  const label = displayText(item.label || item.slot || "状态");
  if (item.slot === "prop" || label === "道具") return "道具惩罚";
  return label;
}

function statusValueText(item: StatusItem): string {
  const value = displayText(item.value || "");
  const detailParts: string[] = [];
  const level = Math.max(1, Number(item.level || 1));
  if (item.slot === "prop" && level > 1 && isLevelableProp(value)) detailParts.push(`${level}档`);
  const duration = statusDuration(item);
  if (duration) detailParts.push(duration);
  if (!value) return detailParts.length ? detailParts.join("，") : "状态";
  return detailParts.length ? `${value}（${detailParts.join("，")}）` : value;
}

function isLevelableProp(value: string): boolean {
  return LEVELABLE_PROP_PATTERNS.some((pattern) => value.includes(pattern));
}

function groupStatusItems(statuses: StatusItem[]): StatusDisplayGroup[] {
  const groups = new Map<string, string[]>();
  statuses.filter((item) => !isFinalMaterialSlot(item.slot)).slice(-6).forEach((item) => {
    const label = statusLabel(item);
    const values = groups.get(label) || [];
    values.push(statusValueText(item));
    groups.set(label, values);
  });
  return Array.from(groups.entries()).map(([label, values]) => ({ label, values }));
}

function actorPaused(statuses: StatusItem[] | undefined): boolean {
  return (statuses || []).some((item) => item.blocks_action && Number(item.remaining_actions || 0) > 0);
}

function recentLines(text: string): string[] {
  const allowed = [
    /^(你|对方)掷出\s*\d+/,
    /^第\s*\d+\s*格：/,
    /^下一次行动：/,
    /行动权/,
    /到达终点/,
    /^新局已开始。?$/,
    /^本局已结束。?$/,
  ];
  return displayText(text)
    .split("\n")
    .map((item) => item.trim())
    .filter((item) => item && allowed.some((pattern) => pattern.test(item)))
    .slice(0, 4);
}

function assistantWantsRoll(text: string): boolean {
  const firstLine = String(text || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find(Boolean);
  return firstLine === "【掷骰】";
}

function assistantIncludesRollDirective(text: string): boolean {
  return String(text || "")
    .split(/\r?\n/)
    .some((line) => line.trim() === "【掷骰】");
}

type AssistantDirective =
  | { kind: "roll"; body: string }
  | { kind: "submit"; body: string }
  | { kind: "approve"; body: string }
  | { kind: "reject"; body: string }
  | { kind: "choose"; choice: string; body: string }
  | { kind: "pass"; body: string }
  | { kind: ""; body: string };

type ReviewFeedback = {
  outcome: "approved" | "rejected";
  title: string;
  text: string;
  note: string;
};

function directiveBody(lines: string[], startIndex: number): string {
  return lines
    .slice(startIndex)
    .map((line) => {
      const trimmed = line.trim();
      if (trimmed === "【掷骰】") return "";
      const description = trimmed.match(/^【描述[:：](.*)】$/);
      return description ? description[1].trim() : trimmed;
    })
    .filter(Boolean)
    .join("\n")
    .trim();
}

function multilineColonDirectiveBody(lines: string[], firstIndex: number, pattern: RegExp): string | null {
  const first = lines[firstIndex]?.trim() || "";
  const match = first.match(pattern);
  if (!match) return null;
  const firstBody = match[1] || "";
  const inlineClose = firstBody.indexOf("】");
  if (inlineClose >= 0) return firstBody.slice(0, inlineClose).trim();
  const text = [firstBody, ...lines.slice(firstIndex + 1)]
    .join("\n")
    .trim();
  return text.endsWith("】") ? text.slice(0, -1).trim() : text;
}

function parseAssistantDirective(text: string): AssistantDirective {
  const lines = String(text || "").split(/\r?\n/);
  const firstIndex = lines.findIndex((line) => line.trim());
  if (firstIndex < 0) return { kind: "", body: "" };
  const first = lines[firstIndex].trim();
  const body = directiveBody(lines, firstIndex + 1);
  const descriptionText = multilineColonDirectiveBody(lines, firstIndex, /^【描述[:：](.*)$/);
  if (descriptionText !== null) return { kind: "submit", body: descriptionText || body };
  const truthQuestionText = multilineColonDirectiveBody(lines, firstIndex, /^【真心话出题[:：](.*)$/);
  if (truthQuestionText !== null) return { kind: "submit", body: truthQuestionText || body };
  const truthAnswerText = multilineColonDirectiveBody(lines, firstIndex, /^【真心话回答[:：](.*)$/);
  if (truthAnswerText !== null) return { kind: "submit", body: truthAnswerText || body };
  if (first === "【掷骰】") return { kind: "roll", body };
  if (first === "【提交】") return { kind: "submit", body };
  const approveMatch = first.match(/^【通过[:：](.*?)(?:】)?$/);
  if (approveMatch) return { kind: "approve", body: approveMatch[1].trim() || body };
  const rejectMatch = first.match(/^【(?:不通过|打回|驳回)[:：](.*?)(?:】)?$/);
  if (rejectMatch) return { kind: "reject", body: rejectMatch[1].trim() || body };
  if (first === "【通过】") return { kind: "approve", body };
  if (first === "【不通过】" || first === "【打回】" || first === "【驳回】") return { kind: "reject", body };
  if (first === "【Pass】" || first === "【PASS】" || first === "【使用Pass卡】") return { kind: "pass", body };
  const choiceMatch = first.match(/^【选择[:：](.+)】$/);
  if (choiceMatch) return { kind: "choose", choice: choiceMatch[1].trim(), body };
  const duelMatch = first.match(/^【(?:剪刀石头布|石头剪刀布)[:：](.+)】$/);
  if (duelMatch) return { kind: "choose", choice: duelMatch[1].trim(), body };
  return { kind: "", body: directiveBody(lines, firstIndex) };
}


export type AssistantTurnParse = { command: string | null; chatText: string };

export function parseAssistantTurn(text: string): AssistantTurnParse {
  const directive = parseAssistantDirective(text);
  if (directive.kind === "roll") return { command: "roll", chatText: directive.body };
  if (directive.kind === "submit") return { command: directive.body ? `submit ${directive.body}` : null, chatText: directive.body };
  if (directive.kind === "approve") return { command: directive.body ? `approve ${directive.body}` : "approve", chatText: directive.body };
  if (directive.kind === "reject") return { command: directive.body ? `reject ${directive.body}` : "reject", chatText: directive.body };
  if (directive.kind === "choose") return { command: directive.choice ? `choose ${directive.choice}` : null, chatText: directive.body };
  if (directive.kind === "pass") return { command: "pass", chatText: directive.body };
  return { command: null, chatText: directive.body };
}

export function parseAssistantCommand(text: string): string | null {
  return parseAssistantTurn(text).command;
}

function firstPendingChoice(pending: PendingEvent | null | undefined, fallback = "rock"): string {
  const first = (pending?.choices || []).find((choice) => choice?.id || choice?.label);
  return String(first?.id || first?.label || fallback).trim();
}

const LONG_DESCRIPTION_REVIEW_TASKS = new Set(["反向诱惑", "全部暴露！", "羞耻台词大放送", "自慰陈述"]);

function localAssistantReplyForState(mode: SeseBoardSyncMode, state: SeseBoardState | undefined): string {
  if (mode === "final_note") {
    return "本地预览：终局小纸条收到了。";
  }
  const pending = state?.pending_event || null;
  if (pending?.type === "duel" && pending.current_actor === "ai") {
    return "【剪刀石头布：石头】";
  }
  if (pending?.type === "choice" && pending.actor === "ai") {
    const choice = firstPendingChoice(pending, "");
    if (choice) return `【选择：${choice}】`;
  }
  if (pending?.type === "review" && pending.reviewer === "ai" && pending.phase === "questioning") {
    return "【真心话出题：本地预览：对方想问你的真心话问题。】";
  }
  if (pending?.type === "review" && pending.actor === "ai" && pending.phase === "assigned") {
    if (pending.name === "真心话点名") {
      return "【真心话回答：本地预览：对方已经回答真心话。】";
    }
    if (LONG_DESCRIPTION_REVIEW_TASKS.has(String(pending.name || ""))) {
      return "【描述：本地预览：对方已经完成任务，提交给你验收。】";
    }
    return "【提交】\n本地预览：对方已经完成任务，提交给你验收。";
  }
  if (pending?.type === "review" && pending.reviewer === "ai" && pending.phase === "submitted") {
    return "【通过：本地预览：验收通过。】\n【掷骰】";
  }
  if (isAssistantTurnState(state)) {
    return "【掷骰】";
  }
  return "本地预览：我看到了，等你继续行动。";
}

function isAssistantTurnState(state: SeseBoardState | undefined): boolean {
  return Boolean(state && state.turn_actor === "ai" && !state.game_over);
}

function isAssistantPendingState(state: SeseBoardState | undefined): boolean {
  const pending = state?.pending_event || null;
  if (!state || state.game_over || !pending) return false;
  if (pending.type === "duel") return pending.current_actor === "ai";
  if (pending.type === "choice") return pending.actor === "ai";
  if (pending.type === "review") {
    const phase = String(pending.phase || "");
    if (phase === "questioning" || phase === "submitted") return pending.reviewer === "ai";
    return pending.actor === "ai";
  }
  return false;
}

function hasAppliedAssistantCommands(payload: SeseBoardSyncPayload | undefined): boolean {
  return Array.isArray(payload?.applied_reply_commands) && payload.applied_reply_commands.length > 0;
}

function shouldContinueAfterAppliedAssistantCommands(payload: SeseBoardSyncPayload | undefined): boolean {
  if (!hasAppliedAssistantCommands(payload)) return false;
  if (Array.isArray(payload?.followup_wakeups) && payload.followup_wakeups.length > 0) return false;
  const nextState = payload?.state;
  return isAssistantTurnState(nextState) && (!nextState?.pending_event || isAssistantPendingState(nextState));
}

function assistantFollowupMessage(state: SeseBoardState | undefined): string {
  const pending = state?.pending_event || null;
  if (!pending) return "现在轮到对方行动。";
  if (pending.type === "duel") return "现在轮到对方完成剪刀石头布对抗。";
  if (pending.type === "choice") return "对方刚触发了需要自己选择的惩罚。";
  if (pending.type === "review") {
    const phase = String(pending.phase || "");
    if (phase === "questioning") return "现在需要对方给出真心话题目。";
    if (phase === "submitted") return "现在需要对方验收你提交的惩罚任务。";
    return "现在需要对方提交惩罚任务。";
  }
  return "现在轮到对方处理棋局。";
}

function assistantPayloadText(source: string, message = ""): string {
  const body = plainText(source || "").trim();
  const note = plainText(message || "").trim();
  if (!note) return body;
  if (!body || body === note) return `本次说明：\n${note}`;
  return `本次说明：\n${note}\n\n当前棋局：\n${body}`;
}

export type AssistantContext = {
  mode: SeseBoardSyncMode;
  message?: string;
  rollText?: string;
};

export type SeseBoardLabels = {
  title?: string;
};

export type SeseBoardGameProps = {
  executeCommand: (command: string) => Promise<SeseBoardPayload> | SeseBoardPayload;
  sendToAssistant?: (payload: SeseBoardPayload, context: AssistantContext) => Promise<AssistantResponse> | AssistantResponse;
  labels?: SeseBoardLabels;
  onBack?: () => void;
  className?: string;
  autoRunAssistant?: boolean;
};

export function createHttpExecutor(endpoint: string, saveId = "default") {
  return async (command: string): Promise<SeseBoardPayload> => {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command, save_id: saveId }),
    });
    const payload = await response.json();
    if (!payload?.ok) throw new Error(payload?.error || "走格棋命令失败");
    return payload;
  };
}

export function SeseBoardGame({ executeCommand, sendToAssistant, labels = {}, onBack = () => undefined, className = "", autoRunAssistant = false }: SeseBoardGameProps) {
  void autoRunAssistant;
  const toast = useCallback((message: string) => {
    if (typeof window !== "undefined") window.setTimeout(() => console.warn(message), 0);
  }, []);
  const executeSeseBoard = useCallback(async (command: string): Promise<SeseBoardPayload> => {
    const next = await executeCommand(command);
    if (!next?.ok) throw new Error(next?.error || "走格棋命令失败");
    return next;
  }, [executeCommand]);
  const gameRef = useRef<HTMLDivElement | null>(null);
  const chatOpenRef = useRef(false);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const rollOnceRef = useRef<((options?: { notifyAfterUserRoll?: boolean }) => Promise<void>) | null>(null);
  const continueAssistantTurnRef = useRef<((state: SeseBoardState | undefined, message?: string, sourceText?: string) => Promise<void>) | null>(null);
  const continueAfterPopupRef = useRef<{ state: SeseBoardState | undefined; message: string; sourceText?: string } | null>(null);
  const pendingRollSyncNoteRef = useRef("");
  const [payload, setPayload] = useState<SeseBoardPayload | null>(null);
  const [displayPositions, setDisplayPositions] = useState<Partial<Record<Actor, number>>>(DEFAULT_POSITIONS);
  const [dice, setDice] = useState(1);
  const [busy, setBusy] = useState(false);
  const [rolling, setRolling] = useState(false);
  const [animating, setAnimating] = useState(false);
  const [activeTile, setActiveTile] = useState<number | null>(null);
  const [popup, setPopup] = useState<EventPopup | null>(null);
  const [drawRevealed, setDrawRevealed] = useState(true);
  const [themeDraw, setThemeDraw] = useState<ThemeDraw | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatUnread, setChatUnread] = useState(0);
  const [chatInput, setChatInput] = useState("");
  const [chatSending, setChatSending] = useState(false);
  const [assistantSyncing, setAssistantSyncing] = useState(false);
  const [finalNoteOpen, setFinalNoteOpen] = useState(false);
  const [finalNoteSeenKey, setFinalNoteSeenKey] = useState("");
  const [toyConsoleOpen, setToyConsoleOpen] = useState(false);
  const [toyConsoleLevel, setToyConsoleLevel] = useState(1);
  const [pendingSubmission, setPendingSubmission] = useState("");
  const [reviewFeedback, setReviewFeedback] = useState<ReviewFeedback | null>(null);
  const [chatMessages, setChatMessages] = useState<GameChatMessage[]>(readStoredGameChatMessages);

  const state = payload?.state || {};
  const boardSize = Math.max(12, Math.min(80, Number(state.board_size || 36)));
  const columns = boardSize <= 36 ? 6 : 8;
  const currentActor = state.turn_actor === "ai" ? "ai" : "player";
  const isGameOver = Boolean(state.game_over || payload?.game_over);
  const isAssistantTurn = currentActor === "ai" && !isGameOver;
  const pendingEvent = state.pending_event || null;
  const localPreviewEnabled = useMemo(() => {
    try {
      return Boolean(import.meta.env.DEV || new URLSearchParams(window.location.search).has("preview"));
    } catch {
      return Boolean(import.meta.env.DEV);
    }
  }, []);

  useLayoutEffect(() => {
    if (gameRef.current) gameRef.current.scrollTop = 0;
  }, []);

  useEffect(() => {
    chatOpenRef.current = chatOpen;
    if (chatOpen) setChatUnread(0);
  }, [chatOpen]);

  useEffect(() => {
    if (!chatOpen) return;
    window.setTimeout(() => chatEndRef.current?.scrollIntoView({ block: "end" }), 40);
  }, [chatMessages.length, chatOpen, chatSending]);

  useEffect(() => {
    writeStoredGameChatMessages(chatMessages);
  }, [chatMessages]);

  useEffect(() => {
    if (!popup || popup.kind !== "draw" || popup.tone !== "reward") {
      setDrawRevealed(true);
      return;
    }
    setDrawRevealed(false);
    const timer = window.setTimeout(() => setDrawRevealed(true), 900);
    return () => window.clearTimeout(timer);
  }, [popup]);

  const appendChat = useCallback((message: GameChatMessage, unread = false) => {
    setChatMessages((items) => [...items, message]);
    if (unread && !chatOpenRef.current) {
      setChatUnread((count) => Math.min(9, count + 1));
    }
  }, []);

  const eventMap = useMemo(() => {
    const map = new Map<number, CellEvent>();
    for (const item of state.cell_events || []) {
      const position = Number(item?.position || 0);
      if (position > 0) map.set(position, item);
    }
    return map;
  }, [state.cell_events]);

  const boardTiles = useMemo(() => {
    return snakeOrder(boardSize, columns).map((position) => {
      const event = eventMap.get(position);
      const kind = eventKind(event, position, boardSize);
      return {
        position,
        event,
        kind,
        icon: eventIcon(kind),
        name: tileName(event, position, boardSize),
      };
    });
  }, [boardSize, columns, eventMap]);

  const applyPayload = useCallback((next: SeseBoardPayload) => {
    setPayload(next);
    setDisplayPositions({
      player: Number(next.state?.positions?.player || 0),
      ai: Number(next.state?.positions?.ai || 0),
    });
  }, []);

  const loadStatus = useCallback(async () => {
    setBusy(true);
    try {
      const next = await executeSeseBoard("status");
      applyPayload(next);
    } catch (e: any) {
      toast(`加载涩涩走格棋失败：${e?.message || e}`);
    } finally {
      setBusy(false);
    }
  }, [applyPayload, toast]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  const animateDice = useCallback(async (finalDice: number) => {
    setRolling(true);
    for (let i = 0; i < 12; i += 1) {
      setDice(Math.floor(Math.random() * 6) + 1);
      await wait(58);
    }
    setDice(Math.max(1, Math.min(6, finalDice || 1)));
    setRolling(false);
  }, []);

  const animateActor = useCallback(async (
    positions: Partial<Record<Actor, number>>,
    actor: Actor,
    from: number,
    to: number,
  ) => {
    const start = Number(from || 0);
    const end = Number(to || 0);
    if (start === end) {
      positions[actor] = end;
      setDisplayPositions({ ...positions });
      setActiveTile(clampPosition(end, boardSize));
      await wait(120);
      return;
    }
    const step = end > start ? 1 : -1;
    for (let pos = start + step; step > 0 ? pos <= end : pos >= end; pos += step) {
      positions[actor] = pos;
      setDisplayPositions({ ...positions });
      setActiveTile(clampPosition(pos, boardSize));
      await wait(145);
    }
  }, [boardSize]);

  const startNewGame = useCallback(async () => {
    if (busy || animating) return;
    setBusy(true);
    setPopup(null);
    try {
      const next = await executeSeseBoard("new_game");
      setDice(1);
      applyPayload(next);
      setChatMessages(defaultGameChatMessages());
      setChatUnread(0);
      setThemeDraw(buildThemeDraw(next.state?.theme_profile?.theme, next.state?.theme_profile?.direction_label, next.state?.theme_options));
    } catch (e: any) {
      toast(`开新局失败：${e?.message || e}`);
    } finally {
      setBusy(false);
    }
  }, [animating, applyPayload, busy, toast]);

  const endGame = useCallback(async () => {
    if (busy || animating) return;
    setBusy(true);
    try {
      const next = await executeSeseBoard("end_game");
      applyPayload(next);
    } catch (e: any) {
      toast(`结束本局失败：${e?.message || e}`);
    } finally {
      setBusy(false);
    }
  }, [animating, applyPayload, busy, toast]);

  const processAssistantReply = useCallback(async (reply: string, nextState: SeseBoardState | undefined) => {
    const assistantReply = reply.trim() || "我看到了。";
    const directive = parseAssistantDirective(assistantReply);
    const pending = nextState?.pending_event || null;
    const assistantChatText = directive.body.trim();
    const isReviewDecision = pending?.reviewer === "ai"
      && pending.type === "review"
      && pending.phase === "submitted"
      && (directive.kind === "approve" || directive.kind === "reject");
    if (assistantChatText && !isReviewDecision) {
      appendChat({ id: makeChatId("ai"), speaker: "ai", text: assistantChatText }, true);
    }
    try {
      if (pending?.type === "duel" && pending.current_actor === "ai") {
        if (directive.kind !== "choose" || !directive.choice.trim()) return;
        const resultText = duelResultText(pending, directive.choice.trim());
        const next = await executeSeseBoard(`choose ${directive.choice.trim()}`);
        applyPayload(next);
        const shouldContinueAssistantTurn = isAssistantTurnState(next.state) && !next.state?.pending_event;
        if (resultText) {
          continueAfterPopupRef.current = shouldContinueAssistantTurn
            ? {
                state: next.state,
                message: "剪刀石头布对抗已结算，现在轮到对方行动。",
                sourceText: next.ai_text || next.text || next.player_text || "",
              }
            : null;
          setPopup({
            position: Number(pending.cell || next.state?.positions?.ai || 0),
            kicker: "剪刀石头布对抗",
            title: "对抗结果",
            text: resultText,
            detail: resultText,
            kind: "event",
          });
        }
        appendChat({ id: makeChatId("system"), speaker: "system", text: resultText || payloadFailureText(next, "对方已出拳，系统已判定对抗结果。") }, true);
        if (!resultText && shouldContinueAssistantTurn) {
          await continueAssistantTurnRef.current?.(next.state, "剪刀石头布对抗已结算，现在轮到对方行动。", next.ai_text || next.text || next.player_text || "");
        }
        return;
      }
      if (pending?.reviewer === "ai" && pending.type === "review" && pending.phase === "questioning") {
        if (directive.kind !== "submit") return;
        const question = directive.body.trim();
        if (!question) {
          appendChat({ id: makeChatId("system"), speaker: "system", text: "对方发了【提交】，但后面没有题目。" }, true);
          return;
        }
        const next = await executeSeseBoard(`submit ${question}`);
        applyPayload(next);
        appendChat({ id: makeChatId("system"), speaker: "system", text: "对方已出题，轮到你回答。" }, true);
        return;
      }
      if (pending?.actor === "ai" && pending.type === "review" && pending.phase === "assigned") {
        if (directive.kind !== "submit") return;
        const submission = directive.body.trim();
        if (!submission) {
          appendChat({ id: makeChatId("system"), speaker: "system", text: "对方发了【提交】，但后面没有提交内容。" }, true);
          return;
        }
        const next = await executeSeseBoard(`submit ${submission}`);
        applyPayload(next);
        appendChat({ id: makeChatId("system"), speaker: "system", text: "对方已提交惩罚任务，等你验收。" }, true);
        await continueAssistantTurnRef.current?.(next.state, assistantFollowupMessage(next.state), next.ai_text || next.text || next.player_text || "");
        return;
      }
      if (pending?.actor === "ai" && pending.type === "choice") {
        if (directive.kind === "pass") {
          const next = await executeSeseBoard("pass");
          applyPayload(next);
          if (next.ok === false) {
            appendChat({ id: makeChatId("system"), speaker: "system", text: payloadFailureText(next, "对方没有Pass卡，不能跳过。") }, true);
            return;
          }
          appendChat({ id: makeChatId("system"), speaker: "system", text: "对方使用Pass卡跳过了惩罚。" }, true);
          await continueAssistantTurnRef.current?.(next.state, assistantFollowupMessage(next.state), next.ai_text || next.text || next.player_text || "");
          return;
        }
        if (directive.kind !== "choose" || !directive.choice.trim()) return;
        const next = await executeSeseBoard(`choose ${directive.choice.trim()}`);
        applyPayload(next);
        appendChat({ id: makeChatId("system"), speaker: "system", text: "对方已选择惩罚选项。" }, true);
        await continueAssistantTurnRef.current?.(next.state, assistantFollowupMessage(next.state), next.ai_text || next.text || next.player_text || "");
        return;
      }
      if (pending?.reviewer === "ai" && pending.type === "review" && pending.phase === "submitted") {
        if (directive.kind === "approve") {
          const shouldRollAfterApprove = assistantIncludesRollDirective(assistantReply);
          const feedbackText = directive.body.trim() || "验收通过。";
          const next = await executeSeseBoard(`approve ${feedbackText}`);
          applyPayload(next);
          setReviewFeedback({
            outcome: "approved",
            title: "对方验收通过",
            text: feedbackText,
            note: shouldRollAfterApprove ? "已继续执行对方的掷骰。" : "棋局继续。",
          });
          if (shouldRollAfterApprove && isAssistantTurnState(next.state)) {
            await wait(260);
            await rollOnceRef.current?.({ notifyAfterUserRoll: false });
            return;
          }
          await continueAssistantTurnRef.current?.(next.state, assistantFollowupMessage(next.state), next.ai_text || next.text || next.player_text || "");
          return;
        }
        if (directive.kind === "reject") {
          const feedbackText = directive.body.trim() || "需要重新提交。";
          const next = await executeSeseBoard(`reject ${feedbackText}`);
          applyPayload(next);
          setReviewFeedback({
            outcome: "rejected",
            title: "对方打回了任务",
            text: feedbackText,
            note: "请按反馈修改后重新提交。",
          });
          return;
        }
        return;
      }
      if (isAssistantTurnState(nextState) && assistantWantsRoll(assistantReply)) {
        await wait(260);
        appendChat({ id: makeChatId("system"), speaker: "system", text: "对方发送【掷骰】，已执行他的行动。" }, true);
        await rollOnceRef.current?.({ notifyAfterUserRoll: false });
      }
    } catch (e: any) {
      appendChat({ id: makeChatId("system"), speaker: "system", text: `对方的指令执行失败：${String(e?.message || e)}` }, true);
    }
  }, [appendChat, applyPayload]);

  const syncSeseBoardWithAssistant = useCallback(async (
    options: { mode: SeseBoardSyncMode; message?: string; rollText?: string; sourceText?: string },
    stateForReply: SeseBoardState | undefined,
  ): Promise<SeseBoardSyncPayload> => {
    let nextState = stateForReply;
    let playerText = "";
    let assistantText = options.sourceText || options.rollText || "";
    if (options.mode === "final_note") {
      const marked = await executeSeseBoard("final_note_sent");
      nextState = marked.state || nextState;
      playerText = marked.player_text || marked.text || "";
      assistantText = marked.ai_text || marked.text || marked.player_text || assistantText;
    }
    const aiText = assistantPayloadText(assistantText || options.message || "", options.message);
    const basePayload: SeseBoardPayload = {
      ok: true,
      text: aiText,
      ai_text: aiText,
      state: nextState,
      player_text: playerText || aiText,
    };
    let reply = "";
    if (sendToAssistant) {
      const assistantResult = await sendToAssistant(basePayload, {
        mode: options.mode,
        message: options.message,
        rollText: options.rollText,
      });
      if (assistantResult && typeof assistantResult === "object") {
        const syncPayload = assistantResult as SeseBoardSyncPayload;
        const syncedReply = plainText(
          syncPayload.reply_text
            || syncPayload.wakeup?.reply_text
            || syncPayload.reply_preview
            || syncPayload.wakeup?.reply_preview
            || "",
        ).trim();
        return {
          ...syncPayload,
          ok: syncPayload.ok !== false,
          state: syncPayload.state || nextState,
          player_text: syncPayload.player_text || playerText,
          reply_text: syncedReply,
          reply_preview: syncPayload.reply_preview || syncPayload.wakeup?.reply_preview || syncedReply.slice(0, 120),
        };
      }
      reply = plainText(assistantResult).trim();
    } else if (localPreviewEnabled) {
      reply = localAssistantReplyForState(options.mode, nextState);
    }
    return {
      ok: true,
      state: nextState,
      player_text: playerText,
      reply_text: reply,
      reply_preview: reply.slice(0, 120),
      wakeup: {
        reply_text: reply,
        reply_preview: reply.slice(0, 120),
      },
    };
  }, [executeSeseBoard, localPreviewEnabled, sendToAssistant]);

  const continueAssistantTurn = useCallback(async (
    stateForReply: SeseBoardState | undefined,
    message = "现在轮到对方行动。",
    sourceText = "",
  ) => {
    const assistantPending = isAssistantPendingState(stateForReply);
    if (!isAssistantTurnState(stateForReply) || (stateForReply?.pending_event && !assistantPending)) return;
    setAssistantSyncing(true);
    try {
      const next = await syncSeseBoardWithAssistant({
        mode: "state_update",
        message,
        rollText: "",
        sourceText,
      }, stateForReply);
      if (next.state) {
        applyPayload({
          ok: true,
          state: next.state,
          player_text: next.player_text || "",
        });
      }
      const reply = plainText(next.reply_text || next.wakeup?.reply_text || next.reply_preview || next.wakeup?.reply_preview || "").trim();
      if (hasAppliedAssistantCommands(next)) {
        if (shouldContinueAfterAppliedAssistantCommands(next)) {
          await continueAssistantTurnRef.current?.(next.state, assistantFollowupMessage(next.state), next.player_text || "");
        }
        return;
      }
      await processAssistantReply(reply, next.state || stateForReply);
    } catch (e: any) {
      const error = String(e?.message || e || "同步失败");
      appendChat({ id: makeChatId("system"), speaker: "system", text: `对方行动同步失败：${error}` }, true);
      toast(`对方行动同步失败：${error}`);
    } finally {
      setAssistantSyncing(false);
    }
  }, [appendChat, applyPayload, processAssistantReply, syncSeseBoardWithAssistant, toast]);

  useEffect(() => {
    continueAssistantTurnRef.current = continueAssistantTurn;
  }, [continueAssistantTurn]);

  const closePopup = useCallback(() => {
    const next = continueAfterPopupRef.current;
    continueAfterPopupRef.current = null;
    setPopup(null);
    if (next) {
      void continueAssistantTurnRef.current?.(next.state, next.message, next.sourceText);
    }
  }, []);

  const notifyRollResultToAssistant = useCallback(async (rolled: SeseBoardPayload, message = "你刚掷完骰子。") => {
    const rollText = plainText(rolled.text || rolled.ai_text || rolled.player_text || "").trim();
    const pendingNote = pendingRollSyncNoteRef.current.trim();
    const baseMessage = message.trim() === "你刚掷完骰子。" ? "" : message.trim();
    const syncMessage = [pendingNote, baseMessage].filter(Boolean).join("\n");
    setAssistantSyncing(true);
    try {
      const next = await syncSeseBoardWithAssistant({
        mode: "roll_result",
        message: syncMessage,
        rollText,
      }, rolled.state);
      if (pendingNote && pendingRollSyncNoteRef.current.trim() === pendingNote) {
        pendingRollSyncNoteRef.current = "";
      }
      if (next.state) {
        applyPayload({
          ok: true,
          state: next.state,
          player_text: next.player_text || rolled.player_text || "",
        });
      }
      const reply = plainText(next.reply_text || next.wakeup?.reply_text || next.reply_preview || next.wakeup?.reply_preview || "").trim();
      if (hasAppliedAssistantCommands(next)) {
        if (shouldContinueAfterAppliedAssistantCommands(next)) {
          await continueAssistantTurnRef.current?.(next.state, assistantFollowupMessage(next.state), next.player_text || rolled.player_text || "");
        }
        return;
      }
      await processAssistantReply(reply, next.state || rolled.state);
    } catch (e: any) {
      const message = String(e?.message || e || "同步失败");
      appendChat({ id: makeChatId("system"), speaker: "system", text: `自动同步失败：${message}` }, true);
      toast(`自动同步给对方失败：${message}`);
    } finally {
      setAssistantSyncing(false);
    }
  }, [appendChat, applyPayload, processAssistantReply, syncSeseBoardWithAssistant, toast]);

  const rollOnce = useCallback(async (options: { notifyAfterUserRoll?: boolean } = {}) => {
    if (busy || animating || isGameOver) return;
    let notifyPayload: SeseBoardPayload | null = null;
    let continuePayload: SeseBoardPayload | null = null;
    setBusy(true);
    setAnimating(true);
    setPopup(null);
    const beforePositions: Partial<Record<Actor, number>> = {
      player: Number(state.positions?.player || 0),
      ai: Number(state.positions?.ai || 0),
    };
    const actorBeforeRoll = state.turn_actor === "ai" ? "ai" : "player";
    const visualPositions = { ...beforePositions };
    try {
      const next = await executeSeseBoard("roll");
      const move = parseMove(next.player_text || "");
      await animateDice(move?.dice || Math.floor(Math.random() * 6) + 1);
      if (move) {
        await animateActor(visualPositions, move.actor, move.from, move.to);
      }
      const finalPositions: Partial<Record<Actor, number>> = {
        player: Number(next.state?.positions?.player || 0),
        ai: Number(next.state?.positions?.ai || 0),
      };
      for (const actor of ACTORS) {
        const current = Number(visualPositions[actor] || 0);
        const target = Number(finalPositions[actor] || 0);
        if (current !== target) {
          await animateActor(visualPositions, actor, current, target);
        }
      }
      applyPayload(next);
      const nextPopup = parseEventPopup(next.player_text || "", move);
      if (nextPopup) setPopup(nextPopup);
      const pendingAfterRoll = next.state?.pending_event || null;
      if (
        options.notifyAfterUserRoll !== false
        && actorBeforeRoll === "player"
        && !next.state?.game_over
        && (!pendingAfterRoll || isAssistantPendingState(next.state))
      ) {
        notifyPayload = next;
      } else if (options.notifyAfterUserRoll === false && actorBeforeRoll === "ai" && isAssistantTurnState(next.state)) {
        continuePayload = next;
      }
    } catch (e: any) {
      toast(`掷骰失败：${e?.message || e}`);
    } finally {
      setBusy(false);
      setAnimating(false);
      window.setTimeout(() => setActiveTile(null), 260);
    }
    if (notifyPayload) {
      await notifyRollResultToAssistant(notifyPayload);
    } else if (continuePayload) {
      await continueAssistantTurnRef.current?.(
        continuePayload.state,
        assistantFollowupMessage(continuePayload.state),
        continuePayload.ai_text || continuePayload.text || continuePayload.player_text || "",
      );
    }
  }, [animateActor, animateDice, animating, applyPayload, busy, isGameOver, notifyRollResultToAssistant, state.positions, state.turn_actor, toast]);

  useEffect(() => {
    rollOnceRef.current = rollOnce;
  }, [rollOnce]);

  const executePendingCommand = useCallback(async (
    command: string,
    options: { success?: string; syncAfter?: boolean; syncMessage?: string; deferSyncMessage?: string } = {},
  ) => {
    if (busy || !payload?.state) return;
    let nextPayload: SeseBoardPayload | null = null;
    setBusy(true);
    setPopup(null);
    try {
      const next = await executeSeseBoard(command);
      nextPayload = next;
      applyPayload(next);
      if (next.ok === false) {
        toast(payloadFailureText(next, "这次操作没有生效。"));
        return;
      }
      setPendingSubmission("");
      if (options.success) {
        appendChat({ id: makeChatId("system"), speaker: "system", text: options.success }, true);
      }
      if (options.deferSyncMessage?.trim()) {
        pendingRollSyncNoteRef.current = options.deferSyncMessage.trim();
      }
    } catch (e: any) {
      toast(`处理惩罚任务失败：${e?.message || e}`);
    } finally {
      setBusy(false);
    }
    if (nextPayload && options.syncAfter) {
      await continueAssistantTurnRef.current?.(
        nextPayload.state,
        options.syncMessage || assistantFollowupMessage(nextPayload.state),
        nextPayload.ai_text || nextPayload.text || nextPayload.player_text || "",
      );
    }
  }, [appendChat, applyPayload, busy, payload?.state, toast]);

  const submitPending = useCallback(() => {
    const text = pendingSubmission.trim();
    if (!text) {
      toast("先写提交内容。");
      return;
    }
    void executePendingCommand(`submit ${text}`, {
      success: "已提交任务，等对方验收。",
      syncAfter: true,
      syncMessage: "你提交了惩罚任务，请你验收。",
    });
  }, [executePendingCommand, pendingSubmission, toast]);

  const approvePending = useCallback(() => {
    const feedback = pendingSubmission.trim();
    void executePendingCommand(feedback ? `approve ${feedback}` : "approve", {
      success: "你通过了任务，棋局继续。",
      deferSyncMessage: feedback ? `你刚刚通过了对方的惩罚任务：${feedback}` : "你刚刚通过了对方的惩罚任务。",
    });
  }, [executePendingCommand, pendingSubmission]);

  const rejectPending = useCallback(() => {
    const feedback = pendingSubmission.trim();
    void executePendingCommand(feedback ? `reject ${feedback}` : "reject", {
      success: "你打回了任务，等对方重新提交。",
      syncAfter: true,
      syncMessage: feedback ? `你打回了对方的惩罚任务：${feedback}` : "你打回了对方的惩罚任务，请重新提交。",
    });
  }, [executePendingCommand, pendingSubmission]);

  const choosePending = useCallback((choiceId: string) => {
    const isDuel = pendingEvent?.type === "duel";
    const duelActor = pendingEvent?.current_actor || pendingEvent?.actor;
    const isPlayerDuelPick = isDuel && duelActor === "player";
    if (isDuel && !isPlayerDuelPick) {
      toast("等待对方出拳。");
      return;
    }
    void executePendingCommand(`choose ${choiceId}`, {
      success: isDuel ? "已出拳，等待对方出拳。" : "已选择惩罚，棋局继续。",
      syncAfter: true,
      syncMessage: isDuel
        ? "你已在剪刀石头布对抗中出拳。请第一行单独发送【剪刀石头布：石头】、【剪刀石头布：剪刀】或【剪刀石头布：布】。"
        : "你处理完选择惩罚，棋局继续。",
    });
  }, [executePendingCommand, pendingEvent?.actor, pendingEvent?.current_actor, pendingEvent?.type, toast]);

  const passPending = useCallback(() => {
    void executePendingCommand("pass", {
      success: "已使用Pass卡跳过惩罚。",
      syncAfter: true,
      syncMessage: "你使用Pass卡跳过了惩罚任务。",
    });
  }, [executePendingCommand]);

  const sendFinalNote = useCallback(async () => {
    const note = payload?.state?.final_note || null;
    if (chatSending || assistantSyncing || busy || animating || !payload?.state || !note || note.sent) return;
    setChatSending(true);
    try {
      const next = await syncSeseBoardWithAssistant({
        mode: "final_note",
        message: note.text || "",
      }, payload.state);
      if (next.state) {
        applyPayload({
          ok: true,
          state: next.state,
          player_text: next.player_text || payload.player_text || "",
        });
      }
      appendChat({ id: makeChatId("system"), speaker: "system", text: localPreviewEnabled ? "预览模式：终局小纸条已同步。" : "终局小纸条已发送给对方。" }, true);
      const reply = plainText(next.reply_text || next.wakeup?.reply_text || next.reply_preview || next.wakeup?.reply_preview || "").trim();
      if (reply) appendChat({ id: makeChatId("ai"), speaker: "ai", text: reply }, true);
      setFinalNoteOpen(false);
    } catch (e: any) {
      const message = String(e?.message || e || "同步失败");
      appendChat({ id: makeChatId("system"), speaker: "system", text: `小纸条发送失败：${message}` }, true);
      toast(`发送终局小纸条失败：${message}`);
    } finally {
      setChatSending(false);
    }
  }, [animating, appendChat, applyPayload, busy, chatSending, assistantSyncing, localPreviewEnabled, payload, syncSeseBoardWithAssistant, toast]);

  const appendFinalStatus = useCallback(async (slot: FinalAppendSlot, value: string, level = 1) => {
    if (chatSending || assistantSyncing || busy || animating || !payload?.state) return;
    const cleanValue = value.replace(/\s+/g, " ").trim();
    if (!cleanValue) {
      toast("先选要追加的内容。");
      return;
    }
    const levelPart = slot === "prop" && isLevelableProp(cleanValue)
      ? ` level=${Math.max(1, Math.min(5, Math.round(Number(level) || 1)))}`
      : "";
    setBusy(true);
    try {
      const next = await executeSeseBoard(`append_final_status ${slot} ${cleanValue}${levelPart}`);
      applyPayload(next);
      setFinalNoteOpen(true);
      toast(`已启用：${cleanValue}`);
    } catch (e: any) {
      toast(`追加失败：${e?.message || e}`);
    } finally {
      setBusy(false);
    }
  }, [animating, applyPayload, busy, chatSending, assistantSyncing, payload?.state, toast]);

  const removeFinalStatus = useCallback(async (slot: FinalAppendSlot, value: string) => {
    if (chatSending || assistantSyncing || busy || animating || !payload?.state) return;
    const cleanValue = value.replace(/\s+/g, " ").trim();
    if (!cleanValue) return;
    setBusy(true);
    try {
      const next = await executeSeseBoard(`remove_final_status ${slot} ${cleanValue}`);
      applyPayload(next);
      setFinalNoteOpen(true);
      toast(`已取消：${cleanValue}`);
    } catch (e: any) {
      toast(`取消失败：${e?.message || e}`);
    } finally {
      setBusy(false);
    }
  }, [animating, applyPayload, busy, chatSending, assistantSyncing, payload?.state, toast]);

  const sendGameChat = useCallback(async () => {
    if (chatSending || assistantSyncing || busy || animating || !payload?.state) return;
    const message = chatInput.trim();
    if (!message) return;
    const userChatMessage: GameChatMessage = { id: makeChatId("player"), speaker: "player", text: message };
    setChatInput("");
    appendChat(userChatMessage);
    setChatSending(true);
    try {
      const next = await syncSeseBoardWithAssistant({
        mode: "chat",
        message,
      }, payload.state);
      if (next.state) {
        applyPayload({
          ok: true,
          state: next.state,
          player_text: next.player_text || payload.player_text || "",
        });
      }
      const reply = plainText(next.reply_text || next.wakeup?.reply_text || next.reply_preview || next.wakeup?.reply_preview || "").trim();
      await processAssistantReply(reply, next.state || payload.state);
    } catch (e: any) {
      const message = String(e?.message || e || "同步失败");
      appendChat({ id: makeChatId("system"), speaker: "system", text: `交流失败：${message}` });
      toast(`游戏内交流失败：${message}`);
    } finally {
      setChatSending(false);
    }
  }, [animating, appendChat, applyPayload, busy, chatInput, chatSending, assistantSyncing, payload, processAssistantReply, syncSeseBoardWithAssistant, toast]);

  const themeName = displayText(state.theme_profile?.theme || "未触发");
  const directionLabel = displayText(state.theme_profile?.direction_label || "待定");
  const meProgress = progressPosition(state.positions?.player, boardSize);
  const duProgress = progressPosition(state.positions?.ai, boardSize);
  const winnerLabel = state.winner ? ACTOR_LABEL[state.winner] : "";
  const lines = recentLines(payload?.player_text || "");
  const finalNote = state.final_note || null;
  const finalMaterialItems = finalMaterialItemsFrom(state.final_note_items || [], finalNote);
  const finalNoteKey = String(finalNote?.id || `${state.winner || ""}-${state.updated_at || ""}`);
  const canUseToyConsole = Boolean(
    isGameOver
      && state.winner === "player"
      && (!finalNote || finalNote.target === "ai")
      && !finalNote?.sent
  );
  const finalTargetStatuses = state.statuses?.ai || [];
  const activeFinalProps = finalTargetStatuses.filter((item) => item.slot === "prop").map((item) => displayText(item.value || ""));

  useEffect(() => {
    if (!isGameOver || !finalNote || !finalNoteKey) return;
    if (finalNoteSeenKey === finalNoteKey) return;
    setFinalNoteSeenKey(finalNoteKey);
    setFinalNoteOpen(true);
  }, [finalNote, finalNoteKey, finalNoteSeenKey, isGameOver]);
  const myPassCount = Math.max(0, Number(state.hands?.player?.pass || 0));
  const passSkipsUsed = Math.max(0, Number(state.pass_skips_used || 0));
  const pausedByActor: Record<Actor, boolean> = {
    player: actorPaused(state.statuses?.player),
    ai: actorPaused(state.statuses?.ai),
  };
  const canProcessAssistantPause = isAssistantTurn && pausedByActor.ai && !pendingEvent;
  const rollDisabled = busy || animating || chatSending || assistantSyncing || !payload?.state || Boolean(pendingEvent) || (isAssistantTurn && !canProcessAssistantPause);
  const chatInputDisabled = !payload?.state;
  const chatSubmitDisabled = chatSending || assistantSyncing || busy || animating || !payload?.state;

  return (
    <div className={["sese-game", className].filter(Boolean).join(" ")} ref={gameRef}>
      <div className="sese-header">
        <button className="sese-back" type="button" onClick={onBack} aria-label="返回游戏">
          <ChevronLeftIcon />
        </button>
        <button className="sese-chat-entry" type="button" onClick={() => setChatOpen(true)} aria-label="游戏内交流">
          <MessageCircleIconMini />
          {chatUnread ? <span>{chatUnread}</span> : null}
        </button>
        <div className="sese-header-title">{labels.title || "涩涩走格棋"}</div>
        <div className="sese-game-status-bar">
          <StatusPill label="主题" value={themeName} />
          <StatusPill label="主导方" value={directionLabel} />
          <StatusPill label="你 进度" value={`${String(meProgress).padStart(2, "0")} / ${boardSize}`} />
          <StatusPill label="对方 进度" value={`${String(duProgress).padStart(2, "0")} / ${boardSize}`} />
          <div className="sese-turn-indicator">
            {isGameOver && winnerLabel ? `${winnerLabel} 到达终点` : isAssistantTurn ? "等待 对方 行动..." : "轮到 你 行动"}
          </div>
        </div>
      </div>

      <section className="sese-board-container" aria-label="走格棋盘">
        <div className="sese-board" style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}>
          {boardTiles.map((tile) => {
            const pieces = ACTORS.filter((actor) => clampPosition(displayPositions[actor], boardSize) === tile.position);
            return (
              <div
                key={tile.position}
                className={`sese-tile sese-tile-${tile.kind} ${activeTile === tile.position ? "is-active" : ""}`}
              >
                <div className="sese-tile-number">{tile.position}</div>
                <div className="sese-tile-icon">{tile.icon}</div>
                <div className="sese-tile-name">{tile.name}</div>
                <div className="sese-piece-stack">
                  {pieces.map((actor) => (
                    <span
                      key={actor}
                      className={`sese-piece ${actor === "player" ? "sese-piece-me" : "sese-piece-ai"} ${pausedByActor[actor] ? "paused" : ""}`}
                    >
                      {ACTOR_LABEL[actor]}
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="sese-controls">
        <div className="sese-player-states">
          <PlayerStateCard actor="player" statuses={state.statuses?.player || []} active={currentActor === "player"} />
          <PlayerStateCard
            actor="ai"
            statuses={state.statuses?.ai || []}
            active={currentActor === "ai"}
          />
        </div>

        {finalMaterialItems.length ? (
          <div className="sese-final-pose-panel">
            {finalMaterialItems.map((item) => (
              <div className="sese-final-material-row" key={item.label}>
                <span>{item.label}</span>
                <strong>{item.values.join("、")}</strong>
              </div>
            ))}
          </div>
        ) : null}

        <div className="sese-action-area">
          <div className={`sese-dice ${rolling ? "rolling" : ""}`} aria-label={`骰子 ${dice}`}>
            {dice}
          </div>
          <button
            className="sese-roll-button"
            type="button"
            disabled={rollDisabled}
            onClick={isGameOver ? startNewGame : () => void rollOnce({ notifyAfterUserRoll: true })}
          >
            {isGameOver ? "开新局" : pendingEvent ? "先处理任务" : canProcessAssistantPause ? "处理停步" : isAssistantTurn ? "等对方掷骰" : busy || animating ? "移动中" : chatSending || assistantSyncing ? "等对方回应" : "掷骰子"}
          </button>
          <button
            className="sese-restart-button"
            type="button"
            disabled={busy || animating || chatSending || assistantSyncing}
            onClick={startNewGame}
          >
            重开
          </button>
        </div>

        <div className="sese-history">
          {lines.length ? `最近：${lines[0]}` : "最近：等待第一次掷骰"}
        </div>
      </section>

      {chatOpen ? (
        <div className="sese-chat-mask" role="dialog" aria-modal="true" aria-label="游戏内交流" onClick={() => setChatOpen(false)}>
          <div className="sese-chat-panel" onClick={(event) => event.stopPropagation()}>
            <div className="sese-chat-head">
              <div>
                <strong>游戏内交流</strong>
                <span>{isAssistantTurn ? "等待对方发送【掷骰】" : "当前轮到你行动"}</span>
              </div>
              <button type="button" onClick={() => setChatOpen(false)} aria-label="关闭交流">×</button>
            </div>
            <div className="sese-chat-list">
              {chatMessages.map((message) => (
                <div key={message.id} className={`sese-chat-message ${message.speaker}`}>
                  <span>{message.speaker === "player" ? "你" : message.speaker === "ai" ? "对方" : "系统"}</span>
                  <p>{plainText(message.text)}</p>
                </div>
              ))}
              {chatSending ? (
                <div className="sese-chat-message ai pending">
                  <span>对方</span>
                  <p>正在回复...</p>
                </div>
              ) : null}
              <div ref={chatEndRef} />
            </div>
            <form className="sese-chat-form" onSubmit={(event) => {
              event.preventDefault();
              void sendGameChat();
            }}>
              <input
                value={chatInput}
                disabled={chatInputDisabled}
                placeholder="和对方说一句游戏内的话"
                onChange={(event) => setChatInput(event.target.value)}
              />
              <button type="submit" disabled={chatSubmitDisabled || !chatInput.trim()} aria-label={chatSending ? "发送中" : "发送"}>
                <SendIconMini />
              </button>
            </form>
          </div>
        </div>
      ) : null}

      {themeDraw ? (
        <div className="sese-theme-mask" role="dialog" aria-modal="true" aria-label="开局主题抽取">
          <div className="sese-theme-modal">
            <div className="sese-slot-lights" aria-hidden="true">
              <i />
              <i />
              <i />
              <i />
              <i />
              <i />
              <i />
            </div>
            <div className="sese-slot-marquee">
              <span>THEME</span>
              <strong>JACKPOT</strong>
            </div>
            <div className="sese-slot-face">
              <div className="sese-theme-window">
                <div className="sese-theme-strip" key={themeDraw.spinKey}>
                  {themeDraw.items.map((item, index) => (
                    <div className="sese-theme-item" key={`${item}-${index}`}>{displayText(item)}</div>
                  ))}
                </div>
              </div>
              <p className="sese-slot-plaque">主导方：{themeDraw.direction}</p>
              <div className="sese-theme-actions">
                <button className="secondary" type="button" disabled={busy} onClick={startNewGame}>{busy ? "重抽中" : "重抽主题"}</button>
                <button type="button" onClick={() => setThemeDraw(null)}>开始本局</button>
              </div>
              <div className="sese-slot-tray" aria-hidden="true" />
            </div>
          </div>
        </div>
      ) : null}

      {pendingEvent && !popup ? (
        <div className="sese-pending-mask" role="dialog" aria-modal="true" aria-label="待处理惩罚">
          <div className="sese-pending-modal">
            <PendingEventPanel
              pending={pendingEvent}
              reviewFeedback={reviewFeedback}
              passCount={myPassCount}
              passSkipsUsed={passSkipsUsed}
              submission={pendingSubmission}
              disabled={busy || assistantSyncing}
              onSubmissionChange={setPendingSubmission}
              onSubmit={submitPending}
              onApprove={approvePending}
              onReject={rejectPending}
              onChoose={choosePending}
              onPass={passPending}
            />
          </div>
        </div>
      ) : null}

      {isGameOver && finalNote && finalNoteOpen ? (
        <div className="sese-final-note-mask" role="dialog" aria-modal="true" aria-label="终局小纸条">
          <div className="sese-final-note-modal">
            <div className="sese-final-note-head">
              <span>终局小纸条</span>
              <button type="button" onClick={() => setFinalNoteOpen(false)} aria-label="关闭终局小纸条">关闭</button>
            </div>
            <h2>{winnerLabel || "玩家"} 到达终点</h2>
            <FinalNoteContent
              note={finalNote}
              canAddStatus={canUseToyConsole}
              onAddStatus={() => setToyConsoleOpen(true)}
            />
            {finalNote.sent ? (
              <em>已发送给对方</em>
            ) : (
              <button className="sese-final-note-send" type="button" disabled={chatSending || assistantSyncing || busy || animating} onClick={() => void sendFinalNote()}>
                {chatSending ? "发送中" : "发送给对方"}
              </button>
            )}
          </div>
        </div>
      ) : null}

      {canUseToyConsole && toyConsoleOpen ? (
        <ToyConsoleSheet
          level={toyConsoleLevel}
          activeProps={activeFinalProps}
          disabled={chatSending || assistantSyncing || busy || animating}
          onClose={() => setToyConsoleOpen(false)}
          onLevelChange={setToyConsoleLevel}
          onToggleProp={(value, active) => {
            if (active) void removeFinalStatus("prop", value);
            else void appendFinalStatus("prop", value, toyConsoleLevel);
          }}
        />
      ) : null}

      {popup ? (
        <div className="sese-popup-mask" role="dialog" aria-modal="true">
          <div className={`sese-popup ${popup.kind === "draw" ? `sese-popup-draw tone-${popup.tone || "penalty"}` : ""}`}>
            <div className="sese-popup-kicker">
              {displaySystemText(popup.kicker || (popup.actorLabel ? `${popup.actorLabel}走到第 ${popup.position} 格` : `第 ${popup.position} 格`))}
            </div>
            {popup.kind === "draw" ? (
              <div className={`sese-draw-card ${popup.tone === "reward" && !drawRevealed ? "is-covered" : "is-revealed"}`}>
                {popup.tone === "reward" && !drawRevealed ? (
                  <>
                    <div className="sese-card-pile" aria-hidden="true">
                      <i />
                      <i />
                      <i />
                      <i />
                      <b />
                    </div>
                    <span>奖励抽卡</span>
                    <em>抽卡中</em>
                  </>
                ) : (
                  <>
                    {popupCardTypeText(popup) ? <span>{popupCardTypeText(popup)}</span> : null}
                    <strong>{displaySystemText(popup.cardTitle || popup.title)}</strong>
                  </>
                )}
              </div>
            ) : null}
            {popup.kind === "draw" ? null : <h2>{displaySystemText(popup.title)}</h2>}
            {popup.tone === "reward" && !drawRevealed ? <p>正在洗牌...</p> : popupDetailText(popup) ? <p>{popupDetailText(popup)}</p> : null}
            {popup.tone === "reward" && !drawRevealed ? null : <button type="button" onClick={closePopup}>确 认</button>}
          </div>
        </div>
      ) : null}

      {reviewFeedback ? (
        <div className="sese-pending-mask" role="dialog" aria-modal="true" aria-label="验收反馈">
          <div className="sese-pending-modal">
            <ReviewFeedbackPanel feedback={reviewFeedback} onClose={() => setReviewFeedback(null)} />
          </div>
        </div>
      ) : null}

      <style>
        {`
        .sese-game {
          --primary-pink: #f8bbd0;
          --soft-lavender: #f3e5f5;
          --accent-yellow: #fff9c4;
          --accent-mint: #e0f2f1;
          --accent-blue: #e1f5fe;
          --text-main: #884d8a;
          --text-light: #ba68c8;
          --bg-page: #fce4ec;
          --card-white: rgba(255, 255, 255, 0.86);
          --sese-safe-top: max(calc(env(safe-area-inset-top, 0px) + 12px), 44px);
          position: absolute;
          inset: 0;
          z-index: 34;
          min-height: 100dvh;
          overflow-y: auto;
          background:
            linear-gradient(180deg, rgba(255,255,255,0.62) 0, rgba(255,255,255,0) 210px),
            var(--bg-page);
          color: var(--text-main);
          font-family: "Microsoft YaHei", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          padding: var(--sese-safe-top) 14px calc(env(safe-area-inset-bottom, 0px) + 22px);
        }
        .sese-game,
        .sese-game * {
          box-sizing: border-box;
        }
        .sese-header {
          display: flex;
          align-items: center;
          gap: 10px;
          margin: 0 auto 12px;
          max-width: 720px;
        }
        .sese-back,
        .sese-header-button,
        .sese-quiet-button {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border: 0;
          border-radius: 999px;
          background: rgba(255, 255, 255, 0.82);
          color: var(--text-main);
          box-shadow: 0 8px 18px rgba(136, 77, 138, 0.14);
          transition: transform 140ms ease, opacity 140ms ease;
        }
        .sese-back {
          width: 42px;
          height: 42px;
          flex: 0 0 42px;
        }
        .sese-header-button {
          min-width: 58px;
          height: 36px;
          padding: 0 14px;
          font-size: 13px;
          font-weight: 800;
        }
        .sese-back:active,
        .sese-header-button:active,
        .sese-roll-button:active,
        .sese-quiet-button:active {
          transform: scale(0.96);
        }
        .sese-header-button:disabled,
        .sese-roll-button:disabled,
        .sese-quiet-button:disabled {
          opacity: 0.54;
        }
        .sese-title-block {
          min-width: 0;
          flex: 1;
          text-align: center;
        }
        .sese-title-block h1 {
          margin: 0;
          color: var(--text-main);
          font-size: 24px;
          font-weight: 900;
          line-height: 1.12;
          text-shadow: 0 2px 0 rgba(255, 255, 255, 0.82);
        }
        .sese-title-block p {
          margin: 4px 0 0;
          color: var(--text-light);
          font-size: 12px;
          font-weight: 800;
          line-height: 1.2;
        }
        .sese-status-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 8px;
          margin: 0 auto 12px;
          max-width: 720px;
        }
        .sese-pill {
          min-height: 54px;
          overflow: hidden;
          border: 1px solid rgba(255, 255, 255, 0.72);
          border-radius: 18px;
          background: var(--card-white);
          padding: 8px 10px;
          box-shadow: 0 10px 22px rgba(136, 77, 138, 0.1);
        }
        .sese-pill span {
          display: block;
          color: var(--text-light);
          font-size: 10px;
          font-weight: 900;
          line-height: 1.1;
        }
        .sese-pill strong {
          display: block;
          margin-top: 4px;
          overflow: hidden;
          color: var(--text-main);
          font-size: 13px;
          font-weight: 900;
          line-height: 1.18;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .sese-board-wrap {
          margin: 0 auto;
          max-width: 720px;
          border: 6px solid rgba(255, 255, 255, 0.84);
          border-radius: 26px;
          background: rgba(255, 255, 255, 0.62);
          padding: 8px;
          box-shadow: 0 18px 38px rgba(136, 77, 138, 0.16);
        }
        .sese-board {
          display: grid;
          gap: 6px;
          width: 100%;
        }
        .sese-tile {
          position: relative;
          display: flex;
          aspect-ratio: 1;
          min-width: 0;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          overflow: hidden;
          border: 1px solid rgba(255, 255, 255, 0.8);
          border-radius: 14px;
          background: rgba(255, 255, 255, 0.8);
          box-shadow: inset 0 1px 0 rgba(255,255,255,0.9), 0 5px 10px rgba(136, 77, 138, 0.08);
          transition: transform 170ms ease, box-shadow 170ms ease;
        }
        .sese-tile.is-active {
          transform: translateY(-2px) scale(1.03);
          box-shadow: inset 0 1px 0 rgba(255,255,255,0.96), 0 10px 20px rgba(136, 77, 138, 0.2);
        }
        .sese-tile-start { background: #e0f2f1; }
        .sese-tile-end { background: #fff9c4; }
        .sese-tile-place { background: #e1f5fe; }
        .sese-tile-item { background: #f3e5f5; }
        .sese-tile-task { background: #f8bbd0; }
        .sese-tile-move { background: #fff9c4; }
        .sese-tile-reset { background: #ffe0ec; }
        .sese-tile-finish-jump { background: #fff3b0; }
        .sese-tile-swap { background: #e0f2f1; }
        .sese-tile-clear { background: #ffffff; }
        .sese-tile-time { background: #fff7dd; }
        .sese-tile-limit { background: #ffe3ea; }
        .sese-tile-pose { background: #edf7ff; }
        .sese-tile-theme { background: #f6e9ff; }
        .sese-tile-empty {
          border-color: rgba(255, 255, 255, 0.55);
          background: rgba(255, 255, 255, 0.46);
          box-shadow: inset 0 1px 0 rgba(255,255,255,0.62);
        }
        .sese-tile-empty .sese-tile-icon {
          display: none;
        }
        .sese-tile-empty .sese-tile-name {
          color: rgba(136, 77, 138, 0.38);
          font-weight: 700;
        }
        .sese-tile-number {
          position: absolute;
          left: 6px;
          top: 5px;
          color: rgba(136, 77, 138, 0.46);
          font-size: 9px;
          font-weight: 900;
          line-height: 1;
        }
        .sese-tile-icon {
          height: 18px;
          color: var(--text-main);
          font-size: 15px;
          font-weight: 900;
          line-height: 18px;
        }
        .sese-tile-name {
          display: -webkit-box;
          width: calc(100% - 8px);
          min-height: 20px;
          overflow: hidden;
          -webkit-box-orient: vertical;
          -webkit-line-clamp: 2;
          color: var(--text-main);
          font-size: 9px;
          font-weight: 900;
          line-height: 10px;
          text-align: center;
        }
        .sese-piece-stack {
          position: absolute;
          inset: auto 4px 4px;
          display: flex;
          justify-content: center;
          gap: 3px;
          min-height: 17px;
          pointer-events: none;
        }
        .sese-piece {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 24px;
          height: 16px;
          border: 2px solid #ffffff;
          border-radius: 999px;
          font-size: 10px;
          font-weight: 900;
          line-height: 1;
          box-shadow: 0 5px 10px rgba(68, 42, 77, 0.18);
          animation: sesePiecePop 180ms ease both;
        }
        .sese-piece-player {
          background: #ff6f91;
          color: #ffffff;
        }
        .sese-piece-ai {
          background: #7bc9ff;
          color: #ffffff;
        }
        .sese-control-panel {
          margin: 12px auto 0;
          max-width: 720px;
          border: 1px solid rgba(255, 255, 255, 0.78);
          border-radius: 26px;
          background: var(--card-white);
          padding: 12px;
          box-shadow: 0 16px 36px rgba(136, 77, 138, 0.12);
        }
        .sese-player-row {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 10px;
        }
        .sese-player-card {
          min-height: 98px;
          border-radius: 20px;
          padding: 10px;
          background: rgba(255, 255, 255, 0.74);
          box-shadow: inset 0 1px 0 rgba(255,255,255,0.78);
        }
        .sese-player-card-head {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
          margin: 0 0 7px;
        }
        .sese-player-card h2 {
          margin: 0;
          color: var(--text-main);
          font-size: 14px;
          font-weight: 900;
          line-height: 1.2;
        }
        .sese-status-list {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .sese-status-empty {
          border-radius: 12px;
          background: rgba(248, 187, 208, 0.22);
          padding: 6px 7px;
          color: #7c4a80;
          font-size: 11px;
          font-weight: 800;
          line-height: 1.25;
        }
        .sese-status-group {
          display: grid;
          gap: 4px;
        }
        .sese-status-group-label {
          color: rgba(124, 74, 128, 0.62);
          font-size: 10px;
          font-weight: 900;
          line-height: 1.2;
        }
        .sese-status-chip-row {
          display: flex;
          flex-wrap: wrap;
          gap: 4px;
        }
        .sese-status-chip {
          display: inline-flex;
          align-items: center;
          box-sizing: border-box;
          max-width: 100%;
          min-height: 22px;
          border-radius: 999px;
          background: rgba(248, 187, 208, 0.26);
          color: #7c4a80;
          padding: 4px 7px;
          font-size: 11px;
          font-weight: 800;
          line-height: 1.2;
        }
        .sese-pending-mask {
          position: fixed;
          inset: 0;
          z-index: 92;
          display: flex;
          align-items: center;
          justify-content: center;
          background: rgba(136, 77, 138, 0.34);
          padding: max(env(safe-area-inset-top, 0px), 18px) 18px max(env(safe-area-inset-bottom, 0px), 18px);
          backdrop-filter: blur(6px);
        }
        .sese-pending-modal {
          display: flex;
          max-height: calc(100dvh - max(env(safe-area-inset-top, 0px), 18px) - max(env(safe-area-inset-bottom, 0px), 18px) - 24px);
          min-height: 0;
          width: min(360px, 100%);
        }
        .sese-pending-modal .sese-pending-card {
          box-sizing: border-box;
          display: flex;
          flex-direction: column;
          max-height: 100%;
          min-height: 0;
          width: 100%;
          overflow: hidden;
          border-width: 4px;
          border-radius: var(--radius-lg);
          background: rgba(255, 255, 255, 0.97);
          padding: 18px;
          box-shadow: 0 20px 40px rgba(0,0,0,0.2);
        }
        .sese-roll-row {
          display: grid;
          grid-template-columns: 70px minmax(0, 1fr) 68px;
          gap: 10px;
          align-items: center;
          margin-top: 12px;
        }
        .sese-dice {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 70px;
          height: 70px;
          border: 3px solid #ffffff;
          border-radius: 20px;
          background: #ffffff;
          color: var(--text-main);
          font-size: 42px;
          line-height: 1;
          box-shadow: 0 12px 24px rgba(136, 77, 138, 0.16);
        }
        .sese-dice.rolling {
          animation: seseDiceRoll 120ms linear infinite;
        }
        .sese-roll-button {
          min-width: 0;
          height: 54px;
          border: 0;
          border-radius: 18px;
          background: linear-gradient(135deg, #f48fb1, #ba68c8);
          color: #ffffff;
          font-size: 16px;
          font-weight: 900;
          box-shadow: 0 12px 24px rgba(186, 104, 200, 0.24);
          transition: transform 140ms ease, opacity 140ms ease;
        }
        .sese-quiet-button {
          height: 48px;
          padding: 0 10px;
          font-size: 13px;
          font-weight: 900;
        }
        .sese-log {
          display: flex;
          flex-direction: column;
          gap: 5px;
          margin-top: 12px;
          border-radius: 18px;
          background: rgba(255, 255, 255, 0.62);
          padding: 10px;
        }
        .sese-log p {
          margin: 0;
          color: #7b5a7f;
          font-size: 12px;
          font-weight: 700;
          line-height: 1.35;
        }
        .sese-popup-mask {
          position: fixed;
          inset: 0;
          z-index: 60;
          display: flex;
          align-items: center;
          justify-content: center;
          background: rgba(73, 34, 81, 0.28);
          padding: 24px;
          backdrop-filter: blur(8px);
        }
        .sese-popup {
          width: min(340px, 100%);
          border: 1px solid rgba(255, 255, 255, 0.82);
          border-radius: 28px;
          background: rgba(255, 255, 255, 0.95);
          padding: 20px;
          text-align: center;
          box-shadow: 0 22px 48px rgba(73, 34, 81, 0.24);
        }
        .sese-popup-kicker {
          display: inline-flex;
          border-radius: 999px;
          background: #f3e5f5;
          padding: 5px 10px;
          color: var(--text-light);
          font-size: 11px;
          font-weight: 900;
          line-height: 1;
        }
        .sese-popup h2 {
          margin: 12px 0 8px;
          color: var(--text-main);
          font-size: 20px;
          font-weight: 900;
          line-height: 1.2;
        }
        .sese-popup p {
          margin: 0;
          color: #7b5a7f;
          font-size: 13px;
          font-weight: 700;
          line-height: 1.55;
          text-align: left;
        }
        .sese-popup button {
          width: 100%;
          height: 44px;
          margin-top: 16px;
          border: 0;
          border-radius: 16px;
          background: linear-gradient(135deg, #f48fb1, #ba68c8);
          color: #ffffff;
          font-size: 14px;
          font-weight: 900;
        }
        @keyframes seseDiceRoll {
          0% { transform: rotate(-8deg) scale(1); }
          50% { transform: rotate(8deg) scale(1.06); }
          100% { transform: rotate(-8deg) scale(1); }
        }
        @keyframes sesePiecePop {
          from { transform: translateY(4px) scale(0.82); opacity: 0.6; }
          to { transform: translateY(0) scale(1); opacity: 1; }
        }
        @media (max-width: 380px) {
          .sese-game {
            padding-left: 10px;
            padding-right: 10px;
          }
          .sese-board {
            gap: 4px;
          }
          .sese-board-wrap {
            border-width: 5px;
            padding: 6px;
          }
          .sese-tile {
            border-radius: 11px;
          }
          .sese-piece {
            width: 21px;
            height: 15px;
          }
          .sese-roll-row {
            grid-template-columns: 62px minmax(0, 1fr) 58px;
          }
          .sese-dice {
            width: 62px;
            height: 62px;
          }
        }
        .sese-game {
          --card-white: rgba(255, 255, 255, 0.85);
          --radius-lg: 24px;
          --radius-md: 16px;
          --shadow-soft: 0 4px 12px rgba(233, 30, 99, 0.1);
          --sese-safe-top: max(calc(env(safe-area-inset-top, 0px) + 12px), 44px);
          display: flex;
          flex-direction: column;
          min-height: 100dvh;
          overflow-x: hidden;
          overflow-y: auto;
          padding: 0;
          background: var(--bg-page);
          color: var(--text-main);
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }
        .sese-header {
          position: relative;
          z-index: 10;
          display: block;
          max-width: none;
          margin: 0;
          background-color: var(--primary-pink);
          padding: var(--sese-safe-top) 16px 18px;
        }
        .sese-back {
          position: absolute;
          left: 10px;
          top: var(--sese-safe-top);
          z-index: 12;
          width: 34px;
          height: 34px;
          border: 0;
          border-radius: 50%;
          background: rgba(255,255,255,0.22);
          color: #fff;
          box-shadow: none;
        }
        .sese-chat-entry {
          position: absolute;
          right: 10px;
          top: var(--sese-safe-top);
          z-index: 12;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 34px;
          height: 34px;
          border: 0;
          border-radius: 17px;
          background: rgba(255,255,255,0.24);
          color: #fff;
          padding: 0;
          box-shadow: none;
        }
        .sese-chat-entry span {
          position: absolute;
          right: -4px;
          top: -4px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 16px;
          height: 16px;
          border-radius: 8px;
          background: #fff9c4;
          color: var(--text-main);
          font-size: 10px;
          line-height: 1;
        }
        .sese-header-title {
          margin-bottom: 8px;
          color: #fff;
          font-size: 18px;
          font-weight: 900;
          line-height: 1.15;
          text-align: center;
          text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
        }
        .sese-game-status-bar {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 5px 8px;
          border-radius: 14px;
          background: var(--card-white);
          padding: 7px 10px;
          backdrop-filter: blur(5px);
        }
        .sese-pill {
          min-height: 0;
          overflow: hidden;
          border: 0;
          border-radius: 0;
          background: transparent;
          padding: 0;
          box-shadow: none;
          font-size: 11px;
        }
        .sese-pill span {
          display: block;
          color: var(--text-light);
          font-size: 9px;
          font-weight: bold;
          line-height: 1.2;
        }
        .sese-pill strong {
          display: block;
          margin-top: 1px;
          overflow: hidden;
          color: var(--text-main);
          font-size: 11px;
          font-weight: 800;
          line-height: 1.2;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .sese-turn-indicator {
          grid-column: span 2;
          margin-top: 1px;
          border-radius: 20px;
          background: var(--accent-yellow);
          padding: 3px;
          font-size: 10px;
          font-weight: bold;
          text-align: center;
        }
        .sese-board-container {
          flex: 0 0 auto;
          display: flex;
          align-items: center;
          justify-content: center;
          overflow: visible;
          padding: 14px 12px 20px;
        }
        .sese-board {
          display: grid;
          grid-template-rows: repeat(6, 1fr);
          gap: 4px;
          width: 100%;
          max-width: 400px;
          aspect-ratio: 1 / 1;
          border-radius: var(--radius-lg);
          background: var(--card-white);
          padding: 6px;
          box-shadow: var(--shadow-soft);
          position: relative;
        }
        .sese-tile {
          position: relative;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          aspect-ratio: 1;
          overflow: hidden;
          border: 1px solid rgba(255,255,255,0.5);
          border-radius: 8px;
          background: var(--soft-lavender);
          box-shadow: none;
          transition: all 0.3s;
        }
        .sese-tile.is-active {
          z-index: 5;
          background: var(--accent-yellow) !important;
          transform: scale(1.05);
          box-shadow: 0 0 15px var(--accent-yellow);
        }
        .sese-tile-start,
        .sese-tile-theme { background: #ffecb3; font-weight: bold; }
        .sese-tile-end { background: #b2dfdb; font-weight: bold; }
        .sese-tile-task { background: #f8bbd0; }
        .sese-tile-place { background: #e1f5fe; }
        .sese-tile-pose { background: #d1c4e9; }
        .sese-tile-reset { background: #ffe0ec; }
        .sese-tile-finish-jump { background: #fff3b0; }
        .sese-tile-empty {
          border-color: rgba(255,255,255,0.45);
          background: rgba(255,255,255,0.42);
          box-shadow: inset 0 0 0 1px rgba(255,255,255,0.26);
        }
        .sese-tile-empty .sese-tile-icon {
          display: none;
        }
        .sese-tile-empty .sese-tile-name {
          color: rgba(136, 77, 138, 0.42);
          font-weight: 400;
        }
        .sese-tile-number {
          position: absolute;
          top: 2px;
          left: 3px;
          color: var(--text-main);
          font-size: 9px;
          font-weight: 400;
          line-height: 1;
          opacity: 0.6;
        }
        .sese-tile-icon {
          height: auto;
          margin-bottom: 2px;
          color: var(--text-main);
          font-size: 14px;
          font-weight: 400;
          line-height: 1;
        }
        .sese-tile-name {
          display: block;
          width: auto;
          min-height: 0;
          max-width: calc(100% - 4px);
          overflow: hidden;
          color: var(--text-main);
          font-size: 8px;
          font-weight: 400;
          line-height: 1.1;
          text-align: center;
          text-overflow: ellipsis;
          transform: scale(0.9);
          white-space: nowrap;
        }
        .sese-piece-stack {
          position: absolute;
          inset: 0;
          min-height: 0;
          pointer-events: none;
        }
        .sese-piece {
          position: absolute;
          z-index: 10;
          display: flex;
          align-items: center;
          justify-content: center;
          width: 20px;
          height: 20px;
          border: 2px solid #fff;
          border-radius: 50%;
          color: #fff;
          font-size: 10px;
          font-weight: bold;
          line-height: 1;
          box-shadow: 0 2px 4px rgba(0,0,0,0.2);
          transition: all 0.25s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }
        .sese-piece-me { left: 10%; bottom: 10%; background: #ec407a; }
        .sese-piece-ai { right: 10%; bottom: 10%; background: #7e57c2; }
        .sese-piece.paused { filter: grayscale(1); opacity: 0.7; }
        .sese-piece.paused::after {
          content: "🔒";
          position: absolute;
          top: -5px;
          right: -5px;
          font-size: 8px;
        }
        .sese-controls {
          display: flex;
          flex-direction: column;
          gap: 12px;
          padding: 0 16px calc(env(safe-area-inset-bottom, 0px) + 20px);
        }
        .sese-player-states {
          display: flex;
          gap: 10px;
        }
        .sese-final-pose-panel {
          display: grid;
          gap: 4px;
          border-radius: var(--radius-md);
          background: rgba(255, 249, 196, 0.72);
          padding: 8px 10px;
          color: var(--text-main);
        }
        .sese-final-material-row {
          display: grid;
          gap: 2px;
        }
        .sese-final-pose-panel span {
          color: var(--text-light);
          font-size: 10px;
          font-weight: 900;
          line-height: 1.2;
        }
        .sese-final-pose-panel strong {
          font-size: 11px;
          font-weight: 900;
          line-height: 1.35;
        }
        .sese-player-card {
          flex: 1;
          min-height: 80px;
          border-radius: var(--radius-md);
          background: var(--card-white);
          padding: 8px;
          font-size: 11px;
          box-shadow: none;
        }
        .sese-player-card.active { border: 2px solid var(--primary-pink); }
        .sese-player-card-head {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 6px;
          margin: 0 0 4px;
        }
        .sese-player-card h2 {
          margin: 0;
          color: var(--text-main);
          font-size: 11px;
          font-weight: 900;
          line-height: 1.2;
        }
        .sese-status-list {
          display: grid;
          gap: 4px;
        }
        .sese-status-empty {
          display: inline-block;
          margin: 2px;
          border: 1px solid rgba(0,0,0,0.05);
          border-radius: 4px;
          background: var(--soft-lavender);
          padding: 2px 6px;
          color: var(--text-main);
          font-size: 9px;
          font-weight: 400;
          line-height: 1.2;
        }
        .sese-status-group {
          display: grid;
          gap: 3px;
        }
        .sese-status-group-label {
          color: var(--text-light);
          font-size: 9px;
          font-weight: 700;
          line-height: 1.2;
        }
        .sese-status-chip-row {
          display: flex;
          flex-wrap: wrap;
          gap: 3px;
        }
        .sese-status-chip {
          display: inline-flex;
          align-items: center;
          box-sizing: border-box;
          max-width: 100%;
          border: 1px solid rgba(0,0,0,0.05);
          border-radius: 999px;
          background: var(--soft-lavender);
          color: var(--text-main);
          padding: 2px 6px;
          font-size: 9px;
          font-weight: 400;
          line-height: 1.2;
        }
        .sese-pending-card {
          border: 2px solid rgba(248, 187, 208, 0.9);
          border-radius: var(--radius-md);
          background: rgba(255, 255, 255, 0.9);
          padding: 10px;
          box-shadow: var(--shadow-soft);
        }
        .sese-pending-head {
          flex: 0 0 auto;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
          margin-bottom: 6px;
        }
        .sese-pending-head span {
          flex: 0 0 auto;
          border-radius: 999px;
          background: var(--accent-yellow);
          padding: 3px 7px;
          color: var(--text-main);
          font-size: 9px;
          font-weight: 900;
          line-height: 1;
        }
        .sese-pending-head strong {
          min-width: 0;
          overflow: hidden;
          color: var(--text-main);
          font-size: 13px;
          font-weight: 900;
          line-height: 1.2;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .sese-pending-card p,
        .sese-pending-tip,
        .sese-pending-wait {
          margin: 0;
          color: #7c4a80;
          font-size: 11px;
          font-weight: 700;
          line-height: 1.45;
        }
        .sese-pending-card > p,
        .sese-pending-card > .sese-review-feedback,
        .sese-pending-card > .sese-pending-tip,
        .sese-pending-card > .sese-pending-wait {
          flex: 0 1 auto;
          min-height: 0;
          max-height: min(32dvh, 240px);
          overflow-y: auto;
          overscroll-behavior: contain;
          -webkit-overflow-scrolling: touch;
        }
        .sese-pending-tip,
        .sese-pending-wait {
          margin-top: 6px;
          border-radius: 10px;
          background: var(--soft-lavender);
          padding: 6px 8px;
        }
        .sese-submission-text {
          max-height: min(36dvh, 260px);
          overflow-y: auto;
          overscroll-behavior: contain;
          -webkit-overflow-scrolling: touch;
          min-height: 44px;
          white-space: pre-wrap;
          word-break: break-word;
        }
        .sese-pending-card textarea {
          flex: 0 0 auto;
          display: block;
          width: 100%;
          min-height: 82px;
          max-height: min(24dvh, 150px);
          margin-top: 8px;
          resize: vertical;
          border: 1px solid rgba(186, 104, 200, 0.24);
          border-radius: 12px;
          background: #fff;
          color: var(--text-main);
          padding: 8px 10px;
          font-size: 12px;
          line-height: 1.45;
          outline: none;
        }
        .sese-review-feedback {
          margin-top: 8px;
          border: 1px solid rgba(186, 104, 200, 0.24);
          border-radius: 12px;
          background: #fff;
          color: var(--text-main);
          padding: 8px 10px;
          font-size: 12px;
          font-weight: 800;
          line-height: 1.45;
          white-space: pre-wrap;
          word-break: break-word;
        }
        .sese-choice-list {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 8px;
          margin-top: 9px;
        }
        .sese-review-actions {
          flex: 0 0 auto;
          display: flex;
          flex-wrap: wrap;
          justify-content: center;
          gap: 8px;
          margin-top: 9px;
        }
        .sese-choice-list button,
        .sese-review-actions button,
        .sese-pass-button {
          min-height: 36px;
          border: 0;
          border-radius: 14px;
          background: var(--primary-pink);
          color: #fff;
          padding: 7px 9px;
          font-size: 11px;
          font-weight: 900;
          line-height: 1.25;
          box-shadow: 0 3px 0 #d81b60;
        }
        .sese-review-actions button {
          flex: 1 1 112px;
          max-width: 180px;
        }
        .sese-choice-list button:disabled,
        .sese-review-actions button:disabled,
        .sese-pass-button:disabled {
          opacity: 0.5;
        }
        .sese-rps-list {
          grid-template-columns: repeat(3, minmax(0, 1fr));
        }
        .sese-choice-list .sese-rps-button {
          min-height: 54px;
          border-radius: 18px;
          background: #ffffff;
          color: var(--text-main);
          font-size: 26px;
          line-height: 1;
          box-shadow: inset 0 0 0 2px rgba(248, 187, 208, 0.82), 0 4px 0 #f48fb1;
        }
        .sese-choice-list .sese-rps-button.is-selected {
          background: var(--primary-pink);
          color: #ffffff;
          box-shadow: inset 0 0 0 2px #ffffff, 0 4px 0 #d81b60;
          transform: translateY(1px);
        }
        .sese-choice-list .sese-rps-button.is-selected:disabled {
          opacity: 1;
        }
        .sese-pass-button {
          width: 100%;
          margin-top: 8px;
          background: #ba68c8;
          box-shadow: 0 3px 0 #8e24aa;
        }
        .sese-action-area {
          display: flex;
          align-items: center;
          gap: 16px;
          border-radius: 40px;
          background: var(--card-white);
          padding: 12px;
        }
        .sese-dice {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 50px;
          height: 50px;
          border: 0;
          border-radius: 12px;
          background: white;
          color: var(--text-main);
          font-size: 24px;
          font-weight: 900;
          line-height: 1;
          box-shadow: inset 0 -4px 0 rgba(0,0,0,0.1), 0 4px 8px rgba(0,0,0,0.1);
        }
        .sese-dice.rolling { animation: seseDiceRoll 0.1s infinite; }
        .sese-roll-button {
          flex: 1;
          height: 50px;
          border: none;
          border-radius: 25px;
          background: var(--primary-pink);
          color: white;
          font-size: 18px;
          font-weight: 900;
          box-shadow: 0 4px 0 #d81b60;
          transition: all 0.1s;
        }
        .sese-roll-button:active {
          transform: translateY(2px);
          box-shadow: 0 2px 0 #d81b60;
        }
        .sese-roll-button:disabled {
          background: #ce93d8;
          box-shadow: 0 4px 0 #ab47bc;
          opacity: 0.7;
        }
        .sese-restart-button {
          flex: 0 0 46px;
          height: 42px;
          border: 0;
          border-radius: 21px;
          background: #fff;
          color: var(--text-main);
          font-size: 12px;
          font-weight: 900;
          box-shadow: 0 3px 0 rgba(136, 77, 138, 0.18);
        }
        .sese-restart-button:disabled {
          opacity: 0.5;
        }
        .sese-theme-mask {
          position: fixed;
          inset: 0;
          z-index: 105;
          display: flex;
          align-items: center;
          justify-content: center;
          background: rgba(136, 77, 138, 0.42);
          padding: max(env(safe-area-inset-top, 0px), 18px) 18px max(env(safe-area-inset-bottom, 0px), 18px);
          backdrop-filter: blur(6px);
        }
        .sese-theme-modal {
          position: relative;
          width: min(380px, calc(100vw - 54px));
          border: 5px solid #ffffff;
          border-radius: 32px 32px 26px 26px;
          background: #e975a5;
          padding: 13px 16px 18px;
          text-align: center;
          box-shadow:
            0 24px 50px rgba(73, 34, 81, 0.32),
            inset 0 2px 0 rgba(255,255,255,0.74),
            inset 0 -7px 0 rgba(174, 42, 100, 0.28);
        }
        .sese-slot-lights {
          display: flex;
          justify-content: center;
          gap: 7px;
          margin-bottom: 8px;
        }
        .sese-slot-lights i {
          width: 11px;
          height: 11px;
          border: 2px solid rgba(255,255,255,0.86);
          border-radius: 50%;
          background: #fff7a8;
          box-shadow: 0 0 12px rgba(255, 247, 168, 0.88);
          animation: seseSlotLight 900ms ease-in-out infinite alternate;
        }
        .sese-slot-lights i:nth-child(2),
        .sese-slot-lights i:nth-child(4) {
          background: #ffffff;
          animation-delay: 180ms;
        }
        .sese-slot-marquee {
          display: grid;
          grid-template-columns: 1fr;
          gap: 2px;
          margin-bottom: 10px;
          border: 3px solid #7b3c78;
          border-radius: 18px;
          background: #fff2ac;
          padding: 7px 12px;
          box-shadow: inset 0 -4px 0 rgba(123,60,120,0.16), 0 5px 0 rgba(123,60,120,0.22);
        }
        .sese-slot-marquee span,
        .sese-slot-marquee strong {
          color: #7b3c78;
          line-height: 1;
          letter-spacing: 0;
        }
        .sese-slot-marquee span {
          font-size: 10px;
          font-weight: 900;
        }
        .sese-slot-marquee strong {
          font-size: 20px;
          font-weight: 900;
        }
        .sese-slot-face {
          position: relative;
          border: 4px solid rgba(255,255,255,0.88);
          border-radius: 24px;
          background: #fff4fa;
          padding: 13px;
          box-shadow:
            inset 0 0 0 2px rgba(216, 95, 146, 0.16),
            0 8px 0 rgba(157, 47, 103, 0.25);
        }
        .sese-reel-bank {
          display: grid;
          grid-template-columns: 58px minmax(0, 1fr) 58px;
          gap: 7px;
          border: 4px solid #7b3c78;
          border-radius: 20px;
          background: #7b3c78;
          padding: 7px;
          box-shadow: inset 0 0 0 2px rgba(255,255,255,0.22);
        }
        .sese-theme-window {
          position: relative;
          height: 70px;
          margin: 0;
          overflow: hidden;
          border: 3px solid #fff;
          border-radius: 14px;
          background: #fff;
          box-shadow:
            inset 0 8px 12px rgba(74, 34, 78, 0.12),
            inset 0 -8px 12px rgba(74, 34, 78, 0.1);
        }
        .sese-theme-window-main {
          border-width: 4px;
        }
        .sese-theme-window-side {
          background: #fff7c8;
        }
        .sese-theme-window::before,
        .sese-theme-window::after {
          content: "";
          position: absolute;
          left: 0;
          right: 0;
          z-index: 2;
          height: 16px;
          pointer-events: none;
        }
        .sese-theme-window::before {
          top: 0;
          border-top: 5px solid rgba(123,60,120,0.18);
        }
        .sese-theme-window::after {
          bottom: 0;
          border-bottom: 5px solid rgba(123,60,120,0.16);
        }
        .sese-theme-strip {
          animation: seseThemeSpin 1200ms cubic-bezier(0.16, 1, 0.3, 1) both;
        }
        .sese-theme-item {
          display: flex;
          align-items: center;
          justify-content: center;
          height: 70px;
          color: var(--text-main);
          font-size: 18px;
          font-weight: 900;
          line-height: 1;
          text-align: center;
          word-break: keep-all;
          padding: 0 8px;
        }
        .sese-theme-window-side .sese-theme-item {
          color: #9b3f78;
          font-size: 12px;
          padding: 0 3px;
        }
        .sese-slot-plaque {
          margin: 12px 0 10px;
          border-radius: 14px;
          background: #f3e5f5;
          color: #7c4a80;
          padding: 8px 10px;
          font-size: 13px;
          font-weight: 900;
        }
        .sese-theme-actions {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 8px;
        }
        .sese-theme-modal button {
          min-width: 0;
          min-height: 38px;
          border: 0;
          border-radius: 16px;
          background: #ff6f9f;
          color: #fff;
          padding: 8px 12px;
          font-size: 12px;
          font-weight: 900;
          box-shadow: 0 4px 0 #bd3367;
        }
        .sese-theme-modal button.secondary {
          background: #ffffff;
          color: #7b3c78;
          box-shadow: 0 4px 0 rgba(123,60,120,0.22);
        }
        .sese-theme-modal button:disabled {
          opacity: 0.52;
          box-shadow: none;
        }
        .sese-slot-tray {
          width: 70px;
          height: 11px;
          margin: 13px auto 0;
          border-radius: 999px;
          background: #7b3c78;
          box-shadow: inset 0 3px 0 rgba(0,0,0,0.18), 0 2px 0 rgba(255,255,255,0.54);
        }
        .sese-history {
          padding: 0 10px;
          color: var(--text-light);
          font-size: 10px;
          text-align: center;
        }
        .sese-chat-mask {
          position: fixed;
          inset: 0;
          z-index: 110;
          display: flex;
          align-items: flex-start;
          justify-content: flex-end;
          background: rgba(136, 77, 138, 0.18);
          padding: calc(var(--sese-safe-top) + 42px) 14px 14px;
          backdrop-filter: blur(2px);
        }
        .sese-chat-panel {
          display: flex;
          flex-direction: column;
          width: min(360px, calc(100vw - 28px));
          max-height: min(70dvh, 560px);
          overflow: hidden;
          border: 2px solid rgba(248, 187, 208, 0.9);
          border-radius: 18px;
          background: #fff6fb;
          box-shadow: 0 18px 42px rgba(136, 77, 138, 0.22);
        }
        .sese-chat-head {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
          border-bottom: 1px solid rgba(186, 104, 200, 0.16);
          background: #f8bbd0;
          padding: 9px 10px;
          color: #fff;
        }
        .sese-chat-head strong,
        .sese-chat-head span {
          display: block;
          line-height: 1.2;
        }
        .sese-chat-head strong {
          font-size: 13px;
          font-weight: 900;
        }
        .sese-chat-head span {
          margin-top: 2px;
          font-size: 10px;
          font-weight: 700;
          opacity: 0.9;
        }
        .sese-chat-head button {
          flex: 0 0 28px;
          width: 28px;
          height: 28px;
          border: 0;
          border-radius: 50%;
          background: rgba(255,255,255,0.24);
          color: #fff;
          font-size: 20px;
          font-weight: 700;
          line-height: 1;
        }
        .sese-chat-list {
          display: flex;
          flex: 1;
          min-height: 180px;
          flex-direction: column;
          gap: 8px;
          overflow-y: auto;
          padding: 10px;
        }
        .sese-chat-message {
          max-width: 86%;
          border-radius: 12px;
          padding: 7px 9px;
          color: var(--text-main);
          font-size: 12px;
          line-height: 1.45;
        }
        .sese-chat-message span {
          display: block;
          margin-bottom: 2px;
          font-size: 9px;
          font-weight: 900;
          opacity: 0.72;
        }
        .sese-chat-message p {
          margin: 0;
          white-space: pre-wrap;
          word-break: break-word;
        }
        .sese-chat-message.player {
          align-self: flex-end;
          background: #ffe0ec;
        }
        .sese-chat-message.ai {
          align-self: flex-start;
          background: #efe7f6;
        }
        .sese-chat-message.system {
          align-self: center;
          max-width: 100%;
          background: #fff9c4;
          color: #8a6d3b;
          font-size: 10px;
          text-align: center;
        }
        .sese-chat-message.pending {
          opacity: 0.72;
        }
        .sese-chat-form {
          display: flex;
          gap: 6px;
          border-top: 1px solid rgba(186, 104, 200, 0.16);
          background: rgba(255,255,255,0.74);
          padding: 8px;
        }
        .sese-chat-form input {
          flex: 1;
          min-width: 0;
          height: 36px;
          border: 1px solid rgba(186, 104, 200, 0.22);
          border-radius: 18px;
          background: #fff;
          color: var(--text-main);
          padding: 0 12px;
          font-size: 12px;
          outline: none;
        }
        .sese-chat-form input:disabled {
          opacity: 0.6;
        }
        .sese-chat-form button {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          flex: 0 0 44px;
          width: 44px;
          height: 36px;
          border: 0;
          border-radius: 18px;
          background: #f06292;
          color: #fff;
          font-size: 13px;
          font-weight: 900;
          box-shadow: 0 3px 0 #d81b60;
        }
        .sese-chat-form button svg {
          color: currentColor;
        }
        .sese-chat-form button:disabled {
          opacity: 0.5;
        }
        .sese-final-note-mask {
          position: fixed;
          inset: 0;
          z-index: 110;
          display: flex;
          align-items: center;
          justify-content: center;
          background: rgba(136, 77, 138, 0.34);
          padding: 18px;
          backdrop-filter: blur(4px);
        }
        .sese-final-note-modal {
          width: min(430px, 100%);
          border: 4px solid var(--primary-pink);
          border-radius: var(--radius-lg);
          background: rgba(255, 255, 255, 0.96);
          padding: 22px;
          box-shadow: 0 18px 36px rgba(136, 77, 138, 0.22);
        }
        .sese-final-note-head {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
        }
        .sese-final-note-head span {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          height: 24px;
          padding: 0 12px;
          border-radius: 999px;
          background: #fff9c4;
          color: var(--text-main);
          font-size: 11px;
          font-weight: 900;
        }
        .sese-final-note-head button {
          height: 28px;
          border: 0;
          border-radius: 14px;
          background: rgba(240, 98, 146, 0.12);
          color: var(--text-light);
          padding: 0 10px;
          font-size: 12px;
          font-weight: 900;
        }
        .sese-final-note-modal h2 {
          margin: 12px 0 10px;
          color: var(--text-main);
          font-size: 22px;
          line-height: 1.18;
          text-align: center;
        }
        .sese-final-note-body {
          display: grid;
          gap: 10px;
          margin-top: 12px;
        }
        .sese-final-note-intro,
        .sese-final-note-closing {
          border-radius: 16px;
          background: #fff7fb;
          color: #875183;
          padding: 10px 12px;
          font-size: 13px;
          font-weight: 900;
          line-height: 1.55;
        }
        .sese-final-note-section {
          display: grid;
          gap: 9px;
          border: 1px solid #f3c6dd;
          border-radius: 18px;
          background: #fff;
          padding: 11px 12px;
        }
        .sese-final-note-section > span {
          color: #b45a91;
          font-size: 11px;
          font-weight: 900;
          line-height: 1.2;
        }
        .sese-final-note-section-title {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
        }
        .sese-final-note-section-title > span {
          color: #b45a91;
          font-size: 11px;
          font-weight: 900;
          line-height: 1.2;
        }
        .sese-final-note-section-title > button {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          flex: 0 0 auto;
          width: 26px;
          height: 26px;
          border: 0;
          border-radius: 50%;
          background: #f8a9c6;
          color: #fff;
          box-shadow: 0 3px 0 #d81b60;
        }
        .sese-final-note-section-title > button svg {
          width: 15px;
          height: 15px;
          fill: none;
          stroke: currentColor;
          stroke-width: 3;
          stroke-linecap: round;
        }
        .sese-final-note-section-title > button:active {
          transform: translateY(1px);
          box-shadow: 0 2px 0 #d81b60;
        }
        .sese-final-note-section > strong {
          color: var(--text-main);
          font-size: 14px;
          line-height: 1.35;
        }
        .sese-final-note-status-group {
          display: grid;
          gap: 7px;
        }
        .sese-final-note-status-group > b {
          justify-self: start;
          border-radius: 999px;
          background: #fff1f7;
          color: #8d4a86;
          padding: 4px 9px;
          font-size: 11px;
          line-height: 1.2;
        }
        .sese-final-note-status-values {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }
        .sese-final-note-status-values span {
          display: inline-flex;
          align-items: center;
          box-sizing: border-box;
          max-width: 100%;
          border-radius: 999px;
          background: #f8edf6;
          color: #795078;
          padding: 6px 10px;
          font-size: 12px;
          line-height: 1.25;
          word-break: break-word;
        }
        .sese-final-note-empty {
          color: #9b7598;
          font-size: 12px;
          line-height: 1.45;
        }
        .sese-final-note-closing {
          text-align: center;
          background: #fff9c4;
        }
        .sese-toy-console-mask {
          position: fixed;
          inset: 0;
          z-index: 125;
          display: flex;
          align-items: flex-end;
          justify-content: center;
          background: rgba(74, 37, 70, 0.28);
          padding: 14px;
          backdrop-filter: blur(4px);
        }
        .sese-toy-console-sheet {
          width: min(460px, 100%);
          max-height: min(78vh, 620px);
          overflow: auto;
          border: 3px solid #f4a9c5;
          border-radius: 28px 28px 20px 20px;
          background: #fffafc;
          padding: 18px;
          box-shadow: 0 18px 42px rgba(112, 63, 105, 0.24);
        }
        .sese-toy-console-head {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 14px;
        }
        .sese-toy-console-head div {
          display: grid;
          gap: 5px;
        }
        .sese-toy-console-head span {
          color: var(--text-main);
          font-size: 20px;
          font-weight: 900;
          line-height: 1.2;
        }
        .sese-toy-console-head strong {
          color: #9b6b97;
          font-size: 12px;
          font-weight: 900;
          line-height: 1.35;
        }
        .sese-toy-console-head button {
          flex: 0 0 auto;
          height: 30px;
          border: 0;
          border-radius: 15px;
          background: #fce5ef;
          color: var(--text-light);
          padding: 0 11px;
          font-size: 12px;
          font-weight: 900;
        }
        .sese-toy-console-section {
          display: grid;
          gap: 9px;
          margin-top: 14px;
        }
        .sese-toy-console-section label {
          color: #8d4a86;
          font-size: 12px;
          font-weight: 900;
          line-height: 1.2;
        }
        .sese-toy-level-row,
        .sese-toy-chip-grid {
          display: grid;
          gap: 8px;
        }
        .sese-toy-level-row {
          grid-template-columns: repeat(5, minmax(0, 1fr));
        }
        .sese-toy-chip-grid {
          grid-template-columns: repeat(3, minmax(0, 1fr));
        }
        .sese-toy-level-row button,
        .sese-toy-chip-grid button {
          min-height: 38px;
          border: 2px solid #f1c2d6;
          border-radius: 14px;
          background: #fff;
          color: var(--text-main);
          padding: 7px 9px;
          font-size: 12px;
          font-weight: 900;
          line-height: 1.25;
          box-shadow: 0 3px 0 rgba(216, 27, 96, 0.18);
        }
        .sese-toy-level-row button.selected,
        .sese-toy-chip-grid button.selected {
          border-color: #e91e63;
          background: #f8a9c6;
          color: #fff;
          box-shadow: 0 3px 0 #d81b60;
        }
        .sese-toy-level-row button:disabled,
        .sese-toy-chip-grid button:disabled {
          opacity: 0.58;
        }
        .sese-final-note-modal em {
          display: block;
          margin-top: 18px;
          color: var(--text-light);
          font-size: 13px;
          font-style: normal;
          font-weight: 900;
          text-align: center;
        }
        .sese-final-note-send {
          width: 100%;
          height: 46px;
          margin-top: 18px;
          border: 0;
          border-radius: 23px;
          background: #f06292;
          color: #fff;
          font-size: 15px;
          font-weight: 900;
          box-shadow: 0 4px 0 #d81b60;
        }
        .sese-final-note-send:disabled {
          opacity: 0.58;
        }
        .sese-popup-mask {
          position: fixed;
          inset: 0;
          z-index: 100;
          display: flex;
          align-items: center;
          justify-content: center;
          background: rgba(136, 77, 138, 0.4);
          padding: 0;
          backdrop-filter: blur(4px);
        }
        .sese-popup {
          width: 80%;
          border: 4px solid var(--primary-pink);
          border-radius: var(--radius-lg);
          background: white;
          padding: 24px;
          text-align: center;
          box-shadow: 0 20px 40px rgba(0,0,0,0.2);
        }
        .sese-popup-draw {
          overflow: hidden;
        }
        .sese-popup-kicker {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          margin: 0 auto 10px;
          border-radius: 999px;
          background: var(--accent-yellow);
          padding: 5px 12px;
          color: var(--text-main);
          font-size: 12px;
          font-weight: 900;
          line-height: 1.2;
        }
        .sese-draw-card {
          margin: 0 auto 14px;
          border-radius: 18px;
          background: var(--soft-lavender);
          padding: 16px 12px;
          box-shadow: inset 0 0 0 2px rgba(248, 187, 208, 0.8);
          animation: seseDrawCard 420ms cubic-bezier(0.16, 1, 0.3, 1) both;
        }
        .sese-draw-card.is-covered {
          min-height: 118px;
          border: 3px solid #ffffff;
          background: #e975a5;
          box-shadow:
            inset 0 0 0 3px rgba(123,60,120,0.18),
            inset 0 -6px 0 rgba(123,60,120,0.18),
            0 8px 0 rgba(123,60,120,0.22);
          animation: seseDrawCard 360ms cubic-bezier(0.16, 1, 0.3, 1) both, seseCardPulse 740ms ease-in-out infinite alternate;
        }
        .sese-card-pile {
          position: relative;
          width: 132px;
          height: 94px;
          margin: 2px auto 12px;
        }
        .sese-card-pile i,
        .sese-card-pile b {
          position: absolute;
          display: block;
          width: 62px;
          height: 82px;
          border: 3px solid #ffffff;
          border-radius: 12px;
          background: #fff2ac;
          box-shadow: 0 5px 0 rgba(123,60,120,0.16), inset 0 -5px 0 rgba(123,60,120,0.1);
        }
        .sese-card-pile i:nth-child(1) {
          left: 13px;
          top: 9px;
          transform: rotate(-9deg);
          background: #f3e5f5;
        }
        .sese-card-pile i:nth-child(2) {
          left: 18px;
          top: 6px;
          transform: rotate(-4deg);
          background: #fff2ac;
        }
        .sese-card-pile i:nth-child(3) {
          left: 23px;
          top: 3px;
          transform: rotate(3deg);
          background: #ffe0ec;
        }
        .sese-card-pile i:nth-child(4) {
          left: 28px;
          top: 0;
          transform: rotate(7deg);
          background: #ffffff;
        }
        .sese-card-pile b {
          left: 52px;
          top: 3px;
          z-index: 2;
          background: #fff7c8;
          animation: seseCardDrawOut 900ms cubic-bezier(0.16, 1, 0.3, 1) both;
        }
        .sese-draw-card span {
          display: block;
          color: var(--text-light);
          font-size: 11px;
          font-weight: 900;
          line-height: 1;
        }
        .sese-draw-card strong {
          display: block;
          margin-top: 8px;
          color: var(--text-main);
          font-size: 20px;
          font-weight: 900;
          line-height: 1.2;
        }
        .sese-draw-card em {
          display: block;
          margin-top: 8px;
          color: #fff;
          font-size: 12px;
          font-style: normal;
          font-weight: 900;
        }
        .sese-draw-card.is-covered span,
        .sese-draw-card.is-covered strong {
          color: #fff;
        }
        .sese-draw-card.is-covered strong {
          margin-top: 0;
          font-size: 28px;
        }
        .sese-popup-draw.tone-reward .sese-draw-card {
          background: var(--accent-yellow);
        }
        .sese-popup-draw.tone-reward .sese-draw-card.is-covered {
          background: #e975a5;
        }
        .sese-popup-draw.tone-choice .sese-draw-card {
          background: #f8bbd0;
        }
        .sese-popup h2 {
          margin: 0 0 12px;
          color: var(--text-main);
          font-size: 20px;
          font-weight: 900;
          line-height: 1.2;
        }
        .sese-popup p {
          margin: 0 0 20px;
          color: #666;
          font-size: 14px;
          font-weight: 400;
          line-height: 1.6;
          text-align: center;
        }
        .sese-popup button {
          width: auto;
          height: auto;
          margin: 0;
          border: none;
          border-radius: 20px;
          background: var(--primary-pink);
          color: white;
          padding: 12px 30px;
          font-size: 14px;
          font-weight: bold;
          box-shadow: none;
        }
        @keyframes seseDiceRoll {
          0% { transform: rotate(0deg) scale(1); }
          50% { transform: rotate(10deg) scale(1.1); }
          100% { transform: rotate(-10deg) scale(1); }
        }
        @keyframes seseThemeSpin {
          from { transform: translateY(0); }
          to { transform: translateY(-490px); }
        }
        @keyframes seseSlotLight {
          from { opacity: 0.58; transform: scale(0.86); }
          to { opacity: 1; transform: scale(1); }
        }
        @keyframes seseDrawCard {
          from { transform: translateY(18px) scale(0.94); opacity: 0; }
          to { transform: translateY(0) scale(1); opacity: 1; }
        }
        @keyframes seseCardPulse {
          from { transform: translateY(0) rotate(-1deg); }
          to { transform: translateY(-3px) rotate(1deg); }
        }
        @keyframes seseCardDrawOut {
          0% { transform: translateX(-18px) rotate(7deg) scale(0.96); opacity: 0.86; }
          58% { transform: translateX(28px) translateY(-10px) rotate(13deg) scale(1); opacity: 1; }
          100% { transform: translateX(36px) translateY(-14px) rotate(10deg) scale(1.04); opacity: 1; }
        }
        `}
      </style>
    </div>
  );
}

function StatusPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="sese-pill">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function PlayerStateCard({
  actor,
  statuses,
  active,
}: {
  actor: Actor;
  statuses: StatusItem[];
  active: boolean;
}) {
  const shown = groupStatusItems(statuses);
  return (
    <div className={`sese-player-card sese-player-card-${actor} ${active ? "active" : ""}`}>
      <div className="sese-player-card-head">
        <h2>{actor === "player" ? "你的状态" : "对方的状态"}</h2>
      </div>
      <div className="sese-status-list">
        {shown.length ? shown.map((item) => {
          return (
            <div className="sese-status-group" key={item.label}>
              <span className="sese-status-group-label">{item.label}</span>
              <div className="sese-status-chip-row">
                {item.values.map((value) => (
                  <span className="sese-status-chip" key={`${item.label}-${value}`}>
                    {value}
                  </span>
                ))}
              </div>
            </div>
          );
        }) : <div className="sese-status-empty">无状态</div>}
      </div>
    </div>
  );
}

function ToyConsoleSheet({
  level,
  activeProps,
  disabled,
  onClose,
  onLevelChange,
  onToggleProp,
}: {
  level: number;
  activeProps: string[];
  disabled: boolean;
  onClose: () => void;
  onLevelChange: (level: number) => void;
  onToggleProp: (value: string, active: boolean) => void;
}) {
  const activePropSet = new Set(activeProps);
  return (
    <div className="sese-toy-console-mask" role="dialog" aria-modal="true" aria-label="玩具控制台" onClick={onClose}>
      <div className="sese-toy-console-sheet" onClick={(event) => event.stopPropagation()}>
        <div className="sese-toy-console-head">
          <div>
            <span>玩具控制台</span>
            <strong>控制对方当前状态</strong>
          </div>
          <button type="button" onClick={onClose} aria-label="关闭玩具控制台">关闭</button>
        </div>

        <div className="sese-toy-console-section">
          <label>道具档位</label>
          <div className="sese-toy-level-row">
            {[1, 2, 3, 4, 5].map((item) => (
              <button
                key={item}
                type="button"
                disabled={disabled}
                className={item === level ? "selected" : ""}
                onClick={() => onLevelChange(item)}
              >
                {item}
              </button>
            ))}
          </div>
        </div>

        <div className="sese-toy-console-section">
          <label>启用道具</label>
          <div className="sese-toy-chip-grid">
            {FINAL_TOY_PROP_OPTIONS.map((item) => (
              (() => {
                const active = activePropSet.has(item);
                return (
                  <button
                    key={item}
                    type="button"
                    disabled={disabled}
                    className={active ? "selected" : ""}
                    aria-pressed={active}
                    aria-label={active ? `取消启用${item}` : `启用${item}`}
                    onClick={() => onToggleProp(item, active)}
                  >
                    {item}
                  </button>
                );
              })()
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function FinalNoteContent({
  note,
  canAddStatus = false,
  onAddStatus,
}: {
  note: FinalNote;
  canAddStatus?: boolean;
  onAddStatus?: () => void;
}) {
  const intro = finalNoteIntro(note);
  const theme = displayText(note.theme || "本局主题");
  const targetLabel = note.target === "ai" ? "对方当前状态" : "你的当前状态";
  const statusGroups = finalNoteStatusGroups(note.target_status || "");
  const finalMaterials = finalMaterialItemsFrom([], note);
  return (
    <div className="sese-final-note-body">
      <div className="sese-final-note-intro">{intro}</div>
      <div className="sese-final-note-section">
        <span>本局主题</span>
        <strong>{theme}</strong>
      </div>
      <div className="sese-final-note-section">
        <div className="sese-final-note-section-title">
          <span>{targetLabel}</span>
          {canAddStatus ? (
            <button type="button" onClick={onAddStatus} aria-label="打开玩具控制台">
              <PlusIcon />
            </button>
          ) : null}
        </div>
        {statusGroups.length ? (
          statusGroups.map((group) => (
            <div className="sese-final-note-status-group" key={group.label}>
              <b>{group.label}</b>
              <div className="sese-final-note-status-values">
                {group.values.map((value) => <span key={value}>{value}</span>)}
              </div>
            </div>
          ))
        ) : (
          <div className="sese-final-note-empty">没有遗留状态，可以自由决定最后玩法。</div>
        )}
      </div>
      {finalMaterials.map((item) => (
        <div className="sese-final-note-section" key={item.label}>
          <span>{item.label}</span>
          <strong>{item.values.join("、")}</strong>
        </div>
      ))}
      <div className="sese-final-note-closing">请尽情享受你们的ooxx吧！</div>
    </div>
  );
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

function finalNoteIntro(note: FinalNote): string {
  const lines = displaySystemText(note.text || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const line = lines.find((item) => {
    return !item.startsWith("【") && !item.startsWith("请根据") && !item.startsWith("本局主题") && !item.startsWith("请尽情");
  });
  return line || "终点已到达，赢家状态已清空。";
}

function finalNoteStatusGroups(summary: string): { label: string; values: string[] }[] {
  const cleaned = displaySystemText(summary).trim();
  if (!cleaned || cleaned === "无") return [];
  return cleaned
    .split("；")
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      const index = part.indexOf("：");
      if (index < 0) return { label: "状态", values: [part] };
      const label = part.slice(0, index).trim() || "状态";
      const values = part
        .slice(index + 1)
        .split("、")
        .map((value) => value.trim())
        .filter(Boolean);
      return { label, values: values.length ? values : ["无"] };
    });
}

function PendingEventPanel({
  pending,
  reviewFeedback,
  passCount,
  passSkipsUsed,
  submission,
  disabled,
  onSubmissionChange,
  onSubmit,
  onApprove,
  onReject,
  onChoose,
  onPass,
}: {
  pending: PendingEvent;
  reviewFeedback: ReviewFeedback | null;
  passCount: number;
  passSkipsUsed: number;
  submission: string;
  disabled: boolean;
  onSubmissionChange: (value: string) => void;
  onSubmit: () => void;
  onApprove: () => void;
  onReject: () => void;
  onChoose: (choiceId: string) => void;
  onPass: () => void;
}) {
  const name = displaySystemText(pending.name || "惩罚任务");
  const actor = pending.actor || "player";
  const reviewer = pending.reviewer || (actor === "player" ? "ai" : "player");
  const currentActor = pending.current_actor || actor;
  const isMine = actor === "player";
  const isMyTurn = currentActor === "player";
  const isMyReview = reviewer === "player";
  const hasQuestionText = Boolean(displayText(pending.question_text || "").trim());
  const lastRejectReason = displayText(pending.last_reject_reason || "").trim();
  const canPass = isMine && pending.pass_allowed !== false && passCount > 0 && passSkipsUsed < 1 && !["submitted", "questioning"].includes(String(pending.phase || ""));
  const rawSubmissionHint = displaySystemText(pending.submission || "").trim();
  const submissionHint = /^你的回答[。.]?$/.test(rawSubmissionHint) ? "" : rawSubmissionHint;
  const [selectedRps, setSelectedRps] = useState("");
  useEffect(() => {
    setSelectedRps("");
  }, [pending.id, pending.current_actor, pending.phase]);
  const activeRpsPick = normalizeRpsChoice(selectedRps || pending.picks?.player);
  const hasPlayerRpsPick = Boolean(normalizeRpsChoice(pending.picks?.player));
  if (pending.type === "choice") {
    return (
      <div className="sese-pending-card">
        <div className="sese-pending-head">
          <span>{isMine ? "你的选择惩罚" : "等待对方选择"}</span>
          <strong>{name}</strong>
        </div>
        <p>{displaySystemText(pending.prompt || "选择一项惩罚。")}</p>
        {isMine ? (
          <div className="sese-choice-list">
            {(pending.choices || []).map((choice) => {
              const id = String(choice.id || choice.label || "");
              return (
                <button key={id} type="button" disabled={disabled || !id} onClick={() => onChoose(id)}>
                  {displaySystemText(choice.label || id)}
                </button>
              );
            })}
          </div>
        ) : (
          <div className="sese-pending-wait">
            等待对方选择惩罚。
          </div>
        )}
        {canPass ? <button className="sese-pass-button" type="button" disabled={disabled} onClick={onPass}>使用Pass卡跳过</button> : null}
      </div>
    );
  }

  if (pending.type === "duel") {
    return (
      <div className="sese-pending-card">
        <div className="sese-pending-head">
          <span>{isMyTurn ? "轮到你出拳" : "等待对方出拳"}</span>
          <strong>{name || "剪刀石头布对抗"}</strong>
        </div>
        <p>同格触发对抗。双方各出石头、剪刀或布，系统判定胜负；赢的前进 3 格，输的后退 3 格。</p>
        <div className="sese-choice-list sese-rps-list">
          {RPS_UI_CHOICES.map((choice) => (
            <button
              key={choice.id}
              className={`sese-rps-button ${activeRpsPick === choice.id ? "is-selected" : ""}`}
              type="button"
              title={choice.label}
              aria-label={choice.label}
              aria-pressed={activeRpsPick === choice.id}
              disabled={disabled || !isMyTurn || hasPlayerRpsPick}
              onClick={() => {
                setSelectedRps(normalizeRpsChoice(choice.id));
                onChoose(choice.id);
              }}
            >
              {choice.icon}
            </button>
          ))}
        </div>
        {!isMyTurn ? (
          <div className="sese-pending-wait">
            {hasPlayerRpsPick ? "你的出拳已记录，等待对方出拳。" : "等待对方出拳。"}
          </div>
        ) : null}
      </div>
    );
  }

  if (pending.phase === "submitted") {
    return (
      <div className="sese-pending-card">
        <div className="sese-pending-head">
          <span>{isMyReview ? "需要你验收" : "等待对方验收"}</span>
          <strong>{name}</strong>
        </div>
        <p className="sese-submission-text">{displayText(pending.submission_text || "")}</p>
        {isMyReview ? (
          <>
            <textarea
              value={submission}
              placeholder="写一句验收反馈，会同步给对方"
              onChange={(event) => onSubmissionChange(event.target.value)}
            />
            <div className="sese-review-actions">
              <button type="button" disabled={disabled} onClick={onApprove}>通过</button>
              <button type="button" disabled={disabled} onClick={onReject}>打回</button>
            </div>
          </>
        ) : (
          <div className="sese-pending-wait">
            等待对方验收你的提交。
          </div>
        )}
      </div>
    );
  }

  if (pending.phase === "questioning") {
    const questionPrompt = displaySystemText(pending.question_prompt || "请问对方一个你很想知道答案却一直没有问的问题。");
    const waitingTask = displaySystemText(pending.waiting_task || "对方正在出题中。");
    return (
      <div className="sese-pending-card">
        <div className="sese-pending-head">
          <span>{isMyReview ? "你来出题" : "等待对方出题"}</span>
          <strong>{name}</strong>
        </div>
        {isMyReview ? (
          <>
            <p>{questionPrompt}</p>
            <textarea
              value={submission}
              placeholder="写下你的问题"
              onChange={(event) => onSubmissionChange(event.target.value)}
            />
            <div className="sese-review-actions">
              <button type="button" disabled={disabled || !submission.trim()} onClick={onSubmit}>提交题目</button>
            </div>
          </>
        ) : (
          <div className="sese-pending-wait">
            {waitingTask === "对方正在出题中。" ? "等待对方给出真心话题目。" : waitingTask}
          </div>
        )}
      </div>
    );
  }

  const waitingText = hasQuestionText ? "等待对方回答这个问题。" : "等待对方完成并提交任务。";

  return (
    <div className="sese-pending-card">
      <div className="sese-pending-head">
        <span>{isMine ? "你的惩罚任务" : "等待对方提交"}</span>
        <strong>{name}</strong>
      </div>
      {lastRejectReason ? <div className="sese-review-feedback">打回反馈：{lastRejectReason}</div> : null}
      {reviewFeedback && reviewFeedback.outcome === "rejected" && isMine ? (
        <div className="sese-review-feedback">对方的反馈：{reviewFeedback.text}</div>
      ) : null}
      {hasQuestionText ? <p className="sese-submission-text">题目：{displayText(pending.question_text)}</p> : null}
      {isMine ? (
        <>
          {!hasQuestionText ? <p>{displaySystemText(pending.task || "")}</p> : null}
          {!hasQuestionText && submissionHint ? <div className="sese-pending-tip">提交要求：{submissionHint}</div> : null}
          <textarea
            value={submission}
            placeholder={hasQuestionText ? "在这里写回答" : "在这里写提交内容"}
            onChange={(event) => onSubmissionChange(event.target.value)}
          />
          <div className="sese-review-actions">
            <button type="button" disabled={disabled || !submission.trim()} onClick={onSubmit}>{hasQuestionText ? "提交回答" : "提交验收"}</button>
            {canPass ? <button type="button" disabled={disabled} onClick={onPass}>使用Pass卡</button> : null}
          </div>
        </>
      ) : (
        <div className="sese-pending-wait">
          <span>{waitingText}</span>
        </div>
      )}
    </div>
  );
}

function ReviewFeedbackPanel({ feedback, onClose }: { feedback: ReviewFeedback; onClose: () => void }) {
  return (
    <div className="sese-pending-card sese-review-feedback-card">
      <div className="sese-pending-head">
        <span>{feedback.outcome === "approved" ? "通过反馈" : "打回反馈"}</span>
        <strong>{feedback.title}</strong>
      </div>
      <div className="sese-review-feedback">{feedback.text}</div>
      <div className="sese-pending-wait">{feedback.note}</div>
      <div className="sese-review-actions">
        <button type="button" onClick={onClose}>知道了</button>
      </div>
    </div>
  );
}
