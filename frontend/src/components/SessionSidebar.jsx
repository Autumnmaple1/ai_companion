/**
 * 会话侧边栏组件
 * 显示会话列表，支持创建、切换、删除会话
 */
import { useChat } from '../contexts/ChatContext';
import './SessionSidebar.css';

// 用户选项配置
const USER_OPTIONS = [
  { value: 'nrx', label: 'NRX' },
  { value: 'hym', label: 'HYM' },
  { value: 'guest', label: '访客' }
];

export default function SessionSidebar() {
  const {
    userId,
    sessions,
    activeSessionId,
    isConnected,
    switchUser,
    createSession,
    switchSession,
    deleteSession,
  } = useChat();

  const handleUserChange = (e) => {
    switchUser(e.target.value);
  };

  const handleDeleteSession = (e, sessionId) => {
    e.stopPropagation(); // 阻止触发切换会话
    if (window.confirm('确定要删除这个会话吗？')) {
      deleteSession(sessionId);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();
    
    if (isToday) {
      return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    }
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
  };

  return (
    <div className="session-sidebar">
      {/* 头部 */}
      <div className="sidebar-header">
        <div className="header-top">

          <div className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
            {isConnected ? '已连接' : '未连接'}
          </div>
        </div>
        
        {/* 用户选择器 */}
        <div className="user-selector">

          <select value={userId} onChange={handleUserChange}>
            {USER_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
        
        {/* 新建会话按钮 */}
        <button className="new-session-btn" onClick={createSession}>
          <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
          </svg>
          新建对话
        </button>
      </div>
      
      {/* 会话列表 */}
      <div className="session-list">
        {sessions.length === 0 ? (
          <div className="empty-state">
            <p>暂无对话记录</p>
            <p className="hint">点击上方按钮开始新对话</p>
          </div>
        ) : (
          sessions.map(session => (
            <div
              key={session.id}
              className={`session-item ${session.id === activeSessionId ? 'active' : ''}`}
              onClick={() => switchSession(session.id)}
            >
              <div className="session-info">
                <div className="session-title">
                  {session.title || '新对话'}
                </div>
                <div className="session-meta">
                  <span className="session-date">{formatDate(session.updated_at)}</span>
                  {session.message_count > 0 && (
                    <span className="message-count">{session.message_count} 条消息</span>
                  )}
                </div>
              </div>
              <button
                className="delete-btn"
                onClick={(e) => handleDeleteSession(e, session.id)}
                title="删除对话"
              >
                <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
                  <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
                </svg>
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
