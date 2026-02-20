import React, { useState, useEffect, useRef } from 'react'
import './App.css'
import Live2DViewer from './Live2DViewer';

function App() {
  const [messages, setMessages] = useState([]);
  const [currentEmotion, setCurrentEmotion] = useState("normal");
  const [config, setConfig] = useState(null);
  const ws = useRef(null);
  const listRef = useRef(null);
  const [showLogs, setShowLogs] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(420); // 记录手动调整的宽度
  const [isResizing, setIsResizing] = useState(false);
  const [hasMore, setHasMore] = useState(true);

  // 处理侧边栏拖拽调大小
  const startResizing = (e) => {
    e.preventDefault();
    setIsResizing(true);
  };

  const stopResizing = () => {
    setIsResizing(false);
  };

  const resize = (e) => {
    if (isResizing) {
      // 限制最小宽度和最大宽度（最大也别超过屏幕一半）
      const newWidth = Math.max(280, Math.min(e.clientX - 10, window.innerWidth * 0.7));
      setSidebarWidth(newWidth);
    }
  };

  useEffect(() => {
    if (isResizing) {
      window.addEventListener('mousemove', resize);
      window.addEventListener('mouseup', stopResizing);
      // 禁止文字选中，提升拖拽体验
      document.body.style.userSelect = 'none';
      document.body.style.cursor = 'col-resize';
    } else {
      window.removeEventListener('mousemove', resize);
      window.removeEventListener('mouseup', stopResizing);
      document.body.style.userSelect = 'auto';
      document.body.style.cursor = 'default';
    }
    return () => {
      window.removeEventListener('mousemove', resize);
      window.removeEventListener('mouseup', stopResizing);
    };
  }, [isResizing]);

  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorder = useRef(null);
  const audioChunks = useRef([]);
  const [currentAudio, setCurrentAudio] = useState(null);
  const audioQueue = useRef({}); // 改为对象以存储 index -> data
  const nextPlayIndex = useRef(0);
  const isPlaying = useRef(false);

  // 获取后端角色配置
  useEffect(() => {
    fetch("http://localhost:8000/config")
      .then(res => res.json())
      .then(data => {
        if (data.error) {
          console.error("加载配置失败:", data.error);
        } else {
          console.log("已加载角色配置:", data);
          setConfig(data);
        }
      })
      .catch(err => console.error("获取后端配置异常:", err));

    // 初始获取历史记录
    loadHistory();
  }, []);

  // 加载分页历史记录
  const loadHistory = async (before = null) => {
    if (isLoadingHistory || (!hasMore && before)) return;

    setIsLoadingHistory(true);
    const url = `http://localhost:8000/history?limit=20${before ? `&before=${before}` : ""}`;
    try {
      const res = await fetch(url);
      const data = await res.json();
      if (Array.isArray(data)) {
        if (data.length < 20) {
          setHasMore(false);
        }

        if (before) {
          // 向上加载更多，需要保持滚动位置
          const originalHeight = listRef.current?.scrollHeight || 0;
          setMessages(prev => [...data, ...prev]);

          // 加载完成后恢复滚动位置（会在渲染后处理）
          setTimeout(() => {
            if (listRef.current) {
              const newHeight = listRef.current.scrollHeight;
              listRef.current.scrollTop = newHeight - originalHeight;
            }
          }, 0);
        } else {
          // 初始加载，滚到底部
          setMessages(data);
          setTimeout(() => scrollToBottom(), 100);
        }
      }
    } catch (err) {
      console.error("加载历史失败:", err);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  // 监听滚动到顶部
  const handleScroll = (e) => {
    if (e.target.scrollTop === 0 && hasMore && !isLoadingHistory && !showLogs) {
      // 找到目前最早的一条聊天记录的时间（非系统日志）
      const chatMessages = messages.filter(m => m.role !== 'system');
      if (chatMessages.length > 0) {
        const oldestTimestamp = chatMessages[0].timestamp;
        loadHistory(oldestTimestamp);
      }
    }
  };

  // 自动滚动到底部
  const scrollToBottom = () => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  };

  // 监听消息更新自动滚到底部（仅限新消息进入时）
  useEffect(() => {
    // 如果消息变长且不是在加载历史，则滚动到底
    if (!isLoadingHistory && messages.length > 0) {
      scrollToBottom();
    }
  }, [messages, isLoadingHistory]);

  // 播放音频队列
  const playNextAudio = () => {
    if (isPlaying.current) return;

    const audioObj = audioQueue.current[nextPlayIndex.current];
    if (audioObj) {
      isPlaying.current = true;
      delete audioQueue.current[nextPlayIndex.current]; // 取出后删除

      // 【音画同步】在播放开始前同步显示文本和表情
      if (audioObj.text) {
        const messageId = audioObj.id || Date.now();
        setMessages(prev => {
          const existingIndex = prev.findIndex(m => m.id === messageId && m.role === 'ai');
          if (existingIndex !== -1) {
            const newMessages = [...prev];
            newMessages[existingIndex] = {
              ...newMessages[existingIndex],
              content: newMessages[existingIndex].content + audioObj.text + " ",
              timestamp: Date.now() // 更新时间戳为最后一段话的时间
            };
            return newMessages;
          } else {
            return [...prev, { role: 'ai', content: audioObj.text + " ", id: messageId, timestamp: Date.now() }];
          }
        });
      }

      if (audioObj.live2d_emotion) {
        // 直接使用小写的标签，匹配 LSS.model3.json 中的 Name 段
        const emotion = audioObj.live2d_emotion.toLowerCase();
        setCurrentEmotion(emotion);
      }

      const audio = new Audio(`data:audio/wav;base64,${audioObj.content}`);
      setCurrentAudio(audio);

      audio.onended = () => {
        isPlaying.current = false;
        setCurrentAudio(null);
        nextPlayIndex.current += 1; // 播放下一号
        playNextAudio();
      };

      audio.play().catch(err => {
        console.error("播放音频失败:", err);
        isPlaying.current = false;
        nextPlayIndex.current += 1;
        playNextAudio();
      });
    }
  };

  useEffect(() => {
    ws.current = new WebSocket("ws://localhost:8000/ws/chat");

    ws.current.onopen = () => {
      console.log("连接成功");
      setMessages(prev => [...prev, { role: "system", content: "WebSocket 连接已建立", id: Date.now() }]);
    };

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log("收到 WebSocket 数据:", data);

      if (data.type === 'message') {
        const messageId = data.id || Date.now();
        setMessages(prev => {
          // 检查是否已有该 ID 且 角色相同 的消息，如果有则追加内容
          const existingIndex = prev.findIndex(m => m.id === messageId && m.role === data.sender);
          if (existingIndex !== -1) {
            const newMessages = [...prev];
            newMessages[existingIndex] = {
              ...newMessages[existingIndex],
              content: data.mode === 'append' ? newMessages[existingIndex].content + data.content : data.content
            };
            return newMessages;
          } else {
            return [...prev, { role: data.sender, content: data.content, id: messageId }];
          }
        });

        if (data.live2d_emotion) {
          const emotion = data.live2d_emotion.toLowerCase();
          setCurrentEmotion(emotion);
        }
      }
      else if (data.type === 'voice') {
        // 按编号存入缓冲区，存储完整对象以同步文本
        audioQueue.current[data.index] = data;
        playNextAudio();
      }
    };
    ws.current.onclose = () => {
      console.log("连接关闭");
      setMessages(prev => [...prev, { role: "system", content: "WebSocket 连接已关闭" }]);
    }
    return () => {
      if (ws.current)
        ws.current.close();
    };
  }, []);

  const formatTime = (ts) => {
    if (!ts) return "";
    const date = new Date(Number(ts));
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  };

  const formatDateLabel = (ts) => {
    if (!ts) return "";
    const date = new Date(Number(ts));
    const now = new Date();

    // 如果是今年且是同一天
    if (date.toDateString() === now.toDateString()) {
      return "今天";
    }

    // 昨天
    const yesterday = new Date();
    yesterday.setDate(now.getDate() - 1);
    if (date.toDateString() === yesterday.toDateString()) {
      return "昨天";
    }

    // 跨年显示年份，否则只显示月日
    const options = date.getFullYear() === now.getFullYear()
      ? { month: 'long', day: 'numeric' }
      : { year: 'numeric', month: 'long', day: 'numeric' };

    return date.toLocaleDateString('zh-CN', options);
  };

  const handleSend = () => {
    if (currentAudio) {
      currentAudio.pause();
      setCurrentAudio(null);
    }
    audioQueue.current = {};
    nextPlayIndex.current = 0;
    isPlaying.current = false;

    if (!inputValue.trim()) return;
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      const messageId = Date.now();
      const timestamp = Date.now();
      ws.current.send(JSON.stringify({
        sender: "user",
        format: "text",
        content: inputValue,
        time: timestamp,
        id: messageId
      }));
      setMessages(prev => [...prev, { role: "user", content: inputValue, id: messageId, timestamp: timestamp }]);
      setInputValue("");
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      mediaRecorder.current = new MediaRecorder(stream);
      audioChunks.current = [];

      mediaRecorder.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.current.push(event.data);
        }
      };
      mediaRecorder.current.onstop = () => {
        const audioBlob = new Blob(audioChunks.current, { type: 'audio/wav' });
        const reader = new FileReader();
        reader.readAsDataURL(audioBlob);
        reader.onloadend = () => {
          const base64String = reader.result.split(',')[1];
          if (ws.current && ws.current.readyState === WebSocket.OPEN) {
            ws.current.send(JSON.stringify({
              sender: "user",
              type: "voice",
              format: "audio",
              content: base64String,
              time: new Date().toISOString()
            }));
            setMessages(prev => [...prev, { role: "system", content: "[语音消息已发送]" }]);
          }
        };
      };

      mediaRecorder.current.start();
      if (currentAudio) {
        currentAudio.pause();
        setCurrentAudio(null);
      }
      audioQueue.current = {};
      nextPlayIndex.current = 0;
      isPlaying.current = false;
      setIsRecording(true);
    }
    catch (err) {
      console.error("获取麦克风失败:", err);
    }
  };

  const stopRecording = () => {
    if (mediaRecorder.current && isRecording) {
      mediaRecorder.current.stop();
      setIsRecording(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') handleSend();
  };

  return (
    <div className={`app-container ${isSidebarOpen ? 'sidebar-open' : ''}`}>
      <Live2DViewer
        currentEmotion={currentEmotion}
        audio={currentAudio}
        modelPath={config?.live2d?.model_path}
      />
      <div
        className={`sidebar ${isSidebarOpen ? 'open' : ''} ${isResizing ? 'resizing' : ''}`}
        style={{ width: isSidebarOpen ? `${sidebarWidth}px` : '0' }}
      >
        <div className="sidebar-header">
          <div className="sidebar-title">
            {showLogs ? "系统日志" : "历史对话"}
          </div>
          <button
            className="icon-btn"
            onClick={() => setShowLogs(!showLogs)}
            title={showLogs ? "返回对话" : "查看日志"}
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
              <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z" />
            </svg>
          </button>
        </div>
        <div className="message-list" ref={listRef} onScroll={handleScroll}>
          {isLoadingHistory && (
            <div className="loading-history">加载历史记录中...</div>
          )}
          {!hasMore && !showLogs && messages.length > 10 && (
            <div className="no-more">—— 没有更多记录了 ——</div>
          )}
          {messages
            .filter(msg => showLogs ? msg.role === "system" : msg.role !== "system")
            .map((msg, index, array) => {
              const isFirstInGroup = index === 0 || array[index - 1].role !== msg.role;

              // 检查是否日期发生了跨变
              const showDateSeparator = index === 0 ||
                new Date(Number(array[index - 1].timestamp)).toDateString() !== new Date(Number(msg.timestamp)).toDateString();

              return (
                <React.Fragment key={msg.id || index}>
                  {showDateSeparator && !showLogs && msg.timestamp && (
                    <div className="date-separator">
                      <span>{formatDateLabel(msg.timestamp)}</span>
                    </div>
                  )}
                  <div className={`message-row ${msg.role} ${isFirstInGroup ? 'first-in-group' : 'consecutive'}`}>
                    {msg.role === 'ai' && !showLogs && (
                      <div className="avatar ai">
                        {isFirstInGroup ? (config?.display_name ? config.display_name[0] : 'A') : ''}
                      </div>
                    )}
                    <div className="message-wrapper">
                      {isFirstInGroup && !showLogs && msg.timestamp && (
                        <div className="message-time-top">{formatTime(msg.timestamp)}</div>
                      )}
                      <div
                        className={`message-item ${msg.role}`}
                        style={showLogs ? { fontSize: '12px', color: '#666', fontFamily: 'monospace' } : {}}
                      >
                        <div className="message-content">{msg.content}</div>
                      </div>
                    </div>
                    {msg.role === 'user' && !showLogs && (
                      <div className="avatar user">
                        {isFirstInGroup ? 'U' : ''}
                      </div>
                    )}
                  </div>
                </React.Fragment>
              );
            })}
          {messages.filter(msg => showLogs ? msg.role === "system" : msg.role !== "system").length === 0 && (
            <div style={{ textAlign: 'center', color: '#999', marginTop: '20px', fontSize: '12px' }}>
              {showLogs ? "暂无系统日志" : "暂无对话记录"}
            </div>
          )}
        </div>
        {isSidebarOpen && (
          <div className="resize-handle" onMouseDown={startResizing} />
        )}
      </div>
      <div className="main-area">
        <div className="input-area">
          <button
            className={`toggle-sidebar-btn ${isSidebarOpen ? 'active' : ''}`}
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            title={isSidebarOpen ? "关闭历史" : "打开历史"}
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
              <path d="M13 3c-4.97 0-9 4.03-9 9H1l3.89 3.89.07.14L9 12H6c0-3.87 3.13-7 7-7s7 3.13 7 7-3.13 7-7 7c-1.93 0-3.68-.79-4.94-2.06l-1.42 1.42C8.27 19.99 10.51 21 13 21c4.97 0 9-4.03 9-9s-4.03-9-9-9zm-1 5v5l4.28 2.54.72-1.18-3.5-2.08V8H12z" />
            </svg>
            <span className="btn-label">{isSidebarOpen ? "收起" : "历史"}</span>
          </button>
          <input
            type="text"
            placeholder={config ? `和${config.display_name}聊会儿吧...` : "和我说点什么吧..."}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyPress}
          />
          <button
            className={`action-btn mic-btn ${isRecording ? 'active recording' : ''}`}
            onClick={isRecording ? stopRecording : startRecording}
            title={isRecording ? "停止录音" : "点击开始说话"}
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
              <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
              <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
            </svg>
            <span className="btn-label">{isRecording ? "停止" : "语音"}</span>
          </button>
          <button className="action-btn send-btn primary" onClick={handleSend} title={"单击或enter发送消息"}>
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
            </svg>
            <span className="btn-label">发送</span>
          </button>
        </div>
      </div>
    </div>
  )
}

export default App