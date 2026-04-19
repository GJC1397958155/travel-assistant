import { useEffect, useState } from 'react';
import { Header } from './components/Header';
import { ChatArea } from './components/ChatArea';
import { ItineraryPanel } from './components/ItineraryPanel';
import { MemoryState } from './components/MemoryState';
import { sendChatMessage, ChatApiError } from './services/chatApi';
import { Message, StructuredItinerary, SessionState } from './types/travel';
import { ChevronRight, ChevronLeft } from 'lucide-react';
import '../styles/app.css';

function App() {
  const [sessionId, setSessionId] = useState('demo-session');
  const [userId, setUserId] = useState('demo-user');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [currentItinerary, setCurrentItinerary] = useState<StructuredItinerary | undefined>();
  const [sessionState, setSessionState] = useState<SessionState | undefined>();
  const [error, setError] = useState<string | null>(null);
  const [shouldScrollItinerary, setShouldScrollItinerary] = useState(false);
  const [isPanelCollapsed, setIsPanelCollapsed] = useState(false);

  // 从 localStorage 恢复状态
  useEffect(() => {
    const savedSessionId = localStorage.getItem('travel_session_id');
    const savedUserId = localStorage.getItem('travel_user_id');
    
    if (savedSessionId) setSessionId(savedSessionId);
    if (savedUserId) setUserId(savedUserId);
  }, []);

  // 保存到 localStorage
  useEffect(() => {
    localStorage.setItem('travel_session_id', sessionId);
    localStorage.setItem('travel_user_id', userId);
  }, [sessionId, userId]);

  const handleSendMessage = async (messageText: string) => {
    setError(null);
    setShouldScrollItinerary(false);

    // 添加用户消息
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: messageText,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await sendChatMessage({
        message: messageText,
        session_id: sessionId,
        user_id: userId,
      });

      // 添加助手回复
      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.answer,
        timestamp: Date.now(),
        structured_itinerary: response.structured_itinerary,
      };
      setMessages((prev) => [...prev, assistantMessage]);

      // 更新结构化行程
      if (response.structured_itinerary) {
        setCurrentItinerary(response.structured_itinerary);
        setShouldScrollItinerary(true);
      }

      // 更新会话状态
      if (response.session_state) {
        setSessionState(response.session_state);
      }
    } catch (err) {
      const errorMessage = err instanceof ChatApiError 
        ? err.message 
        : '发送消息失败，请重试';
      
      setError(errorMessage);
      
      // 添加错误消息
      const errorMsg: Message = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: `❌ ${errorMessage}`,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
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
          />
          
          <div className="memory-area">
            <MemoryState sessionState={sessionState} />
          </div>
        </div>

        <div className={`side-panel ${isPanelCollapsed ? 'collapsed' : ''}`}>
          <button
            className="panel-toggle"
            onClick={() => setIsPanelCollapsed(!isPanelCollapsed)}
            aria-label={isPanelCollapsed ? '展开面板' : '收起面板'}
          >
            {isPanelCollapsed ? <ChevronLeft size={20} /> : <ChevronRight size={20} />}
          </button>
          
          <ItineraryPanel
            itinerary={currentItinerary}
            shouldScroll={shouldScrollItinerary}
          />
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

export default App;
