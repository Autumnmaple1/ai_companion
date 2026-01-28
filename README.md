# AI Companion

这是一个基于 Web 技术和 Python 后端的 AI 伴侣项目。它结合了 React 前端（带有 Live2D 模型展示）和 Python FastAPI 后端，旨在提供能够进行语音和文本交互的虚拟形象。

## 项目结构

```
ai_companion/
├── ai_modules/         # AI 核心模块 (ASR, LLM, TTS)
├── backend/            # 后端服务器代码
├── frontend/           # 前端 React 项目
└── __pycache__/
```

## 功能特性

*   **实时流式对话**: LLM (Qwen-Turbo) 异步流式输出，打字机式视觉反馈。
*   **中英双语无缝切换**: 自动识别用户语言并即时切换语种与 TTS 发音。
*   **情绪驱动 Live2D**: AI 回复中自动注入表情标签（Happy/Sad等），驱动模型表情与口型。
*   **高保真语音合成**: 接入云端 GPT-SoVITS (Vertin 维尔汀模型)，支持自动播放。
*   **上下文管理**: 保留最近 10 轮对话记忆，对话更自然。

## 环境要求

### 后端 (Python)

建议使用 Conda 环境：

```bash
pip install fastapi uvicorn dashscope requests
```


### 前端 (Node.js)

需要 Node.js 环境（推荐 LTS 版本）。

## 快速开始

### 1. 启动后端

进入 `backend` 目录并运行服务器：

```bash
python backend\server.py
# 或者如果使用 uvicorn 命令行
# uvicorn server:app --reload
```

服务器默认运行在 `http://localhost:8000` (WebSocket 地址: `ws://localhost:8000/ws/chat`)。

### 2. 启动前端

进入 `frontend` 目录，安装依赖并启动开发服务器：

```bash
cd frontend
npm install
npm run dev
```

启动后，访问终端输出的本地地址（通常是 `http://localhost:5173`）即可看到应用界面。

## 模块说明

*   **backend/server.py**: FastAPI 服务器入口，处理 WebSocket 连接和消息分发。
*   **ai_modules/**:
    *   `ASR.py`: 语音转文字模块 (Automatic Speech Recognition)。
    *   `LLM.py`: 大语言模型交互模块 (Large Language Model)。
    *   `TTS.py`: 文字转语音模块 (Text-to-Speech)。
*   **frontend/src/Live2DViewer.jsx**: 负责加载和渲染 Live2D 模型组件。

## 注意事项

1.  **浏览器权限**: 初次进入页面需点击“开启语音互动”按钮，以解锁浏览器自动播放音频的权限。
2.  **API 配置**: 确保 `LLM.py` 中的 DashScope Key 有效，且 `TTS.py` 中的远程服务器地址已开启。
3.  **缓存**: 项目已清理 redundant 缓存，开发过程中建议保持环境整洁。

## 许可证

[待补充]
