import { ChatRequest, ChatResponse } from '../types/travel';

// 配置后端 API 地址
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export class ChatApiError extends Error {
  constructor(message: string, public statusCode?: number) {
    super(message);
    this.name = 'ChatApiError';
  }
}

export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new ChatApiError(
        `请求失败: ${response.status} ${response.statusText}`,
        response.status
      );
    }

    const data: ChatResponse = await response.json();
    return data;
  } catch (error) {
    if (error instanceof ChatApiError) {
      throw error;
    }
    
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new ChatApiError('无法连接到服务器，请检查后端是否启动');
    }

    throw new ChatApiError('发送消息失败，请重试');
  }
}
