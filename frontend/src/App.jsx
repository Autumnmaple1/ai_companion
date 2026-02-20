import { useState, useEffect, useRef } from 'react'
import './App.css'
import Live2DViewer from './Live2DViewer';

function App() {
  const [messages, setMessages] = useState([]);
  const [currentEmotion, setCurrentEmotion] = useState("normal");
  const [config, setConfig] = useState(null);
  const ws = useRef(null);
  const [showLogs, setShowLogs] = useState(false);
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
  }, []);

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
              content: newMessages[existingIndex].content + audioObj.text + " "
            };
            return newMessages;
          } else {
            return [...prev, { role: 'ai', content: audioObj.text + " ", id: messageId }];
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
      ws.current.send(JSON.stringify({
        sender: "user",
        format: "text",
        content: inputValue,
        time: new Date().toISOString(),
        id: messageId
      }));
      setMessages(prev => [...prev, { role: "user", content: inputValue, id: messageId }]);
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
    <div className="app-container">
      <Live2DViewer
        currentEmotion={currentEmotion}
        audio={currentAudio}
        modelPath={config?.live2d?.model_path}
      />
      <div className="sidebar">
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
        <div className="message-list">
          {messages
            .filter(msg => showLogs ? msg.role === "system" : msg.role !== "system")
            .map((msg, index) => (
              <div
                key={index}
                className={`message-item ${msg.role}`}
                style={showLogs ? { fontSize: '12px', color: '#666', fontFamily: 'monospace' } : {}}
              >
                {msg.content}
              </div>
            ))}
          {messages.filter(msg => showLogs ? msg.role === "system" : msg.role !== "system").length === 0 && (
            <div style={{ textAlign: 'center', color: '#999', marginTop: '20px', fontSize: '12px' }}>
              {showLogs ? "暂无系统日志" : "暂无对话记录"}
            </div>
          )}
        </div>
      </div>
      <div className="main-area">
        <div className="input-area">
          <input
            type="text"
            placeholder={config ? `和${config.display_name}聊会儿吧...` : "和我说点什么吧..."}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyPress}
          />
          <button
            className={`icon-btn ${isRecording ? 'recording' : ''}`}
            onClick={isRecording ? stopRecording : startRecording}
            title={isRecording ? "停止录音" : "点击开始说话"}
          >
            <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
              <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
              <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
            </svg>
          </button>
          <button className="send-btn" onClick={handleSend} title={"单击或enter发送消息"}>
            发送
          </button>
        </div>
      </div>
    </div>
  )
}

export default App