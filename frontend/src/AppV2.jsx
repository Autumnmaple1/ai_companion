/**
 * AI Companion 主应用入口 v2
 * 使用 ChatContext 进行状态管理
 */
import { useState, useEffect } from 'react';
import { ChatProvider, useChat } from './contexts/ChatContext';
import { SessionSidebar, ChatPanel } from './components';
import Live2DViewer from './Live2DViewer';
import './App.css';

function AppContent() {
  const { connect, isConnected, isConnecting, currentEmotion, userId } = useChat();
  const [hasInteracted, setHasInteracted] = useState(false);
  const [isTalking, setIsTalking] = useState(false);

  // 初始化连接
  useEffect(() => {
    if (hasInteracted && !isConnected && !isConnecting) {
      connect(userId);
    }
  }, [hasInteracted, isConnected, isConnecting, connect, userId]);

  const handleStart = () => {
    setHasInteracted(true);
    // 播放一个无声片段来解锁浏览器音频
    const audio = new Audio("data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAAACAAIAAAABkYXRhAgAAAAEA");
    audio.play().catch(e => console.log("Init audio failed", e));
  };

  return (
    <div className="app-container" onClick={() => !hasInteracted && handleStart()}>
      {/* 首次交互遮罩 */}
      {!hasInteracted && (
        <div className="interaction-overlay">
          <button className="start-btn" onClick={handleStart}>
            点击开启 NOVA 语音互动
          </button>
        </div>
      )}

      {/* Live2D 角色 */}
      <Live2DViewer emotion={currentEmotion} isTalking={isTalking} />

      {/* 主布局 */}
      <div className="main-layout">
        {/* 会话侧边栏 */}
        <SessionSidebar />
        
        {/* 聊天面板 */}
        <ChatPanel />
      </div>
    </div>
  );
}

function App() {
  return (
    <ChatProvider>
      <AppContent />
    </ChatProvider>
  );
}

export default App;
