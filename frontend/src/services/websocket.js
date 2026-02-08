/**
 * WebSocket 服务模块
 * 处理与后端的 WebSocket 通信
 */

const WS_URL = 'ws://localhost:8000/ws/chat';

class WebSocketService {
  constructor() {
    this.ws = null;
    this.userId = null;
    this.listeners = new Map();
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 3000;
  }

  /**
   * 连接 WebSocket
   * @param {string} userId 用户 ID
   * @returns {Promise<void>}
   */
  connect(userId) {
    return new Promise((resolve, reject) => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        // 如果已连接且用户相同，直接返回
        if (this.userId === userId) {
          resolve();
          return;
        }
        // 用户变更，关闭旧连接
        this.ws.close();
      }

      this.userId = userId;
      const url = `${WS_URL}?user_id=${encodeURIComponent(userId)}`;
      
      console.log(`[WS] 正在连接: ${url}`);
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        console.log('[WS] 连接成功');
        this.reconnectAttempts = 0;
        this.emit('connected');
        resolve();
      };

      this.ws.onclose = (event) => {
        console.log(`[WS] 连接关闭: ${event.code} ${event.reason}`);
        this.emit('disconnected', { code: event.code, reason: event.reason });
        
        // 自动重连
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++;
          console.log(`[WS] ${this.reconnectDelay}ms 后尝试重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
          setTimeout(() => this.connect(this.userId), this.reconnectDelay);
        }
      };

      this.ws.onerror = (error) => {
        console.error('[WS] 连接错误:', error);
        this.emit('error', error);
        reject(error);
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.handleMessage(data);
        } catch (e) {
          console.error('[WS] 消息解析失败:', e);
        }
      };
    });
  }

  /**
   * 处理接收到的消息
   */
  handleMessage(data) {
    const { type } = data;
    // 触发对应类型的事件
    this.emit(type, data);
    // 同时触发通用消息事件
    this.emit('message', data);
  }

  /**
   * 发送消息
   */
  send(type, data = {}) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.error('[WS] 未连接，无法发送消息');
      return false;
    }

    const message = { type, ...data };
    console.log('[WS] 发送:', message);
    this.ws.send(JSON.stringify(message));
    return true;
  }

  /**
   * 初始化/加载会话
   */
  initSession(sessionId = null) {
    return this.send('init_session', sessionId ? { session_id: sessionId } : {});
  }

  /**
   * 创建新会话
   */
  newSession() {
    return this.send('new_session');
  }

  /**
   * 获取会话列表
   */
  listSessions() {
    return this.send('list_sessions');
  }

  /**
   * 删除会话
   */
  deleteSession(sessionId) {
    return this.send('delete_session', { session_id: sessionId });
  }

  /**
   * 发送聊天消息
   */
  chat(content) {
    return this.send('chat', { content });
  }

  /**
   * 发送语音消息
   */
  chatAudio(audioBase64) {
    return this.send('chat_audio', { audio: audioBase64 });
  }

  /**
   * 订阅事件
   */
  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);
    
    // 返回取消订阅函数
    return () => this.off(event, callback);
  }

  /**
   * 取消订阅
   */
  off(event, callback) {
    if (!this.listeners.has(event)) return;
    const callbacks = this.listeners.get(event);
    const index = callbacks.indexOf(callback);
    if (index > -1) {
      callbacks.splice(index, 1);
    }
  }

  /**
   * 触发事件
   */
  emit(event, data) {
    if (!this.listeners.has(event)) return;
    this.listeners.get(event).forEach(callback => {
      try {
        callback(data);
      } catch (e) {
        console.error(`[WS] 事件处理错误 (${event}):`, e);
      }
    });
  }

  /**
   * 断开连接
   */
  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * 获取连接状态
   */
  get isConnected() {
    return this.ws && this.ws.readyState === WebSocket.OPEN;
  }
}

// 导出单例
export const wsService = new WebSocketService();
export default wsService;
