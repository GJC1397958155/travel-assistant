import { ChatRequest, ChatResponse } from './types';

const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

interface SendChatMessageOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
  onToken?: (delta: string) => void;
  onStatus?: (stage: string) => void;
}

interface SseFrame {
  event: string;
  data: string;
}

type StreamPayload = Record<string, unknown>;

export class ChatApiError extends Error {
  constructor(message: string, public statusCode?: number) {
    super(message);
    this.name = 'ChatApiError';
  }
}

export class ChatRequestCancelledError extends Error {
  constructor(message = '已停止本次生成。') {
    super(message);
    this.name = 'ChatRequestCancelledError';
  }
}

function normalizeChatResponse(data: ChatResponse): ChatResponse {
  return {
    ...data,
    structured_itinerary: data.structured_itinerary ?? undefined,
    session_state: data.session_state ?? undefined,
  };
}

function parseSseFrame(rawFrame: string): SseFrame | null {
  const lines = rawFrame.split(/\r?\n/);
  let event = 'message';
  const dataLines: string[] = [];

  for (const line of lines) {
    if (!line || line.startsWith(':')) {
      continue;
    }

    const separatorIndex = line.indexOf(':');
    const field = separatorIndex === -1 ? line : line.slice(0, separatorIndex);
    let value = separatorIndex === -1 ? '' : line.slice(separatorIndex + 1);

    if (value.startsWith(' ')) {
      value = value.slice(1);
    }

    if (field === 'event') {
      event = value || 'message';
    } else if (field === 'data') {
      dataLines.push(value);
    }
  }

  if (dataLines.length === 0) {
    return null;
  }

  return {
    event,
    data: dataLines.join('\n'),
  };
}

function splitSseFrames(buffer: string): { frames: SseFrame[]; remaining: string } {
  const frames: SseFrame[] = [];
  let remaining = buffer;

  while (true) {
    const match = remaining.match(/\r?\n\r?\n/);
    if (!match || match.index === undefined) {
      break;
    }

    const rawFrame = remaining.slice(0, match.index);
    remaining = remaining.slice(match.index + match[0].length);
    const parsedFrame = parseSseFrame(rawFrame);

    if (parsedFrame) {
      frames.push(parsedFrame);
    }
  }

  return { frames, remaining };
}

function parseStreamPayload(frame: SseFrame): StreamPayload {
  try {
    return JSON.parse(frame.data) as StreamPayload;
  } catch {
    throw new ChatApiError('后端返回了无法解析的流式数据。');
  }
}

export async function sendChatMessage(
  request: ChatRequest,
  options: SendChatMessageOptions = {},
): Promise<ChatResponse> {
  const requestController = new AbortController();
  const timeoutMs = options.timeoutMs ?? 180000;
  let timeoutId = 0;

  const abortWithReason = (reason: string) => {
    if (!requestController.signal.aborted) {
      requestController.abort(reason);
    }
  };

  const refreshTimeout = () => {
    window.clearTimeout(timeoutId);
    timeoutId = window.setTimeout(() => abortWithReason('timeout'), timeoutMs);
  };

  const handleExternalAbort = () => {
    abortWithReason(
      typeof options.signal?.reason === 'string' ? options.signal.reason : 'cancelled',
    );
  };

  if (options.signal) {
    if (options.signal.aborted) {
      handleExternalAbort();
    } else {
      options.signal.addEventListener('abort', handleExternalAbort, { once: true });
    }
  }

  refreshTimeout();

  try {
    const response = await fetch(`${API_BASE_URL}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      signal: requestController.signal,
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

    if (!response.body) {
      throw new ChatApiError('无法读取后端流式响应。');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalResponse: ChatResponse | null = null;

    const handleFrame = (frame: SseFrame) => {
      const payload = parseStreamPayload(frame);

      if (frame.event === 'token') {
        const delta = typeof payload.delta === 'string' ? payload.delta : '';
        if (delta) {
          options.onToken?.(delta);
        }
        return;
      }

      if (frame.event === 'status') {
        const stage = typeof payload.stage === 'string' ? payload.stage : '';
        if (stage) {
          options.onStatus?.(stage);
        }
        return;
      }

      if (frame.event === 'done') {
        finalResponse = normalizeChatResponse(payload as ChatResponse);
        return;
      }

      if (frame.event === 'error') {
        const message =
          typeof payload.message === 'string' ? payload.message : '后端流式处理失败。';
        throw new ChatApiError(message);
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      refreshTimeout();
      buffer += decoder.decode(value, { stream: !done });

      const parsed = splitSseFrames(buffer);
      buffer = parsed.remaining;
      for (const frame of parsed.frames) {
        handleFrame(frame);
      }

      if (done) {
        break;
      }
    }

    if (buffer.trim()) {
      const finalFrame = parseSseFrame(buffer);
      if (finalFrame) {
        handleFrame(finalFrame);
      }
    }

    if (!finalResponse) {
      throw new ChatApiError('流式响应提前结束，未返回最终结果。');
    }

    return finalResponse;
  } catch (error) {
    if (error instanceof ChatApiError) {
      throw error;
    }

    if (error instanceof DOMException && error.name === 'AbortError') {
      const abortReason =
        typeof requestController.signal.reason === 'string'
          ? requestController.signal.reason
          : 'cancelled';

      if (abortReason === 'timeout') {
        throw new ChatApiError('后端处理超时，请查看后端窗口日志，或稍后重试。');
      }

      throw new ChatRequestCancelledError();
    }

    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new ChatApiError('无法连接到后端服务，请确认 `http://localhost:8000` 已启动。');
    }

    throw new ChatApiError('发送消息失败，请稍后重试。');
  } finally {
    window.clearTimeout(timeoutId);
    if (options.signal) {
      options.signal.removeEventListener('abort', handleExternalAbort);
    }
  }
}
