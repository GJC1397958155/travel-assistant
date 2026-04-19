export interface ChatRequest {
  message: string;
  session_id: string;
  user_id: string;
}

export interface DailyPlan {
  day: number;
  date: string;
  title?: string;
  weather?: string;
  morning: Activity[];
  afternoon: Activity[];
  evening: Activity[];
  route_points?: RoutePoint[];
  route_legs?: RouteLeg[];
  transport_tip?: string;
  dining_tip?: string;
  notes?: string[];
  alternatives?: string[];
  highlights?: string[];
}

export interface Activity {
  title: string;
  location?: string;
  reason?: string;
}

export interface RoutePoint {
  order: number;
  label?: string;
  title?: string;
  location?: string;
  time_slot?: string;
  lng?: number | null;
  lat?: number | null;
}

export interface RouteLeg {
  from_order: number;
  to_order: number;
  from_label?: string;
  to_label?: string;
  mode?: 'walking' | 'driving' | 'transit' | string;
  mode_label?: string;
  distance_text?: string;
  duration_text?: string;
  summary?: string;
  polyline?: string;
  path?: number[][];
  error?: string;
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

export interface DayRouteMapRequest {
  city?: string;
  route_points: RoutePoint[];
  route_legs?: RouteLeg[];
}

export interface DayRouteMapResponse {
  city?: string;
  route_points: RoutePoint[];
  route_legs: RouteLeg[];
  warnings?: string[];
}

export interface StructuredItineraryRequest {
  user_input: string;
  answer: string;
  session_state?: SessionState | null;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  structured_itinerary?: StructuredItinerary;
}
