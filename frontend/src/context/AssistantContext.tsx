import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import { useLanguage } from './LanguageContext';
import { useFarmProfile } from './FarmProfileContext';
import { SpeechService } from '../services/speech';
import { ensureBrowserSession } from '../services/session';
import { AsyncSerialQueue } from '../services/asyncSerialQueue';
import { createNonSecurityUuid, getOrCreateConversationId as getStoredConversationId } from '../services/nonSecurityIds';
import { AssistantHttpError, AssistantResponseError, requestAssistantReply } from '../services/assistantChatApi';
import { PrismaManualRecorder, uploadPrismaRecording } from '../services/prismaRecording';

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  intent?: string;
  feature?: string;
  metadata?: any;
  timestamp: string;
}

export interface AssistantSpeechCallbacks {
  onSpeakingStart?: () => void;
  onSpeakingEnd?: () => void;
  onSpeakingError?: () => void;
  onAssistantReply?: (pendingWorkflow: string | null, replyText: string) => void;
}

export interface AssistantSendOptions extends AssistantSpeechCallbacks {}

interface AssistantContextType {
  isOpen: boolean;
  openAssistant: () => void;
  closeAssistant: () => void;
  toggleAssistant: () => void;
  messages: ChatMessage[];
  sendMessage: (text: string, onRoute?: (feature: string) => void, options?: AssistantSendOptions) => Promise<void>;
  clearMessages: () => void;
  isProcessing: boolean;
  isSpeaking: boolean;
  currentTranscript: string;
  voiceError: string;
  isPrismaRecording: boolean;
  startPrismaVoiceInput: () => Promise<void>;
  stopPrismaVoiceInput: () => Promise<void>;
  speakText: (text: string, callbacks?: AssistantSpeechCallbacks) => void;
  stopSpeaking: (notifyOnEnd?: boolean) => void;
  suggestedQuestions: string[];
  pendingWorkflow: string | null;
  nextSlot: string | null;
  lastCollectedSlots: Record<string, any>;
}

const AssistantContext = createContext<AssistantContextType | undefined>(undefined);

function getConversationId(isGuest: boolean, guestContextId: string | null): string {
  const storage = isGuest ? window.sessionStorage : window.localStorage;
  const guestScope = (guestContextId || 'new').replace(/[^a-zA-Z0-9_-]/g, '');
  const key = isGuest ? `kisan_hita_guest_${guestScope}_conversation_id` : 'kisan_hita_conversation_id';
  return getStoredConversationId(storage, key);
}

