/**
 * ChatContext - 聊天状态管理
 * 管理会话列表、当前会话、消息等状态
 */
import { createContext, useContext, useReducer, useEffect, useCallback, useRef } from 'react';
import wsService from '../services/websocket';

// ==================== 状态定义 ====================

const initialState = {
  // 连接状态
  isConnected: false,
  isConnecting: false,
  
  // 用户
  userId: localStorage.getItem('ai_companion_user_id') || 'guest',
  
  // 会话
  sessions: [],
  activeSessionId: null,
  
  // 消息
  messages: [],
  
  // UI 状态
  isLoading: false,
  currentEmotion: null,
  error: null,
};


// ==================== Action Types ====================

const ActionTypes = {
  // 连接
  SET_CONNECTING: 'SET_CONNECTING',
  SET_CONNECTED: 'SET_CONNECTED',
  SET_DISCONNECTED: 'SET_DISCONNECTED',
  
  // 用户
  SET_USER_ID: 'SET_USER_ID',
  
  // 会话
  SET_SESSIONS: 'SET_SESSIONS',
  SET_ACTIVE_SESSION: 'SET_ACTIVE_SESSION',
  ADD_SESSION: 'ADD_SESSION',
  REMOVE_SESSION: 'REMOVE_SESSION',
  LOAD_SESSION_MESSAGES: 'LOAD_SESSION_MESSAGES',
  
  // 消息
  ADD_USER_MESSAGE: 'ADD_USER_MESSAGE',
  START_ASSISTANT_MESSAGE: 'START_ASSISTANT_MESSAGE',
  APPEND_STREAM_DELTA: 'APPEND_STREAM_DELTA',
  FINISH_ASSISTANT_MESSAGE: 'FINISH_ASSISTANT_MESSAGE',
  CLEAR_MESSAGES: 'CLEAR_MESSAGES',
  
  // UI
  SET_LOADING: 'SET_LOADING',
  SET_EMOTION: 'SET_EMOTION',
  SET_ERROR: 'SET_ERROR',
};


// ==================== Reducer ====================

function chatReducer(state, action) {
  switch (action.type) {
    case ActionTypes.SET_CONNECTING:
      return { ...state, isConnecting: true, error: null };
    
    case ActionTypes.SET_CONNECTED:
      return { ...state, isConnected: true, isConnecting: false };
    
    case ActionTypes.SET_DISCONNECTED:
      return { ...state, isConnected: false, isConnecting: false };
    
    case ActionTypes.SET_USER_ID:
      localStorage.setItem('ai_companion_user_id', action.payload);
      return { ...state, userId: action.payload };
    
    case ActionTypes.SET_SESSIONS:
      return { ...state, sessions: action.payload };
    
    case ActionTypes.SET_ACTIVE_SESSION:
      return { ...state, activeSessionId: action.payload };
    
    case ActionTypes.ADD_SESSION:
      return { 
        ...state, 
        sessions: [action.payload, ...state.sessions],
        activeSessionId: action.payload.id
      };
    
    case ActionTypes.REMOVE_SESSION:
      return {
        ...state,
        sessions: state.sessions.filter(s => s.id !== action.payload),
        activeSessionId: state.activeSessionId === action.payload ? null : state.activeSessionId,
        messages: state.activeSessionId === action.payload ? [] : state.messages
      };
    
    case ActionTypes.LOAD_SESSION_MESSAGES:
      return { ...state, messages: action.payload, isLoading: false };
    
    case ActionTypes.ADD_USER_MESSAGE:
      return {
        ...state,
        messages: [...state.messages, {
          id: action.payload.id || `user-${Date.now()}`,
          role: 'user',
          content: action.payload.content,
          created_at: new Date().toISOString(),
        }]
      };
    
    case ActionTypes.START_ASSISTANT_MESSAGE:
      return {
        ...state,
        messages: [...state.messages, {
          id: action.payload.id || `assistant-${Date.now()}`,
          role: 'assistant',
          content: '',
          isStreaming: true,
          created_at: new Date().toISOString(),
        }]
      };
    
    case ActionTypes.APPEND_STREAM_DELTA: {
      const messages = [...state.messages];
      const lastMsg = messages[messages.length - 1];
      
      if (lastMsg && lastMsg.role === 'assistant' && lastMsg.isStreaming) {
        // 追加到现有流式消息
        messages[messages.length - 1] = {
          ...lastMsg,
          content: lastMsg.content + action.payload.delta
        };
      } else {
        // 创建新的助手消息
        messages.push({
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: action.payload.delta,
          isStreaming: true,
          created_at: new Date().toISOString(),
        });
      }
      
      return { ...state, messages };
    }
    
    case ActionTypes.FINISH_ASSISTANT_MESSAGE: {
      const messages = [...state.messages];
      const lastMsg = messages[messages.length - 1];
      
      if (lastMsg && lastMsg.role === 'assistant' && lastMsg.isStreaming) {
        messages[messages.length - 1] = {
          ...lastMsg,
          isStreaming: false,
          emotion: action.payload.emo,
          // 如果服务端返回了完整内容，可以用它替换
          content: action.payload.content || lastMsg.content
        };
      }
      
      return { 
        ...state, 
        messages,
        currentEmotion: action.payload.emo || state.currentEmotion
      };
    }
    
    case ActionTypes.CLEAR_MESSAGES:
      return { ...state, messages: [] };
    
    case ActionTypes.SET_LOADING:
      return { ...state, isLoading: action.payload };
    
    case ActionTypes.SET_EMOTION:
      return { ...state, currentEmotion: action.payload };
    
    case ActionTypes.SET_ERROR:
      return { ...state, error: action.payload, isLoading: false };
    
    default:
      return state;
  }
}


