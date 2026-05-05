import { ChatRequest, ChatResponse } from './types';

const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

export class ChatApiError extends Error {
  constructor(message: string, public statusCode?: number) {
    super(message);
    this.name = 'ChatApiError';
  }
}

export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  const controller = new AbortController();
  let timeoutId = 0;
  const refreshTimeout = () => {
    window.clearTimeout(timeoutId);
    timeoutId = window.setTimeout(() => controller.abort(), 180000);
  };
  refreshTimeout();

  try {
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      signal: controller.signal,
      body: JSON.stringify(request),
    });
    refreshTimeout();

    if (!response.ok) {
      let errorMessage = `请求失败: ${response.status} ${response.statusText}`;
      const contentType = response.headers.get('content-type') || '';

      if (contentType.includes('application/json')) {
        const errorData = await response.json().catch(() => null);
        const detail =
          typeof errorData?.detail === 'string'
            ? errorData.detail
            : typeof errorData?.message === 'string'
              ? errorData.message
              : '';
        if (detail) {
          errorMessage = detail;
        }
      } else {
        const errorText = await response.text().catch(() => '');
        if (errorText) {
          errorMessage = errorText;
        }
      }

      throw new ChatApiError(errorMessage, response.status);
    }

    const data = (await response.json()) as ChatResponse;
    return {
      ...data,
      structured_itinerary: data.structured_itinerary ?? undefined,
      session_state: data.session_state ?? undefined,
    };
  } catch (error) {
    if (error instanceof ChatApiError) {
      throw error;
    }

    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ChatApiError('后端处理超时，请查看后端窗口日志，或稍后重试。');
    }

    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new ChatApiError('无法连接到后端服务，请确认 `http://localhost:8000` 已启动。');
    }

    throw new ChatApiError('发送消息失败，请稍后重试。');
  } finally {
    window.clearTimeout(timeoutId);
  }
}
