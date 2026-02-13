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

*   **实时交互**: 使用 WebSocket 实现前后端实时通信。
*   **Live2D 展示**: 前端集成 `pixi-live2d-display`，能够在网页上展示并驱动 Live2D 模型。
*   **多模态输入/输出**:
    *   **文本对话**: 发送和接收文本消息。
    *   **语音交互**: 支持发送语音（录音），后端进行语音转文字 (ASR)。
    *   **语音合成**: 后端可将回复转换为语音 (TTS) 返回给前端播放。
*   **AI 智能**: 集成 LLM（大型语言模型）处理对话逻辑（目前模块可能处于测试/Mock 状态）。

## 环境要求

### 后端 (Python)

需要 Python 3.x 环境。建议安装以下依赖包：

```bash
pip install fastapi uvicorn websockets openai
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

*   目前的 AI 模块（`ai_modules`）中包含测试用的桩代码（Mock Data），例如返回固定的文本或音频。如需实际功能，请配置相应的 API Key 或本地模型路径。
*   Live2D 模型文件位于 `frontend/public/models/LSS/` 目录下。

## 许可证

[待补充]
