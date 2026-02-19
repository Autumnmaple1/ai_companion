import httpx
import json
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

LETTA_URL = os.getenv("LETTA_URL", "http://localhost:8083")
# 注意：在 docker-compose 中，letta 容器内部监听 8083，并映射到宿主机的 8083
# 如果脚本在宿主机运行，通常使用 localhost:8083

CHARACTER_NAME = os.getenv("CHARACTER_NAME", "yoimiya")


def init_letta_agent():
    # 1. 加载角色配置中的 system prompt
    char_config_path = f"backend/characters/{CHARACTER_NAME}.json"
    if not os.path.exists(char_config_path):
        print(f"Error: 找不到角色配置文件 {char_config_path}")
        return

    with open(char_config_path, "r", encoding="utf-8") as f:
        char_data = json.load(f)
        system_prompt = char_data["llm"]["system_prompt"]
        display_name = char_data.get("display_name", CHARACTER_NAME)

    # 2. 检查 agent 是否已存在
    try:
        print(f"尝试连接 Letta Server: {LETTA_URL} ...")
        response = httpx.get(f"{LETTA_URL}/v1/agents")
        if response.status_code == 200:
            agents = response.json().get("agents", [])
            for agent in agents:
                if agent["name"] == CHARACTER_NAME:
                    print(
                        f"Letta Agent '{CHARACTER_NAME}' 已经存在 (ID: {agent['id']})。"
                    )
                    save_agent_id(agent["id"])
                    return
        else:
            print(f"获取 Agents 列表失败: {response.status_code} - {response.text}")
            return

        # 3. 创建 Agent
        # 根据 docker-compose.yml 里的推荐配置
        create_payload = {
            "name": CHARACTER_NAME,
            "memory": {
                "persona": f"名字是 {display_name}。\n{system_prompt}",
                "human": "你是一个充满好奇心的用户。",
            },
            "llm_config": {
                "model": os.getenv("LLM_MODEL", "qwen3.5-plus"),
                "model_endpoint": os.getenv(
                    "DASHSCOPE_BASE_URL",
                    "https://dashscope.aliyuncs.com/compatible-mode/v1",
                ),
                "model_endpoint_type": "openai",
                "context_window": 32000,
            },
            "embedding_config": {
                "model": "text-embedding-v4",
                "model_endpoint": os.getenv(
                    "DASHSCOPE_BASE_URL",
                    "https://dashscope.aliyuncs.com/compatible-mode/v1",
                ),
                "model_endpoint_type": "openai",
                "dim": 1536,
            },
        }

        print(f"正在创建 Letta Agent '{CHARACTER_NAME}'...")
        create_resp = httpx.post(f"{LETTA_URL}/v1/agents", json=create_payload)
        if create_resp.status_code == 200 or create_resp.status_code == 201:
            agent_id = create_resp.json()["id"]
            print(f"成功创建 Letta Agent! ID: {agent_id}")
            save_agent_id(agent_id)
        else:
            print(f"创建失败: {create_resp.status_code} - {create_resp.text}")

    except Exception as e:
        print(f"连接失败: {e}")
        print("\n[请确认]:")
        print("1. 已运行 'docker-compose up -d'")
        print(f"2. 浏览器访问 {LETTA_URL}/v1/agents 是否能打开")


def save_agent_id(agent_id):
    env_file = ".env"
    lines = []
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

    updated = False
    new_lines = []
    for line in lines:
        if line.startswith("LETTA_AGENT_ID="):
            new_lines.append(f"LETTA_AGENT_ID={agent_id}\n")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines.append("\n")
        new_lines.append(f"LETTA_AGENT_ID={agent_id}\n")

    with open(env_file, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print(f"已将 LETTA_AGENT_ID 写入 {env_file}")


if __name__ == "__main__":
    init_letta_agent()
