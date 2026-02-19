/**
 * 聊天面板组件
 * 显示消息列表和输入框
 */
import { useState, useRef, useEffect } from 'react';
import { useChat } from '../contexts/ChatContext';
import './ChatPanel.css';

export default function ChatPanel() {
  const {
    messages,
    activeSessionId,
    isLoading,
    sendMessage,
    sendAudioMessage,
    stopAudio,
  } = useChat();

  const [inputValue, setInputValue] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const messageListRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  // 自动滚动到底部
  useEffect(() => {
    if (messageListRef.current) {
      messageListRef.current.scrollTop = messageListRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = () => {
    if (!inputValue.trim()) return;
    stopAudio();
    sendMessage(inputValue);
    setInputValue('');
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorderRef.current.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        const reader = new FileReader();
        reader.readAsDataURL(audioBlob);
        reader.onloadend = () => {
          const base64String = reader.result.split(',')[1];
          sendAudioMessage(base64String);
        };
        // 停止所有音轨
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorderRef.current.start();
      stopAudio();
      setIsRecording(true);
    } catch (err) {
      console.error('获取麦克风失败:', err);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  // 清理消息内容（移除 emo 标签及其后可能跟随的标点符号）
  const cleanContent = (content) => {
    let cleaned = content.replace(/\[emo:\w+\]\s*[!?！？。，、~]*/g, '');
    // 移除句首残留的标点
    cleaned = cleaned.replace(/^[!?！？。，、~\s]+/, '');
    return cleaned.trim();
  };

  return (
    <div className="chat-panel">
      {/* 消息列表 */}
      <div className="message-list" ref={messageListRef}>
        {!activeSessionId && messages.length === 0 && (
          <div className="welcome-message">
            <h3>👋 欢迎回来！</h3>
            <p>选择一个对话或开始新的对话</p>
          </div>
        )}
        
        {isLoading && (
          <div className="loading-indicator">
            <span className="loading-dot"></span>
            <span className="loading-dot"></span>
            <span className="loading-dot"></span>
          </div>
        )}
        
        {messages.map((msg, index) => (
          <div key={msg.id || index} className={`message ${msg.role}`}>
            <div className="message-avatar">
              {msg.role === 'user' ? '👤' : '🤖'}
            </div>
            <div className="message-content">
              <div className="message-bubble">
                {cleanContent(msg.content)}
                {msg.isStreaming && <span className="streaming-cursor">▌</span>}
              </div>
              {msg.emotion && (
                <span className="emotion-tag">{msg.emotion}</span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* 输入区域 */}
      <div className="input-area">
        <input
          type="text"
          placeholder={activeSessionId ? "输入消息..." : "请先选择或创建对话"}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyPress}
          disabled={!activeSessionId && messages.length === 0}
        />
        
        <button
          className={`icon-btn mic-btn ${isRecording ? 'recording' : ''}`}
          onClick={isRecording ? stopRecording : startRecording}
          title={isRecording ? '停止录音' : '开始录音'}
        >
          <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
          </svg>
        </button>
        
        <button className="send-btn" onClick={handleSend} disabled={!inputValue.trim()}>
          发送
        </button>
      </div>
    </div>
  );
}
