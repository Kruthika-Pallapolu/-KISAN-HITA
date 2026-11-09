export interface AssistantChatPayload {
  message: string;
  conversation_id: string;
  language: string;
  farm_context?: Record<string, unknown>;
}

export class AssistantHttpError extends Error {
  readonly status: number;
  readonly detail?: string;

  constructor(status: number, detail?: string) {
    super(`Assistant request returned HTTP ${status}`);
    this.name = 'AssistantHttpError';
    this.status = status;
    this.detail = detail;
  }
}

export class AssistantResponseError extends Error {
  constructor() {
    super('Assistant response did not contain a usable reply');
    this.name = 'AssistantResponseError';
  }
}

export async function requestAssistantReply(
  payload: AssistantChatPayload,
  fetcher: typeof fetch = fetch,
): Promise<Record<string, any>> {
  const response = await fetcher('/api/assistant/chat', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new AssistantHttpError(response.status, typeof body?.detail === 'string' ? body.detail : undefined);
  }

  const data = await response.json();
  if (!data || typeof data.reply_text !== 'string' || !data.reply_text.trim()) throw new AssistantResponseError();
  return data;
}
