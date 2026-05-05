export interface ChatRequest {
  message: string;
  session_id: string;
  user_id: string;
  client_context?: string;
}

export interface MapCandidate {
  name?: string;
  address?: string;
  formatted_address?: string;
  longitude?: number;
  latitude?: number;
  poi_id?: string;
  source?: string;
}

export interface Activity {
  title: string;
  location?: string;
  reason?: string;
  longitude?: number;
  latitude?: number;
  poi_id?: string;
  formatted_address?: string;
  map_query?: string;
  map_source?: string;
  map_candidates?: MapCandidate[];
}

export interface DailyPlan {
  day: number;
  date?: string;
  title?: string;
  weather?: string;
  morning: Activity[];
  afternoon: Activity[];
  evening: Activity[];
  transport_tip?: string;
  dining_tip?: string;
  notes?: string[];
  alternatives?: string[];
  highlights?: string[];
}

export interface HotelSuggestion {
  area?: string;
  reason?: string;
  candidates?: string[];
}

export interface BudgetAdvice {
  level?: string;
  summary?: string;
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
  pace?: string;
  preference_tags?: string[];
  must_visit?: string[];
  avoid?: string[];
}

export interface ChatResponse {
  session_id: string;
  user_id: string;
  user_input: string;
  answer: string;
  structured_itinerary?: StructuredItinerary | null;
  session_state?: SessionState | null;
  memory_backend?: string;
  memory_persistent?: boolean;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  structured_itinerary?: StructuredItinerary;
}
