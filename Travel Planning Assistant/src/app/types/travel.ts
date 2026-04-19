// 旅游助手相关类型定义

export interface ChatRequest {
  message: string;
  session_id: string;
  user_id: string;
}

export interface DailyPlan {
  day: number;
  date: string;
  morning: string;
  afternoon: string;
  evening: string;
  highlights?: string[];
}

export interface HotelCandidate {
  name: string;
  price_range?: string;
  features?: string[];
}

export interface HotelSuggestion {
  area: string;
  reason: string;
  candidates: HotelCandidate[];
}

export interface BudgetAdvice {
  level: string;
  summary: string;
}

export interface StructuredItinerary {
  status: 'needs_clarification' | 'ready' | 'processing';
  destination?: string;
  days?: number;
  date?: string;
  companions?: string;
  travel_style?: string;
  budget?: number;
  overview?: string;
  weather_summary?: string;
  daily_plans?: DailyPlan[];
  hotel_suggestion?: HotelSuggestion;
  budget_advice?: BudgetAdvice;
  alerts?: string[];
  alternatives?: string[];
  follow_up_questions?: string[];
  source_summary?: string[];
  raw_text?: string;
}

export interface SessionState {
  city?: string;
  days?: number;
  date?: string;
  budget?: number;
  companions?: string;
  preference_tags?: string[];
}

export interface ChatResponse {
  session_id: string;
  user_id: string;
  user_input: string;
  answer: string;
  structured_itinerary?: StructuredItinerary;
  session_state?: SessionState;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  structured_itinerary?: StructuredItinerary;
}
