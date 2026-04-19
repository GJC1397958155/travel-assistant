import { useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import {
  ChatApiError,
  ChatRequestCancelledError,
  fetchStructuredItinerary,
  sendChatMessage,
} from './apiRuntime';
import { ItineraryPanel } from './itinerary';
import MemoryDropdown from './MemoryDropdown';
import { ChatArea, Header } from './shellRuntime';
import { Message, SessionState, StructuredItinerary } from './types';
import '../styles/app.css';

const PLACEHOLDER_KEYWORDS = ['\u5f85\u8865\u5145', '\u5b89\u6392\u5f85\u8865\u5145'];
const CANCELLED_MESSAGE =
  '\u5df2\u505c\u6b62\u672c\u6b21\u751f\u6210\u3002\u4f60\u53ef\u4ee5\u7ee7\u7eed\u8865\u5145\u9700\u6c42\u540e\u91cd\u65b0\u53d1\u9001\u3002';
const DEFAULT_SEND_ERROR = '\u53d1\u9001\u6d88\u606f\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002';
const STRUCTURE_FALLBACK_ALERT =
  '\u53f3\u4fa7\u7ed3\u6784\u5316\u6574\u7406\u6682\u65f6\u5931\u8d25\u4e86\uff0c\u5148\u4fdd\u7559\u57fa\u7840\u7ed3\u679c\uff0c\u4f60\u53ef\u4ee5\u518d\u8bd5\u4e00\u6b21\u540c\u6837\u7684\u8bf7\u6c42\u3002';
const EXPAND_PANEL_LABEL = '\u5c55\u5f00\u884c\u7a0b\u9762\u677f';
const COLLAPSE_PANEL_LABEL = '\u6536\u8d77\u884c\u7a0b\u9762\u677f';
const ERROR_PREFIX = '\u9519\u8bef\uff1a';

function hasPlaceholderText(value: string) {
  return PLACEHOLDER_KEYWORDS.some((keyword) => value.includes(keyword));
}

function hasConcreteDailyPlan(itinerary?: StructuredItinerary) {
  if (!itinerary?.daily_plans || itinerary.daily_plans.length === 0) {
    return false;
  }

  return itinerary.daily_plans.some((plan) => {
    const activities = [...(plan.morning ?? []), ...(plan.afternoon ?? []), ...(plan.evening ?? [])];
    return activities.some((item) => {
      const title = (item.title ?? '').trim();
      const location = (item.location ?? '').trim();
      const combined = `${title} ${location}`.trim();
      if (!combined) {
        return false;
      }

      return !hasPlaceholderText(combined);
    });
  });
}

function buildItineraryFallback(
  answer: string,
  sessionState?: SessionState,
  source?: StructuredItinerary,
): StructuredItinerary {
  if (source && hasConcreteDailyPlan(source)) {
    return source;
  }

  return {
    status: 'ready',
    destination: sessionState?.city ?? '',
    days: sessionState?.days,
    date: sessionState?.date ?? '',
    companions: sessionState?.companions ?? '',
    travel_style: sessionState?.pace ?? '',
    budget: sessionState?.budget,
    overview: answer.trim().slice(0, 180),
    alerts: [STRUCTURE_FALLBACK_ALERT],
    raw_text: answer,
    daily_plans: source?.daily_plans ?? [],
  };
}

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
  const activeItineraryControllerRef = useRef<AbortController | null>(null);

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
      activeItineraryControllerRef.current?.abort('cancelled');
    };
  }, []);

  const handleCancelGeneration = () => {
    activeRequestControllerRef.current?.abort('cancelled');
    activeItineraryControllerRef.current?.abort('cancelled');
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
    activeItineraryControllerRef.current?.abort('cancelled');

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
          onStatus: (stage) => {
            if (stage === 'structuring') {
              setCurrentItinerary({ status: 'processing' } as StructuredItinerary);
              setShouldScrollItinerary(true);
            }
          },
        },
      );

      const baseItinerary = response.structured_itinerary ?? undefined;

      const assistantMessage: Message = {
        id: assistantMessageId,
        role: 'assistant',
        content: response.answer,
        timestamp: assistantTimestamp,
        structured_itinerary: baseItinerary,
      };

      setMessages((prev) => {
        const existingIndex = prev.findIndex((message) => message.id === assistantMessageId);
        if (existingIndex === -1) {
          return [...prev, assistantMessage];
        }

        const next = [...prev];
        next[existingIndex] = {
          ...next[existingIndex],
          content: response.answer,
          structured_itinerary: baseItinerary,
        };
        return next;
      });

      if (baseItinerary) {
        setCurrentItinerary(baseItinerary);
        setShouldScrollItinerary(true);
      }

      if (response.session_state) {
        setSessionState(response.session_state);
      }

      if (response.answer && !hasConcreteDailyPlan(baseItinerary)) {
        const itineraryController = new AbortController();
        activeItineraryControllerRef.current = itineraryController;

        if (!baseItinerary) {
          setCurrentItinerary({ status: 'processing' } as StructuredItinerary);
          setShouldScrollItinerary(true);
        }

        try {
          const hydratedItinerary = await fetchStructuredItinerary(
            {
              user_input: messageText,
              answer: response.answer,
              session_state: response.session_state ?? undefined,
            },
            {
              signal: itineraryController.signal,
              timeoutMs: 90000,
            },
          );

          if (itineraryController.signal.aborted) {
            return;
          }

          setCurrentItinerary(
            hasConcreteDailyPlan(hydratedItinerary)
              ? hydratedItinerary
              : buildItineraryFallback(response.answer, response.session_state ?? undefined, hydratedItinerary),
          );
          setShouldScrollItinerary(true);

          setMessages((prev) => {
            const existingIndex = prev.findIndex((message) => message.id === assistantMessageId);
            if (existingIndex === -1) {
              return prev;
            }

            const next = [...prev];
            next[existingIndex] = {
              ...next[existingIndex],
              structured_itinerary: hydratedItinerary,
            };
            return next;
          });
        } catch (itineraryError) {
          if (!(itineraryError instanceof ChatRequestCancelledError)) {
            console.error(itineraryError);
            setCurrentItinerary(
              buildItineraryFallback(response.answer, response.session_state ?? undefined, baseItinerary),
            );
            setShouldScrollItinerary(true);
          }
        } finally {
          if (activeItineraryControllerRef.current === itineraryController) {
            activeItineraryControllerRef.current = null;
          }
        }
      }
    } catch (err) {
      if (err instanceof ChatRequestCancelledError) {
        setMessages((prev) => [
          ...prev,
          {
            id: `cancelled-${Date.now()}`,
            role: 'assistant',
            content: CANCELLED_MESSAGE,
            timestamp: Date.now(),
          },
        ]);
        return;
      }

      const errorMessage = err instanceof ChatApiError ? err.message : DEFAULT_SEND_ERROR;
      setError(errorMessage);

      const errorMessageBubble: Message = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: `${ERROR_PREFIX}${errorMessage}`,
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
            aria-label={isPanelCollapsed ? EXPAND_PANEL_LABEL : COLLAPSE_PANEL_LABEL}
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
