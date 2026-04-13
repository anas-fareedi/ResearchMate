import { useState, useRef, useEffect } from "react";
import { postQA } from "../services/api";

export default function QAChat({ pdfPath }) {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "I've analyzed the PDF report. What would you like to know?" }
  ]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || isTyping) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsTyping(true);

    try {
      const data = await postQA(pdfPath, userMessage);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.answer || "No response." }
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error connecting to the Q&A service. Please try again." }
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="flex flex-col h-full h-[600px] border border-surface-300/30 rounded-xl bg-surface-100/50 backdrop-blur-sm overflow-hidden shadow-xl">
      <div className="bg-surface-200/80 px-4 py-3 border-b border-surface-300/30 flex items-center gap-2">
        <span className="relative flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent-400 opacity-75"></span>
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-accent-500"></span>
        </span>
        <h3 className="text-sm font-semibold text-white">Document Q&A</h3>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-accent-500 text-white rounded-tr-sm"
                  : "bg-surface-200/80 text-surface-50 rounded-tl-sm"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        {isTyping && (
          <div className="flex justify-start">
            <div className="bg-surface-200/80 rounded-2xl rounded-tl-sm px-4 py-3 pb-3.5">
              <div className="flex gap-1.5 items-center justify-center pt-1">
                <div className="w-1.5 h-1.5 bg-surface-400 rounded-full animate-bounce"></div>
                <div className="w-1.5 h-1.5 bg-surface-400 rounded-full animate-bounce" style={{ animationDelay: "0.15s" }}></div>
                <div className="w-1.5 h-1.5 bg-surface-400 rounded-full animate-bounce" style={{ animationDelay: "0.3s" }}></div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-3 bg-surface-200/40 border-t border-surface-300/30">
        <form onSubmit={handleSend} className="relative flex items-center">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about this report..."
            className="w-full bg-surface-300/40 border border-surface-400/30 rounded-full pl-4 pr-12 py-2.5 text-sm text-white placeholder-surface-400/80 focus:outline-none focus:ring-2 focus:ring-accent-500/50 transition-all"
          />
          <button
            type="submit"
            disabled={!input.trim() || isTyping}
            className="absolute right-1.5 p-1.5 rounded-full bg-accent-500 text-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-accent-400 transition-colors"
          >
            <svg className="w-4 h-4 translate-x-[1px] translate-y-[0.5px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </form>
      </div>
    </div>
  );
}