export const AssistantProvider: React.FC<{ children: React.ReactNode; isGuest?: boolean; guestContextId?: string | null }> = ({ children, isGuest = false, guestContextId = null }) => {
  const { language, t } = useLanguage();
  const { profile, updateProfile } = useFarmProfile();
  const storage = isGuest ? window.sessionStorage : window.localStorage;
  const guestScope = (guestContextId || 'new').replace(/[^a-zA-Z0-9_-]/g, '');
  const storageKeys = isGuest
    ? { messages: `kisan_hita_guest_${guestScope}_chat_messages`, conversation: `kisan_hita_guest_${guestScope}_conversation_id`, pending: `kisan_hita_guest_${guestScope}_pending_wf`, next: `kisan_hita_guest_${guestScope}_next_slot`, collected: `kisan_hita_guest_${guestScope}_collected_slots` }
    : { messages: 'kisan_hita_chat_messages', conversation: 'kisan_hita_conversation_id', pending: 'kisan_hita_pending_wf', next: 'kisan_hita_next_slot', collected: 'kisan_hita_collected_slots' };
  const [conversationId, setConversationId] = useState<string>(() => getConversationId(isGuest, guestContextId));

  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [pendingWorkflow, setPendingWorkflow] = useState<string | null>(() => {
    return storage.getItem(storageKeys.pending) || null;
  });
  const [nextSlot, setNextSlot] = useState<string | null>(() => {
    return storage.getItem(storageKeys.next) || null;
  });
  const [lastCollectedSlots, setLastCollectedSlots] = useState<Record<string, any>>(() => {
    try {
      const saved = storage.getItem(storageKeys.collected);
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    try {
      const saved = storage.getItem(storageKeys.messages);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch {}
    return [
      {
        id: 'msg_initial',
        sender: 'assistant',
        text: t('assistantGreeting'),
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ];
  });

  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [isSpeaking, setIsSpeaking] = useState<boolean>(false);
  const [currentTranscript, setCurrentTranscript] = useState<string>('');
  const [voiceError, setVoiceError] = useState<string>('');
  const [isPrismaRecording, setIsPrismaRecording] = useState(false);
  const prismaRecorderRef = useRef<PrismaManualRecorder | null>(null);
  const prismaTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prismaRunRef = useRef(0);
  const messageQueueRef = useRef(new AsyncSerialQueue());

  // Persist messages and workflow state to localStorage so they survive browser refresh
  useEffect(() => {
    try {
      storage.setItem(storageKeys.messages, JSON.stringify(messages));
    } catch {}
  }, [messages, isGuest]);

  useEffect(() => {
    if (pendingWorkflow) {
      storage.setItem(storageKeys.pending, pendingWorkflow);
    } else {
      storage.removeItem(storageKeys.pending);
    }
  }, [pendingWorkflow, isGuest]);

  useEffect(() => {
    if (nextSlot) {
      storage.setItem(storageKeys.next, nextSlot);
    } else {
      storage.removeItem(storageKeys.next);
    }
  }, [nextSlot, isGuest]);

  useEffect(() => {
    try {
      storage.setItem(storageKeys.collected, JSON.stringify(lastCollectedSlots));
    } catch {}
  }, [lastCollectedSlots, isGuest]);

  // Update initial greeting if language changes and conversation only has 1 message
  useEffect(() => {
    setMessages((prev) => {
      if (prev.length <= 1) {
        return [
          {
            id: 'msg_initial',
            sender: 'assistant',
            text: t('assistantGreeting'),
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ];
      }
      return prev;
    });
  }, [language]);

  const openAssistant = () => setIsOpen(true);
  const closeAssistant = () => {
    setIsOpen(false);
    prismaRunRef.current += 1;
    if (prismaRecorderRef.current) {
      prismaRecorderRef.current.cancel();
      prismaRecorderRef.current = null;
      if (prismaTimerRef.current) clearTimeout(prismaTimerRef.current);
      prismaTimerRef.current = null;
      setIsPrismaRecording(false);
    }
    stopSpeaking(true);
  };
  const toggleAssistant = () => {
    if (isOpen) {
      closeAssistant();
    } else {
      openAssistant();
    }
  };

  const speakText = (text: string, callbacks: AssistantSpeechCallbacks = {}) => {
    setIsSpeaking(false);
    setVoiceError('');
    SpeechService.speak(
      text,
      language,
      () => {
        setIsSpeaking(true);
        callbacks.onSpeakingStart?.();
      },
      () => {
        setIsSpeaking(false);
        callbacks.onSpeakingEnd?.();
      },
      (error) => {
        setIsSpeaking(false);
        setVoiceError(t('voicePlaybackFailed'));
        console.warn('Speech playback failed:', error);
        callbacks.onSpeakingError?.();
      }
    );
  };

  const stopSpeaking = (notifyOnEnd = false) => {
    SpeechService.stop(notifyOnEnd);
    setIsSpeaking(false);
  };

  const startPrismaVoiceInput = async () => {
    if (prismaRecorderRef.current || isPrismaRecording) return;
    const runId = ++prismaRunRef.current;
    stopSpeaking(true);
    setVoiceError('');
    try {
      const recorder = new PrismaManualRecorder();
      await recorder.start();
      if (runId !== prismaRunRef.current) { recorder.cancel(); return; }
      prismaRecorderRef.current = recorder;
      setIsPrismaRecording(true);
      prismaTimerRef.current = setTimeout(() => { void stopPrismaVoiceInput(); }, 29_700);
    } catch (error) {
      if (runId !== prismaRunRef.current) return;
      const message = `${(error as { name?: string })?.name || ''} ${(error as { message?: string })?.message || ''}`;
      setVoiceError(/NotAllowed|Permission|denied|SecurityError/i.test(message)
        ? t('voicePrismaPermissionDenied')
        : /format|recording is not supported/i.test(message)
          ? t('voicePrismaUnsupported')
          : t('voicePrismaFailed'));
    }
  };

  const stopPrismaVoiceInput = async () => {
    const runId = prismaRunRef.current;
    const recorder = prismaRecorderRef.current;
    if (!recorder) return;
    prismaRecorderRef.current = null;
    if (prismaTimerRef.current) clearTimeout(prismaTimerRef.current);
    prismaTimerRef.current = null;
    setIsPrismaRecording(false);
    try {
      const recording = await recorder.stop();
      const transcript = await uploadPrismaRecording(recording, language);
      if (runId !== prismaRunRef.current) return;
      setCurrentTranscript(transcript);
      await sendMessage(transcript);
    } catch (error) {
      recorder.cancel();
      if (runId !== prismaRunRef.current) return;
      const message = (error as { message?: string })?.message || '';
      setVoiceError(/30 seconds|too long/i.test(message)
        ? t('voicePrismaTooLong')
        : /WebM|format|unsupported/i.test(message)
          ? t('voicePrismaUnsupported')
          : t('voicePrismaFailed'));
    }
  };

  useEffect(() => () => {
    prismaRunRef.current += 1;
    prismaRecorderRef.current?.cancel();
    if (prismaTimerRef.current) clearTimeout(prismaTimerRef.current);
  }, []);

  const processMessage = async (text: string, onRoute?: (feature: string) => void, options: AssistantSendOptions = {}) => {
    const trimmed = text.trim();
    if (!trimmed) {
      options.onSpeakingError?.();
      return;
    }

    const userMsg: ChatMessage = {
      id: `user_${createNonSecurityUuid()}`,
      sender: 'user',
      text: trimmed,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsProcessing(true);
    setCurrentTranscript('');

    try {
      await ensureBrowserSession();
      const data = await requestAssistantReply({
          message: trimmed,
          conversation_id: conversationId,
          language,
          farm_context: {
            ...(profile.district ? { district: profile.district } : {}),
            ...(profile.state ? { state: profile.state } : {}),
            ...(profile.soilType ? { soil_type: profile.soilType } : {}),
            ...(profile.waterSource ? { water_source: profile.waterSource } : {}),
          },
        });
      if (typeof data.conversation_id === 'string' && data.conversation_id !== conversationId) {
        setConversationId(data.conversation_id);
        try {
          storage.setItem(storageKeys.conversation, data.conversation_id);
        } catch {}
      }
      const assistantMsg: ChatMessage = {
        id: `ast_${createNonSecurityUuid()}`,
        sender: 'assistant',
        text: data.reply_text,
        intent: data.intent,
        feature: data.routed_feature,
        metadata: data.feature_data,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, assistantMsg]);

      // Synchronize collected slots to farm profile
      if (data.collected_slots) {
        const updates: any = {};
        if (data.collected_slots.district) updates.district = data.collected_slots.district;
        if (data.collected_slots.soil_type) updates.soilType = data.collected_slots.soil_type;
        if (data.collected_slots.water_source) updates.waterSource = data.collected_slots.water_source;
        if (data.collected_slots.commodity) updates.selectedCommodity = data.collected_slots.commodity;
        if (data.collected_slots.crop_name) updates.selectedCropHealthName = data.collected_slots.crop_name;
        if (data.collected_slots.symptoms) updates.selectedSymptoms = data.collected_slots.symptoms;
        if (Object.keys(updates).length > 0) {
          updateProfile(updates);
        }
      }

      setPendingWorkflow(data.pending_workflow || null);
      setNextSlot(data.next_slot || null);
      setLastCollectedSlots(data.collected_slots || {});
      options.onAssistantReply?.(data.pending_workflow || null, data.reply_text);

      // Automatically speak the response if voice is active or user preference
      speakText(data.reply_text, options);

      // Trigger feature navigation only when workflow is complete and route callback provided
      if (data.routed_feature && !data.pending_workflow && onRoute) {
        onRoute(data.routed_feature);
      }
    } catch (err) {
      if (err instanceof AssistantHttpError) {
        console.error('Assistant API request failed:', { status: err.status, detail: err.detail });
      } else {
        console.error('Assistant transport or response error:', err);
      }
      const fallbackReply = err instanceof AssistantResponseError
        ? t('assistantResponseInvalid')
        : err instanceof AssistantHttpError
        ? err.status === 403 && err.detail === 'Untrusted request origin'
          ? t('assistantOriginRejected')
          : t('assistantRequestFailed').replace('{status}', String(err.status))
        : t('voiceServerUnavailable');
      setMessages((prev) => [
        ...prev,
        {
          id: `ast_err_${createNonSecurityUuid()}`,
          sender: 'assistant',
          text: fallbackReply,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
      options.onSpeakingError?.();
    } finally {
      setIsProcessing(false);
    }
  };

  // Clicks, voice recognition callbacks, and keyboard submits can arrive
  // before React renders the updated isProcessing state. Queue each submitted
  // question so every intentional question gets its own ordered API request.
  const sendMessage = (text: string, onRoute?: (feature: string) => void, options: AssistantSendOptions = {}) => {
    // An explicit typed/suggested question wins over an unfinished manual
    // capture. Invalidate its callbacks before stopping so its late `onend`
    // cannot append a second message or reuse old transcript text.
    return messageQueueRef.current.enqueue(() => processMessage(text, onRoute, options));
  };

  const clearMessages = () => {
    stopSpeaking(true);
    const previousConversationId = conversationId;
    const nextConversationId = `conv_${createNonSecurityUuid().replace(/-/g, '')}`;
    try {
      storage.setItem(storageKeys.conversation, nextConversationId);
    } catch {}
    setConversationId(nextConversationId);
    setPendingWorkflow(null);
    setNextSlot(null);
    setLastCollectedSlots({});
    try {
      storage.removeItem(storageKeys.messages);
      storage.removeItem(storageKeys.pending);
      storage.removeItem(storageKeys.next);
      storage.removeItem(storageKeys.collected);
    } catch {}
    setMessages([
      {
        id: 'msg_initial',
        sender: 'assistant',
        text: t('assistantGreeting'),
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
    ensureBrowserSession()
      .then(() => fetch(`/api/assistant/clear/${previousConversationId}`, { method: 'POST', credentials: 'same-origin' }))
      .catch(() => {});
  };

  const suggestedQuestions =
    language === 'te'
      ? [
          'రేపు వర్షం పడుతుందా? నీరు పెట్టవచ్చా?',
          'నల్ల రేగడి నేలలో ఏ పంట వేయాలి?',
          'గుంటూరు మిర్చి మార్కెట్ ధర ఎంత?',
          'పత్తి ఆకులు పసుపు రంగులోకి మారుతున్నాయి',
        ]
      : [
          'How can I improve soil health before sowing?',
          'Which crop suits black cotton soil?',
          'Check current chilli mandi price',
          'Cotton leaves are turning yellow with spots',
        ];

  return (
    <AssistantContext.Provider
      value={{
        isOpen,
        openAssistant,
        closeAssistant,
        toggleAssistant,
        messages,
        sendMessage,
        clearMessages,
        isProcessing,
        isSpeaking,
        currentTranscript,
        voiceError,
        isPrismaRecording,
        startPrismaVoiceInput,
        stopPrismaVoiceInput,
        speakText,
        stopSpeaking,
        suggestedQuestions,
        pendingWorkflow,
        nextSlot,
        lastCollectedSlots,
      }}
    >
      {children}
    </AssistantContext.Provider>
  );
};

export const useAssistant = () => {
  const ctx = useContext(AssistantContext);
  if (!ctx) throw new Error('useAssistant must be used within AssistantProvider');
  return ctx;
};

