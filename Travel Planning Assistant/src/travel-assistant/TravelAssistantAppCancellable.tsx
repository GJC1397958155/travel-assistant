import { useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import {
  ChatApiError,
  ChatRequestCancelledError,
  sendChatMessage,
} from './apiRuntime';
import { ItineraryPanel } from './itinerary';
import MemoryDropdown from './MemoryDropdown';
import { ChatArea, Header } from './shellRuntime';
import { Message, SessionState, StructuredItinerary } from './types';
import '../styles/app.css';

export default function TravelAssistantAppCancellable() {
  const [sessionId, setSessionId] = useState('demo-session');
  const [userId, setUserId] = useState('demo-user');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [currentItinerary, setCurrentItinerary] = useState<StructuredItinerary | undefined>();
  const [sessionState, setSessionState] = useState<SessionState | undefined>();
  const [error, setError] = useState<string | null>(null);
  const [shouldScrollItinerary, setShouldScrollItinerary] = useState(false);
  const [isPanelCollapsed, setIsPanelCollapsed] = useState(false);
  const activeRequestControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const savedSessionId = localStorage.getItem('travel_session_id');
    const savedUserId = localStorage.getItem('travel_user_id');

    if (savedSessionId) {
      setSessionId(savedSessionId);
    }
    if (savedUserId) {
      setUserId(savedUserId);
    }
  }, []);

  useEffect(() => {
    localStorage.setItem('travel_session_id', sessionId);
    localStorage.setItem('travel_user_id', userId);
  }, [sessionId, userId]);

  useEffect(() => {
    return () => {
      activeRequestControllerRef.current?.abort('cancelled');
    };
  }, []);

  const handleCancelGeneration = () => {
    activeRequestControllerRef.current?.abort('cancelled');
  };

  const handleSendMessage = async (messageText: string) => {
    if (!messageText.trim()) {
      return;
    }

    setError(null);
    setShouldScrollItinerary(false);

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: messageText,
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    const assistantMessageId = `assistant-${Date.now()}`;
    const assistantTimestamp = Date.now();
    const requestController = new AbortController();
    activeRequestControllerRef.current = requestController;

    try {
      const response = await sendChatMessage(
        {
          message: messageText,
          session_id: sessionId,
          user_id: userId,
        },
        {
          signal: requestController.signal,
          onToken: (delta) => {
            setMessages((prev) => {
              const existingIndex = prev.findIndex((message) => message.id === assistantMessageId);
              if (existingIndex === -1) {
                return [
                  ...prev,
                  {
                    id: assistantMessageId,
                    role: 'assistant',
                    content: delta,
                    timestamp: assistantTimestamp,
                  },
                ];
              }

              const next = [...prev];
              const existing = next[existingIndex];
              next[existingIndex] = {
                ...existing,
                content: existing.content + delta,
              };
              return next;
            });
          },
        },
      );

      const assistantMessage: Message = {
        id: assistantMessageId,
        role: 'assistant',
        content: response.answer,
        timestamp: assistantTimestamp,
        structured_itinerary: response.structured_itinerary ?? undefined,
      };

      setMessages((prev) => {
        const existingIndex = prev.findIndex((message) => message.id === assistantMessageId);
        if (existingIndex === -1) {
          return [...prev, assistantMessage];
        }

        const next = [...prev];
        next[existingIndex] = assistantMessage;
        return next;
      });

      if (response.structured_itinerary) {
        setCurrentItinerary(response.structured_itinerary);
        setShouldScrollItinerary(true);
      }

      if (response.session_state) {
        setSessionState(response.session_state);
      }
    } catch (err) {
      if (err instanceof ChatRequestCancelledError) {
        setMessages((prev) => [
          ...prev,
          {
            id: `cancelled-${Date.now()}`,
            role: 'assistant',
            content: '已停止本次生成。你可以继续补充需求后重新发送。',
            timestamp: Date.now(),
          },
        ]);
        return;
      }

      const errorMessage =
        err instanceof ChatApiError ? err.message : '发送消息失败，请稍后重试。';

      setError(errorMessage);

      const errorMessageBubble: Message = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: `错误：${errorMessage}`,
        timestamp: Date.now(),
      };

      setMessages((prev) => [...prev, errorMessageBubble]);
    } finally {
      if (activeRequestControllerRef.current === requestController) {
        activeRequestControllerRef.current = null;
      }
      setIsLoading(false);
    }
  };

  return (
    <div className="app">
      <Header
        sessionId={sessionId}
        userId={userId}
        onSessionIdChange={setSessionId}
        onUserIdChange={setUserId}
      />

      <div className="app-content">
        <div className="main-area">
          <ChatArea
            messages={messages}
            isLoading={isLoading}
            onSendMessage={handleSendMessage}
            onCancelGeneration={handleCancelGeneration}
          />

          <div className="memory-area">
            <MemoryDropdown sessionState={sessionState} />
          </div>
        </div>

        <div className={`side-panel-shell ${isPanelCollapsed ? 'collapsed' : ''}`}>
          <button
            className="panel-toggle"
            onClick={() => setIsPanelCollapsed((prev) => !prev)}
            aria-label={isPanelCollapsed ? '展开行程面板' : '收起行程面板'}
            aria-expanded={!isPanelCollapsed}
          >
            {isPanelCollapsed ? <ChevronLeft size={20} /> : <ChevronRight size={20} />}
          </button>

          <div className="side-panel">
            <ItineraryPanel itinerary={currentItinerary} shouldScroll={shouldScrollItinerary} />
          </div>
        </div>
      </div>

      {error && (
        <div className="error-toast" onClick={() => setError(null)}>
          {error}
        </div>
      )}
    </div>
  );
}
