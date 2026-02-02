"use client";

import { useState, useEffect, useRef } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";

// WebSocket URL
const WS_URL = "ws://localhost:8000/ws/chat";

type Message = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
};

type ThinkingEvent = {
  id: string;
  type: "tool_call" | "tool_result" | "agent_call" | "agent_result";
  agent: string;
  tool: string;
  args?: Record<string, unknown>;
  result?: string;
  timestamp: Date;
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [thinkingEvents, setThinkingEvents] = useState<ThinkingEvent[]>([]);
  const [sessionId, setSessionId] = useState<string>("");

  const wsRef = useRef<WebSocket | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Generate or load session ID
  const [initialSessionId] = useState(() => {
    // Check if we're in the browser (not SSR)
    if (typeof window === "undefined") {
      return "";
    }
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

  // Load existing messages from backend
  useEffect(() => {
    if (!sessionId) return;

    const loadMessages = async () => {
      try {
        const response = await fetch(
          `http://localhost:8000/messages/${sessionId}`,
        );
        if (response.ok) {
          const data = await response.json();
          if (data.messages && data.messages.length > 0) {
            // Convert backend messages to UI message format
            const loadedMessages: Message[] = data.messages.map(
              (msg: {
                role?: string;
                content: string;
                timestamp?: string | number;
              }) => ({
                id: crypto.randomUUID(),
                role: msg.role || "assistant",
                content: msg.content,
                timestamp: new Date(msg.timestamp || Date.now()),
              }),
            );
            setMessages(loadedMessages);
          }
        }
      } catch (error) {
        console.error("Failed to load messages:", error);
      }
    };

    loadMessages();
  }, [sessionId]);

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
          setThinkingEvents([]);
        } else if (data.type === "tool_call") {
          const event: ThinkingEvent = {
            id: crypto.randomUUID(),
            type: "tool_call",
            agent: data.agent,
            tool: data.tool,
            args: data.args,
            timestamp: new Date(),
          };
          setThinkingEvents((prev) => [...prev, event]);
        } else if (data.type === "tool_result") {
          const event: ThinkingEvent = {
            id: crypto.randomUUID(),
            type: "tool_result",
            agent: data.agent,
            tool: data.tool,
            result: data.result,
            timestamp: new Date(),
          };
          setThinkingEvents((prev) => [...prev, event]);
        } else if (data.type === "agent_call") {
          const event: ThinkingEvent = {
            id: crypto.randomUUID(),
            type: "agent_call",
            agent: data.agent,
            tool: data.tool,
            args: data.args,
            timestamp: new Date(),
          };
          setThinkingEvents((prev) => [...prev, event]);
        } else if (data.type === "agent_result") {
          const event: ThinkingEvent = {
            id: crypto.randomUUID(),
            type: "agent_result",
            agent: data.agent,
            tool: data.tool,
            result: data.result,
            timestamp: new Date(),
          };
          setThinkingEvents((prev) => [...prev, event]);
        } else if (data.type === "message") {
          setIsThinking(false);
          setThinkingEvents([]);
          const newMessage: Message = {
            id: crypto.randomUUID(),
            role: data.role || "assistant",
            content: data.content,
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, newMessage]);
        } else if (data.type === "error") {
          setIsThinking(false);
          setThinkingEvents([]);
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
  }, [messages, isThinking, thinkingEvents]);

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

  const handleNewChat = () => {
    // Close existing WebSocket connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    // Generate new session ID
    const newSessionId = crypto.randomUUID();
    localStorage.setItem("spotify_session_id", newSessionId);

    // Clear messages and state
    setMessages([]);
    setThinkingEvents([]);
    setIsThinking(false);
    setInput("");

    // Update session ID (this will trigger WebSocket reconnection)
    setSessionId(newSessionId);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-4xl h-[85vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="border-b p-4 flex items-center justify-between bg-primary-brand text-primary-brand-foreground rounded-t-lg shrink-0">
          <div className="flex items-center gap-3">
            <div className="text-2xl">🎵</div>
            <div>
              <h1 className="text-xl font-bold">Spotify Agent</h1>
              <p className="text-sm opacity-90">
                Powered by AWS Bedrock & Claude
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Button
              onClick={handleNewChat}
              variant="ghost"
              size="sm"
              className="bg-primary-brand-foreground/10 hover:bg-primary-brand-foreground/20 text-primary-brand-foreground border-primary-brand-foreground/30"
            >
              ✨ New Chat
            </Button>
            <Badge
              variant={isConnected ? "connected" : "destructive"}
              className={cn(!isConnected && "bg-destructive text-white")}
            >
              {isConnected ? "🟢 Connected" : "🔴 Disconnected"}
            </Badge>
            <Badge variant="playback">Single-user playback mode</Badge>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-hidden">
          <ScrollArea className="h-full p-4">
            <div className="space-y-4">
              {messages.length === 0 && (
                <div className="text-center text-muted-foreground py-8">
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
                    <Avatar className="h-8 w-8 bg-primary-brand">
                      <AvatarFallback className="bg-primary-brand text-primary-brand-foreground text-xs">
                        🎵
                      </AvatarFallback>
                    </Avatar>
                  )}

                  <div
                    className={cn(
                      "max-w-[70%] rounded-lg px-4 py-2",
                      message.role === "user" &&
                        "bg-message-user text-message-user-foreground",
                      message.role === "system" &&
                        "bg-destructive/10 text-destructive border border-destructive/20",
                      message.role === "assistant" &&
                        "bg-message-assistant text-message-assistant-foreground",
                    )}
                  >
                    <p className="text-sm whitespace-pre-wrap">
                      {message.content}
                    </p>
                    <p className="text-xs opacity-70 mt-1">
                      {message.timestamp.toLocaleTimeString()}
                    </p>
                  </div>

                  {message.role === "user" && (
                    <Avatar className="h-8 w-8 bg-message-user">
                      <AvatarFallback className="bg-message-user text-message-user-foreground text-xs">
                        👤
                      </AvatarFallback>
                    </Avatar>
                  )}
                </div>
              ))}

              {isThinking && (
                <div className="flex gap-3 justify-start">
                  <Avatar className="h-8 w-8 bg-primary-brand">
                    <AvatarFallback className="bg-primary-brand text-primary-brand-foreground text-xs">
                      🎵
                    </AvatarFallback>
                  </Avatar>
                  <div className="bg-message-assistant text-message-assistant-foreground rounded-lg px-4 py-2 max-w-[70%]">
                    {thinkingEvents.length === 0 ? (
                      <div className="flex gap-1">
                        <span className="animate-bounce">●</span>
                        <span className="animate-bounce delay-100">●</span>
                        <span className="animate-bounce delay-200">●</span>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {thinkingEvents.map((event) => (
                          <div key={event.id} className="text-xs">
                            {event.type === "agent_call" && (
                              <div className="flex items-center gap-2 text-chart-1">
                                <span>🤖</span>
                                <span className="font-medium">
                                  Delegating to{" "}
                                  {event.tool
                                    .replace("call_", "")
                                    .replace("_", " ")}
                                </span>
                              </div>
                            )}
                            {event.type === "tool_call" && (
                              <div className="flex items-center gap-2 text-chart-2">
                                <span>🔧</span>
                                <span className="font-medium">
                                  Using tool: {event.tool}
                                </span>
                                {event.args && (
                                  <span className="text-muted-foreground truncate max-w-xs">
                                    {JSON.stringify(event.args).substring(
                                      0,
                                      50,
                                    )}
                                  </span>
                                )}
                              </div>
                            )}
                            {event.type === "agent_result" && (
                              <div className="flex items-center gap-2 text-chart-3">
                                <span>✓</span>
                                <span className="font-medium">
                                  Agent completed
                                </span>
                              </div>
                            )}
                            {event.type === "tool_result" && (
                              <div className="flex items-center gap-2 text-chart-4">
                                <span>✓</span>
                                <span className="font-medium">
                                  Tool completed
                                </span>
                              </div>
                            )}
                          </div>
                        ))}
                        <div className="flex gap-1 mt-2">
                          <span className="animate-bounce">●</span>
                          <span className="animate-bounce delay-100">●</span>
                          <span className="animate-bounce delay-200">●</span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <div ref={scrollRef} />
            </div>
          </ScrollArea>
        </div>

        {/* Input */}
        <div className="border-t p-4 bg-muted/30 rounded-b-lg shrink-0">
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
              className="bg-primary-brand hover:bg-primary-brand/90 text-primary-brand-foreground"
            >
              Send
            </Button>
          </div>
          {!isConnected && (
            <p className="text-xs text-destructive mt-2">
              Disconnected. Make sure the backend is running (docker-compose up)
            </p>
          )}
        </div>
      </Card>
    </div>
  );
}