// ==================== Context ====================

const ChatContext = createContext(null);

export function ChatProvider({ children }) {
  const [state, dispatch] = useReducer(chatReducer, initialState);
  const audioRef = useRef(null);
  const playingMessageIdRef = useRef(null);

  // ========== WebSocket 事件处理 ==========

  useEffect(() => {
    // 连接状态
    const unsubConnected = wsService.on('connected', () => {
      dispatch({ type: ActionTypes.SET_CONNECTED });
    });

    const unsubDisconnected = wsService.on('disconnected', () => {
      dispatch({ type: ActionTypes.SET_DISCONNECTED });
    });

    // 会话创建
    const unsubSessionCreated = wsService.on('session_created', (data) => {
      dispatch({
        type: ActionTypes.ADD_SESSION,
        payload: {
          id: data.session_id,
          title: data.title || '新对话',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }
      });
    });

    // 会话加载
    const unsubSessionLoaded = wsService.on('session_loaded', (data) => {
      dispatch({ type: ActionTypes.SET_ACTIVE_SESSION, payload: data.session_id });
      dispatch({ type: ActionTypes.LOAD_SESSION_MESSAGES, payload: data.messages || [] });
    });

    // 会话列表
    const unsubSessionList = wsService.on('session_list', (data) => {
      dispatch({ type: ActionTypes.SET_SESSIONS, payload: data.sessions || [] });
    });

    // 会话删除
    const unsubSessionDeleted = wsService.on('session_deleted', (data) => {
      dispatch({ type: ActionTypes.REMOVE_SESSION, payload: data.session_id });
    });

    // 流式文本
    const unsubStream = wsService.on('stream', (data) => {
      dispatch({ type: ActionTypes.APPEND_STREAM_DELTA, payload: { delta: data.delta } });
    });

    // 流结束
    const unsubStreamEnd = wsService.on('stream_end', (data) => {
      dispatch({ 
        type: ActionTypes.FINISH_ASSISTANT_MESSAGE, 
        payload: { emo: data.emo, content: data.content }
      });
    });

    // 音频
    const unsubAudio = wsService.on('audio', (data) => {
      // 停止当前播放
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }

      const audio = new Audio(`data:audio/${data.format || 'wav'};base64,${data.data}`);
      audioRef.current = audio;
      
      audio.onended = () => {
        audioRef.current = null;
        playingMessageIdRef.current = null;
      };
      
      audio.play().catch(e => console.warn('音频播放失败:', e));
    });

    // 用户消息回显（语音转文字）
    const unsubUserEcho = wsService.on('user_message_echo', (data) => {
      dispatch({ type: ActionTypes.ADD_USER_MESSAGE, payload: { content: data.content } });
    });

    // 错误
    const unsubError = wsService.on('error', (data) => {
      console.error('[Chat Error]', data);
      dispatch({ type: ActionTypes.SET_ERROR, payload: data.message || '发生错误' });
    });

    // 清理
    return () => {
      unsubConnected();
      unsubDisconnected();
      unsubSessionCreated();
      unsubSessionLoaded();
      unsubSessionList();
      unsubSessionDeleted();
      unsubStream();
      unsubStreamEnd();
      unsubAudio();
      unsubUserEcho();
      unsubError();
    };
  }, []);

  // ========== Actions ==========

  /**
   * 连接并初始化
   */
  const connect = useCallback(async (userId) => {
    dispatch({ type: ActionTypes.SET_CONNECTING });
    
    if (userId && userId !== state.userId) {
      dispatch({ type: ActionTypes.SET_USER_ID, payload: userId });
    }
    
    try {
      await wsService.connect(userId || state.userId);
      // 连接后获取会话列表
      wsService.listSessions();
    } catch (error) {
      dispatch({ type: ActionTypes.SET_ERROR, payload: '连接失败' });
    }
  }, [state.userId]);

  /**
   * 切换用户
   */
  const switchUser = useCallback(async (newUserId) => {
    dispatch({ type: ActionTypes.CLEAR_MESSAGES });
    dispatch({ type: ActionTypes.SET_SESSIONS, payload: [] });
    dispatch({ type: ActionTypes.SET_ACTIVE_SESSION, payload: null });
    await connect(newUserId);
  }, [connect]);

  /**
   * 创建新会话
   */
  const createSession = useCallback(() => {
    dispatch({ type: ActionTypes.CLEAR_MESSAGES });
    wsService.newSession();
  }, []);

  /**
   * 切换会话
   */
  const switchSession = useCallback((sessionId) => {
    if (sessionId === state.activeSessionId) return;
    dispatch({ type: ActionTypes.SET_LOADING, payload: true });
    dispatch({ type: ActionTypes.CLEAR_MESSAGES });
    wsService.initSession(sessionId);
  }, [state.activeSessionId]);

  /**
   * 删除会话
   */
  const deleteSession = useCallback((sessionId) => {
    wsService.deleteSession(sessionId);
  }, []);

  /**
   * 发送消息
   */
  const sendMessage = useCallback((content) => {
    if (!content.trim()) return;
    
    // 如果没有活动会话，先创建一个
    if (!state.activeSessionId) {
      // 创建会话后会自动设置 activeSessionId
      wsService.newSession();
      // 稍后发送消息（等待会话创建完成）
      const unsubscribe = wsService.on('session_created', () => {
        dispatch({ type: ActionTypes.ADD_USER_MESSAGE, payload: { content } });
        wsService.chat(content);
        unsubscribe();
      });
      return;
    }
    
    // 停止当前音频
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    
    dispatch({ type: ActionTypes.ADD_USER_MESSAGE, payload: { content } });
    wsService.chat(content);
  }, [state.activeSessionId]);

  /**
   * 发送语音消息
   */
  const sendAudioMessage = useCallback((audioBase64) => {
    // 停止当前音频
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    
    wsService.chatAudio(audioBase64);
  }, []);

  /**
   * 停止音频播放
   */
  const stopAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
      playingMessageIdRef.current = null;
    }
  }, []);

  // ========== Context Value ==========

  const value = {
    // State
    ...state,
    
    // Actions
    connect,
    switchUser,
    createSession,
    switchSession,
    deleteSession,
    sendMessage,
    sendAudioMessage,
    stopAudio,
    
    // Refs (用于外部访问)
    audioRef,
  };

  return (
    <ChatContext.Provider value={value}>
      {children}
    </ChatContext.Provider>
  );
}

// ==================== Hook ====================

export function useChat() {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
}

export default ChatContext;
