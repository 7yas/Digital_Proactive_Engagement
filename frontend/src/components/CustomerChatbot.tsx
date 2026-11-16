import { useEffect, useRef, useState } from 'react';
import {
  Bot,
  Send,
  User,
  X,
  Sparkles,
  MessageCircle,
  RotateCcw,
} from 'lucide-react';

import { api } from '../services/api';

type ChatMessage = {
  role: 'user' | 'assistant';
  content: string;
};

export default function CustomerChatbot({
  customerId,
  customerName,
  onClose,
}: {
  customerId: string;
  customerName?: string;
  onClose: () => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content:
        "Hello! I'm your financial support assistant. I can help explain recent changes in your account activity and answer questions about the assistance we're offering.",
    },
  ]);

  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: 'smooth',
    });
  }, [messages, sending]);

  const sendMessage = async () => {
    const text = input.trim();

    if (!text || sending) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: text,
    };

    const updatedMessages = [
      ...messages,
      userMessage,
    ];

    setMessages(updatedMessages);
    setInput('');
    setSending(true);

    try {
      const result = await api.customerChat(
        customerId,
        text,
        updatedMessages
      );

      setMessages((current) => [
        ...current,
        {
          role: 'assistant',
          content: result.reply,
        },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          role: 'assistant',
          content:
            "I'm sorry, I couldn't connect to the support assistant right now. Please try again.",
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  const resetChat = () => {
    setMessages([
      {
        role: 'assistant',
        content:
          "Hello! I'm your financial support assistant. How can I help you today?",
      },
    ]);
  };

  const suggestedQuestions = [
    'Why are you contacting me?',
    'What changed in my recent activity?',
    'Can you explain my current situation?',
    'What options do I have?',
  ];

  return (
    <div className="chat-overlay">
      <div className="customer-chat">

        <div className="chat-header">

          <div className="chat-header-left">

            <div className="chat-avatar">
              <Bot size={20} />
            </div>

            <div>
              <div className="chat-title">
                Financial Support Assistant
              </div>

              <div className="chat-subtitle">
                <span className="online-dot" />
                AI support · {customerName || customerId}
              </div>
            </div>

          </div>

          <div className="chat-header-actions">

            <button
              className="chat-icon-button"
              onClick={resetChat}
              title="Start new conversation"
            >
              <RotateCcw size={15} />
            </button>

            <button
              className="chat-icon-button"
              onClick={onClose}
              title="Close"
            >
              <X size={18} />
            </button>

          </div>

        </div>


        <div className="chat-body">

          <div className="chat-context-banner">

            <Sparkles size={16} />

            <div>
              <b>Personalized support</b>

              <span>
                This assistant uses your recent account activity
                to make the conversation relevant to your situation.
              </span>
            </div>

          </div>


          {messages.length === 1 && (

            <div className="chat-suggestions">

              <div className="suggestion-title">
                You can ask:
              </div>

              <div className="suggestion-grid">

                {suggestedQuestions.map((question) => (

                  <button
                    key={question}
                    onClick={() => setInput(question)}
                  >
                    <MessageCircle size={13} />
                    {question}
                  </button>

                ))}

              </div>

            </div>

          )}


          <div className="messages">

            {messages.map((message, index) => (

              <div
                key={index}
                className={
                  message.role === 'user'
                    ? 'message-row user-message'
                    : 'message-row assistant-message'
                }
              >

                {message.role === 'assistant' && (

                  <div className="message-avatar assistant-avatar">
                    <Bot size={14} />
                  </div>

                )}

                <div className="message-bubble">
                  {message.content}
                </div>

                {message.role === 'user' && (

                  <div className="message-avatar user-avatar">
                    <User size={14} />
                  </div>

                )}

              </div>

            ))}


            {sending && (

              <div className="message-row assistant-message">

                <div className="message-avatar assistant-avatar">
                  <Bot size={14} />
                </div>

                <div className="typing-bubble">

                  <span />
                  <span />
                  <span />

                </div>

              </div>

            )}

            <div ref={bottomRef} />

          </div>

        </div>


        <div className="chat-footer">

          <div className="chat-input-wrapper">

            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (
                  e.key === 'Enter' &&
                  !e.shiftKey
                ) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              placeholder="Ask about your situation..."
              rows={1}
              disabled={sending}
            />

            <button
              className="send-button"
              onClick={sendMessage}
              disabled={!input.trim() || sending}
            >
              <Send size={16} />
            </button>

          </div>

          <div className="chat-disclaimer">
            General support only. This assistant does not provide
            personalized financial advice.
          </div>

        </div>

      </div>
    </div>
  );
}