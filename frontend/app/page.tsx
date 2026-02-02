"use client";

import { useState, useEffect, useRef } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

// WebSocket URL
const WS_URL = "ws://localhost:8000/ws/chat";

type Message = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [sessionId, setSessionId] = useState<string>("");

  const wsRef = useRef<WebSocket | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Generate or load session ID
  const [initialSessionId] = useState(() => {
    const storedSessionId = localStorage.getItem("spotify_session_id");
    if (storedSessionId) {
      return storedSessionId;
    } else {
      const newSessionId = crypto.randomUUID();
      localStorage.setItem("spotify_session_id", newSessionId);
      return newSessionId;
    }
  });

  useEffect(() => {
    setSessionId(initialSessionId);
  }, [initialSessionId]);

  // WebSocket connection
  useEffect(() => {
    if (!sessionId) return;

    const connectWebSocket = () => {
      const ws = new WebSocket(`${WS_URL}/${sessionId}`);

      ws.onopen = () => {
        console.log("WebSocket connected");
        setIsConnected(true);
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === "thinking") {
          setIsThinking(true);
        } else if (data.type === "message") {
          setIsThinking(false);
          const newMessage: Message = {
            id: crypto.randomUUID(),
            role: data.role || "assistant",
            content: data.content,
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, newMessage]);
        } else if (data.type === "error") {
          setIsThinking(false);
          const errorMessage: Message = {
            id: crypto.randomUUID(),
            role: "system",
            content: data.content,
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, errorMessage]);
        }
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        setIsConnected(false);
      };

      ws.onclose = () => {
        console.log("WebSocket disconnected");
        setIsConnected(false);
        // Attempt to reconnect after 3 seconds
        setTimeout(() => {
          if (sessionId) {
            connectWebSocket();
          }
        }, 3000);
      };

      wsRef.current = ws;
    };

    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [sessionId]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isThinking]);

  const handleSend = () => {
    if (!input.trim() || !isConnected || !wsRef.current) return;

    // Add user message to UI
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: input.trim(),
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);

    // Send to WebSocket
    wsRef.current.send(JSON.stringify({ message: input.trim() }));

    // Clear input
    setInput("");
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-zinc-50 to-zinc-100 dark:from-zinc-950 dark:to-black p-4">
      <Card className="w-full max-w-4xl h-[85vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="border-b p-4 flex items-center justify-between bg-gradient-to-r from-green-500 to-green-600 text-white rounded-t-lg">
          <div className="flex items-center gap-3">
            <div className="text-2xl">🎵</div>
            <div>
              <h1 className="text-xl font-bold">Spotify Agent</h1>
              <p className="text-sm text-green-50">
                Powered by AWS Bedrock & Claude
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge
              variant={isConnected ? "default" : "destructive"}
              className="bg-white/20"
            >
              {isConnected ? "🟢 Connected" : "🔴 Disconnected"}
            </Badge>
            <Badge variant="secondary" className="bg-yellow-500/90 text-white">
              Single-user playback mode
            </Badge>
          </div>
        </div>

        {/* Messages */}
        <ScrollArea className="flex-1 p-4">
          <div className="space-y-4">
            {messages.length === 0 && (
              <div className="text-center text-zinc-500 py-8">
                <p className="text-lg mb-2">👋 Welcome to Spotify Agent!</p>
                <p className="text-sm">
                  Ask me to search for songs, play music, or control playback.
                </p>
                <p className="text-sm mt-2">
                  Try: &quot;Search for Bohemian Rhapsody&quot; or
                  &quot;What&apos;s playing?&quot;
                </p>
              </div>
            )}

            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex gap-3 ${
                  message.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                {message.role !== "user" && (
                  <Avatar className="h-8 w-8 bg-green-500">
                    <AvatarFallback className="bg-green-500 text-white text-xs">
                      🎵
                    </AvatarFallback>
                  </Avatar>
                )}

                <div
                  className={`max-w-[70%] rounded-lg px-4 py-2 ${
                    message.role === "user"
                      ? "bg-green-500 text-white"
                      : message.role === "system"
                        ? "bg-red-100 text-red-800 border border-red-200"
                        : "bg-zinc-100 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100"
                  }`}
                >
                  <p className="text-sm whitespace-pre-wrap">
                    {message.content}
                  </p>
                  <p className="text-xs opacity-70 mt-1">
                    {message.timestamp.toLocaleTimeString()}
                  </p>
                </div>

                {message.role === "user" && (
                  <Avatar className="h-8 w-8 bg-blue-500">
                    <AvatarFallback className="bg-blue-500 text-white text-xs">
                      👤
                    </AvatarFallback>
                  </Avatar>
                )}
              </div>
            ))}

            {isThinking && (
              <div className="flex gap-3 justify-start">
                <Avatar className="h-8 w-8 bg-green-500">
                  <AvatarFallback className="bg-green-500 text-white text-xs">
                    🎵
                  </AvatarFallback>
                </Avatar>
                <div className="bg-zinc-100 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100 rounded-lg px-4 py-2">
                  <div className="flex gap-1">
                    <span className="animate-bounce">●</span>
                    <span className="animate-bounce delay-100">●</span>
                    <span className="animate-bounce delay-200">●</span>
                  </div>
                </div>
              </div>
            )}

            <div ref={scrollRef} />
          </div>
        </ScrollArea>

        {/* Input */}
        <div className="border-t p-4 bg-zinc-50 dark:bg-zinc-900 rounded-b-lg">
          <div className="flex gap-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="Ask me about Spotify music..."
              disabled={!isConnected}
              className="flex-1"
            />
            <Button
              onClick={handleSend}
              disabled={!input.trim() || !isConnected}
              className="bg-green-500 hover:bg-green-600"
            >
              Send
            </Button>
          </div>
          {!isConnected && (
            <p className="text-xs text-red-500 mt-2">
              Disconnected. Make sure the backend is running (docker-compose up)
            </p>
          )}
        </div>
      </Card>
    </div>
  );
}
