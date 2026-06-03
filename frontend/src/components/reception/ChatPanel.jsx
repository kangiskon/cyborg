import { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { AnimatePresence, motion } from "framer-motion";
import { Bot, Send, UserRound } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { CHAT_MESSAGE_MOTION, ICON_SIZE, quickPrompts, SCROLL_INTO_VIEW_OPTIONS } from "@/constants/reception";
import { apiPath, createChatMessage, toTestId } from "@/utils/reception";

function MessageList({ messages, sending, bottomRef }) {
  return (
    <div className="message-list" data-testid="chat-message-list">
      <AnimatePresence initial={false}>
        {messages.map((message) => (
          <motion.div
            data-testid={`chat-message-${message.id}`}
            key={message.id}
            className={`message-row ${message.role}`}
            initial={CHAT_MESSAGE_MOTION.initial}
            animate={CHAT_MESSAGE_MOTION.animate}
            exit={CHAT_MESSAGE_MOTION.exit}
          >
            <div className="message-avatar" data-testid={`chat-message-${message.id}-avatar`}>
              {message.role === "visitor" ? <UserRound size={ICON_SIZE.tiny} /> : <Bot size={ICON_SIZE.tiny} />}
            </div>
            <p data-testid={`chat-message-${message.id}-content`}>{message.content}</p>
          </motion.div>
        ))}
      </AnimatePresence>
      {sending && <div className="typing" data-testid="chat-typing-indicator"><span /> <span /> <span /></div>}
      <div ref={bottomRef} />
    </div>
  );
}

export function ChatPanel({ messages, setMessages, sessionId, setSessionId }) {
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    const node = bottomRef.current;
    node?.scrollIntoView(SCROLL_INTO_VIEW_OPTIONS);
  }, [messages]);

  const sendMessage = useCallback(async (text = input) => {
    const clean = text.trim();
    if (!clean || sending) return;
    setMessages((current) => [...current, createChatMessage("visitor", clean, "visitor")]);
    setInput("");
    setSending(true);
    try {
      const response = await axios.post(apiPath("/chat/message"), { session_id: sessionId, message: clean });
      setSessionId(response.data.session_id);
      setMessages((current) => [...current, createChatMessage("receptionist", response.data.message, "receptionist")]);
    } catch (error) {
      toast.error("The receptionist could not reply just now.");
      setMessages((current) => [...current, createChatMessage("receptionist", "I’m having trouble connecting. Please try again in a moment.", "error")]);
    } finally {
      setSending(false);
    }
  }, [input, sending, sessionId, setMessages, setSessionId]);

  return (
    <section className="chat-panel" data-testid="ai-receptionist-chat-panel">
      <div className="panel-heading">
        <div><span data-testid="chat-panel-kicker">Live reception desk</span><h2 data-testid="chat-panel-title">AI receptionist</h2></div>
        <div className="presence" data-testid="chat-presence-indicator"><span /> Available now</div>
      </div>
      <MessageList messages={messages} sending={sending} bottomRef={bottomRef} />
      <div className="quick-row" data-testid="chat-quick-prompts">
        {quickPrompts.map((prompt) => <button type="button" data-testid={`quick-prompt-${toTestId(prompt)}`} key={prompt} onClick={() => sendMessage(prompt)}>{prompt}</button>)}
      </div>
      <form data-testid="chat-input-form" className="chat-input-row" onSubmit={(event) => { event.preventDefault(); sendMessage(); }}>
        <Input data-testid="chat-message-input" value={input} onChange={(event) => setInput(event.target.value)} placeholder="Ask a question or request an appointment..." />
        <Button data-testid="chat-submit-button" type="submit" disabled={sending}><Send size={ICON_SIZE.inputAction} /> Send</Button>
      </form>
    </section>
  );
}