"use client";

import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import { api, AutomationCommand, CoachChatMessage } from "../../lib/api";
import { useAppSettings } from "../../lib/settings";
import WitchHatIcon from "../../components/common/WitchHatIcon";

const COACH_SESSION_KEY = "ai-life-coach-conversation";
const WELCOME_MESSAGE: CoachChatMessage = {
  role: "assistant",
  content: "I’m your AI coach. Tell me what you’re working through, ask for a plan, or share what feels blocked.",
};
const SUGGESTIONS = [
  "What should I focus on today?",
  "Add a task today: 1h Learn EG high priority tag:study",
  "Update weekly priority Launch target time to 4h",
];

function CoachSpark({ size = 20 }: { size?: number }) {
  return <WitchHatIcon size={size} />;
}

function renderInlineMarkdown(value: string): ReactNode[] {
  return value.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((part, index) => (
    part.startsWith("**") && part.endsWith("**")
      ? <strong key={`${index}-${part}`}>{part.slice(2, -2)}</strong>
      : <span key={`${index}-${part}`}>{part}</span>
  ));
}

function FormattedCoachMessage({ content }: { content: string }) {
  return <>{content.replace(/\r\n/g, "\n").split("\n").map((originalLine, index) => {
    const line = originalLine.trim();
    if (!line) return <span aria-hidden="true" className="coach-markdown-spacer" key={`space-${index}`} />;

    const bullet = line.match(/^[-*]\s+(.+)$/);
    if (bullet) {
      return <span className="coach-markdown-list-item" key={`bullet-${index}`}><i aria-hidden="true">•</i><span>{renderInlineMarkdown(bullet[1])}</span></span>;
    }

    const numbered = line.match(/^(\d+)\.\s+(.+)$/);
    if (numbered) {
      return <span className="coach-markdown-list-item" key={`number-${index}`}><i aria-hidden="true">{numbered[1]}.</i><span>{renderInlineMarkdown(numbered[2])}</span></span>;
    }

    const heading = line.replace(/^#{1,6}\s+/, "");
    return <span className="coach-markdown-line" key={`line-${index}`}>{renderInlineMarkdown(heading)}</span>;
  })}</>;
}

export default function CoachPage() {
  const settings = useAppSettings();
  const [messages, setMessages] = useState<CoachChatMessage[]>(() => {
    if (typeof window === "undefined") return [WELCOME_MESSAGE];
    try {
      const stored = window.sessionStorage.getItem(COACH_SESSION_KEY);
      return stored ? JSON.parse(stored) as CoachChatMessage[] : [WELCOME_MESSAGE];
    } catch {
      return [WELCOME_MESSAGE];
    }
  });
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [pendingCommand, setPendingCommand] = useState<AutomationCommand | null>(null);
  const conversationEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    window.sessionStorage.setItem(COACH_SESSION_KEY, JSON.stringify(messages));
    conversationEnd.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  useEffect(() => {
    function startNewConversation() {
      setMessages([WELCOME_MESSAGE]);
      setPendingCommand(null);
      setDraft("");
      setError("");
    }
    window.addEventListener("ai-life:start-coach-conversation", startNewConversation);
    return () => window.removeEventListener("ai-life:start-coach-conversation", startNewConversation);
  }, []);

  async function sendMessage(message: string) {
    const normalized = message.trim();
    if (!normalized || busy) return;
    const userMessage: CoachChatMessage = { role: "user", content: normalized };
    const history = messages.slice(-30);
    setMessages((current) => [...current, userMessage]);
    setDraft("");
    setBusy(true);
    setError("");
    try {
      if (pendingCommand && /^(?:confirm(?:\s+it)?|yes|approve|go ahead)$/i.test(normalized)) {
        const result = await api.confirmCommand(pendingCommand.id);
        setPendingCommand(null);
        setMessages((current) => [...current, { role: "assistant", content: result.response_message }]);
      } else if (pendingCommand && /^(?:reject(?:\s+it)?|no|cancel)$/i.test(normalized)) {
        const result = await api.rejectCommand(pendingCommand.id);
        setPendingCommand(null);
        setMessages((current) => [...current, { role: "assistant", content: result.response_message }]);
      } else {
        const command = await api.executeCommand(normalized, crypto.randomUUID());
        if (command.intent === "unknown" && !command.parameters_json.clarification_question) {
          const response = await api.chatWithCoach(normalized, history);
          setMessages((current) => [...current, { role: "assistant", content: response.reply }]);
        } else {
          setPendingCommand(command.status === "pending_confirmation" ? command : null);
          setMessages((current) => [...current, { role: "assistant", content: command.response_message }]);
        }
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The coach could not respond. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendMessage(draft);
  }

  function clearConversation() {
    setMessages([WELCOME_MESSAGE]);
    setError("");
  }

  async function decideCommand(action: "confirm" | "reject") {
    if (!pendingCommand || busy) return;
    setBusy(true);
    setError("");
    try {
      const result = action === "confirm"
        ? await api.confirmCommand(pendingCommand.id)
        : await api.rejectCommand(pendingCommand.id);
      setPendingCommand(null);
      setMessages((current) => [...current, { role: "assistant", content: result.response_message }]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The requested change could not be completed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="coach-workspace">
      <header className="coach-page-header">
        <div className="coach-heading-icon"><CoachSpark size={25} /></div>
        <div><h1>AI Coach</h1><p>A thinking partner for planning, focus, and reflection.</p></div>
        <span className="coach-status"><i /> Ready</span>
        <button className="coach-clear-button" disabled={busy || messages.length === 1} onClick={clearConversation} type="button">Clear conversation</button>
      </header>

      <div className="coach-chat-card">
        <div aria-live="polite" className="coach-conversation">
          {messages.map((message, index) => (
            <article className={`coach-message ${message.role}`} key={`${message.role}-${index}-${message.content.slice(0, 16)}`}>
              {message.role === "assistant" ? <span className="coach-avatar"><CoachSpark size={17} /></span> : <span className={`coach-user-avatar ${settings.avatarDataUrl ? "has-image" : ""}`} style={settings.avatarDataUrl ? { backgroundImage: `url(${settings.avatarDataUrl})` } : undefined}>{settings.avatarDataUrl ? "" : settings.name.slice(0, 1).toUpperCase() || "Y"}</span>}
              <div><small>{message.role === "assistant" ? "AI Coach" : "You"}</small><p><FormattedCoachMessage content={message.content} /></p></div>
            </article>
          ))}
          {busy ? <article className="coach-message assistant coach-typing"><span className="coach-avatar"><CoachSpark size={17} /></span><div><small>AI Coach</small><p aria-label="AI Coach is thinking">
            <svg aria-hidden="true" className="coach-cat-loader" viewBox="0 0 120 64">
              <path className="coach-cat-leg coach-cat-leg-a" d="M45 37 L39 55" />
              <path className="coach-cat-leg coach-cat-leg-b" d="M57 39 L62 56" />
              <path className="coach-cat-leg coach-cat-leg-a" d="M72 39 L66 56" />
              <path className="coach-cat-leg coach-cat-leg-b" d="M84 36 L90 53" />
              <path className="coach-cat-tail" d="M35 31 C17 30 21 12 8 16" />
              <ellipse className="coach-cat-body" cx="62" cy="31" rx="31" ry="17" />
              <ellipse className="coach-cat-body" cx="91" cy="25" rx="17" ry="15" />
              <path className="coach-cat-body" d="M78 16 L83 3 L91 14 L102 5 L103 21 Z" />
              <path className="coach-cat-detail" d="M95 24 Q99 20 103 24 M103 29 L113 27 M103 31 L114 32" />
            </svg>
          </p></div></article> : null}
          <div ref={conversationEnd} />
        </div>

        {pendingCommand ? <section className="coach-confirmation-card">
          <div><span>Confirmation required</span><strong>{pendingCommand.intent.replaceAll("_", " ")}</strong><p>{pendingCommand.response_message}</p></div>
          <div><button disabled={busy} onClick={() => void decideCommand("reject")} type="button">Reject</button><button className="confirm" disabled={busy} onClick={() => void decideCommand("confirm")} type="button">Confirm change</button></div>
        </section> : null}

        {messages.length === 1 && !pendingCommand ? <div className="coach-suggestions">
          <span>Try asking</span>
          <div>{SUGGESTIONS.map((suggestion) => <button disabled={busy} key={suggestion} onClick={() => void sendMessage(suggestion)} type="button">{suggestion}</button>)}</div>
        </div> : null}

        {error ? <div className="coach-chat-error">{error}</div> : null}

        <form className="coach-composer" onSubmit={submitMessage}>
          <textarea
            aria-label="Message your AI coach"
            disabled={busy}
            maxLength={20000}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            placeholder="Message your AI coach…"
            rows={2}
            value={draft}
          />
          <div><span>Conversation is kept for this browser session.</span><button disabled={busy || !draft.trim()} type="submit"><CoachSpark size={16} /> {busy ? "Thinking…" : "Send"}</button></div>
        </form>
      </div>
    </section>
  );
}
