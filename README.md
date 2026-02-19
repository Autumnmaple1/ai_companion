# AI Companion 智能伴侣项目

本项目是一个集成了语音识别 (ASR)、大语言模型 (LLM)、长短期记忆管理 (Letta/MemGPT) 以及语音合成 (TTS) 的智能交互伴侣。通过 Live2D 技术提供生动的视觉形象，旨在构建一个具有持久记忆和情感表达能力的数字生命。

## 1. 项目主要功能

*   **实时语音对话**：支持通过麦克风进行语音输入，系统自动识别并生成带有情感的回复。
*   **长短期记忆系统**：集成 Letta (原 MemGPT) 框架，使用 PostgreSQL 和 pgvector 存储对话历史，使角色具备长期记忆。
*   **高品质语音合成**：采用 GPT-SoVITS 技术，支持特定角色的克隆语音输出，还原真实听感。
*   **可视化 Live2D 交互**：前端使用 PixiJS 驱动 Live2D 模型，根据回复内容展示不同的表情和动作。
*   **多阶段流式处理**：从语音识别到文本生成再到语音合成采用异步流式架构，降低交互延迟。

## 2. 快速开始

### 环境要求

*   操作系统：Windows (建议使用 PowerShell)
*   显卡：NVIDIA GPU (支持 CUDA)
*   软件依赖：Docker Desktop, Python 3.10+, Node.js 18+, Conda (可选)

### 部署步骤

1.  **启动基础服务**
    确保已安装 NVIDIA Container Toolkit，然后在项目根目录运行：
    ```powershell
    docker-compose up -d
    ```
    这将启动 PostgreSQL 数据库、Letta 服务器和 GPT-SoVITS API 服务。

2.  **配置 Python 环境**
    创建并激活虚拟环境，安装必要依赖：
    ```powershell
    # 安装项目核心依赖
    pip install -r requirements.txt
    ```

3.  **初始化记忆体**
    运行脚本以在 Letta 中创建并初始化角色：
    ```powershell
    python scripts/init_letta.py
    ```

4.  **启动项目**
    执行根目录下的启动脚本，它将同时启动后端 API 和前端开发服务器：
    ```powershell
    ./start.bat
    ```

## 3. 如何配置

核心配置位于 [backend/config.py](backend/config.py)，建议通过 `.env` 文件进行本地化定制：

### 核心参数
*   **LETTA_URL**：默认 `http://localhost:8283`。
*   **LETTA_AGENT_ID**：运行 `python scripts/init_letta.py` 会生成该 ID，请将其填入 `.env` 或 `config.py` 中以启用关联记忆。
*   **DASHSCOPE_API_KEY**：通义千问的 API Key，必填以支持对话逻辑。
*   **ASR_MODEL_SIZE**：默认 `base`，可选 `tiny`, `small`, `medium`, `large-v3` (根据显存大小调整)。
*   **GPT_SOVITS_URL**：语音合成 API 接口。

### 角色定制
在 [backend/characters/](backend/characters/) 目录下创建或修改 JSON 配置文件。你可以在其中定义：
*   角色的生存法则 (System Prompt)
*   初始人类伴侣记忆 (Persona)
*   情感标签与 TTS 声音权重的映射关系

## 4. 各组分说明

### 项目目录结构
```text
ai_companion/
├── ai_modules/         # AI 核心模块 (ASR, LLM, TTS 适配器)
├── backend/            # FastAPI 后端实现
│   ├── characters/     # 角色配置文件 (JSON)
│   └── core/           # 核心逻辑与流式处理器
├── frontend/           # React + Vite 前端代码
├── scripts/            # 初始化与数据维护脚本
├── docker-compose.yml  # 基础设施容器编排
└── start.bat           # 一键启动脚本
```

### 后端 (Backend)
基于 FastAPI 构建。负责调度 ASR 转换、向 Letta 发送请求并获取推理结果、管理语音合成队列以及维护与前端的 WebSocket 通信。

### 前端 (Frontend)
基于 React 和 Vite 开发。核心组件包括：
*   **Live2DViewer**：负责模型的加载、动画控制以及音频同步。
*   **音频采集模块**：通过 Web Audio API 采集用户语音并实时传输至后端。

### AI 模块 (AI Modules)
*   **ASR (Faster-Whisper)**：本地运行的高性能语音识别模块。
*   **LLM 适配器**：对接通义千问 API，并作为 Letta 的后端生成引擎。
*   **TTS (GPT-SoVITS)**：负责将文本转化为极具表现力的角色声音。

### 存储层
*   **PostgreSQL + pgvector**：用于存储 Letta Agent 的回忆录、知识库以及会话状态，支持向量检索。

## 5. 感谢开源社区

本项目依赖于多个优秀的开源项目，向以下开发者及其社区表示诚挚感谢：

*   **GPT-SoVITS**：优秀的少样本语音转换与合成框架。
*   **Letta (MemGPT)**：为大模型提供长期记忆和复杂状态管理的架构。
*   **Faster-Whisper**：Whisper 模型的高效实现。
*   **PixiJS & pixi-live2d-display**：强大的 Web 2D 渲染引擎。
*   **Aliyun DashScope**：提供高性能的基础语言模型能力。
*   **Live2D Cubism SDK**：提供核心的模型驱动技术。
