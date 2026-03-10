import json
from pathlib import Path

# 确定 json 文件的绝对路径
BASE_DIR = Path(__file__).parent
PROMPTS_PATH = BASE_DIR / "prompts.json"

class PromptManager:
    def __init__(self):
        self._prompts = {}
        self.reload()

    def reload(self):
        if not PROMPTS_PATH.exists():
            print(f"警告: 找不到提示词文件 {PROMPTS_PATH}")
            self._prompts = {}
            return

        try:
            with open(PROMPTS_PATH, "r", encoding="utf-8") as f:
                self._prompts = json.load(f)
            print(f"提示词已加载，共 {len(self._prompts)} 条")
        except Exception as e:
            print(f"提示词加载失败: {e}")

    def get(self, key, default=""):
        return self._prompts.get(key, default)

    def update_and_save(self, key: str, value: str):
        """更新内存并写入文件"""
        self._prompts[key] = value
        try:
            with open(PROMPTS_PATH, "w", encoding="utf-8") as f:
                json.dump(self._prompts, f, ensure_ascii=False, indent=2)
            print(f"提示词 [{key}] 已保存")
            return True
        except Exception as e:
            print(f"保存提示词失败: {e}")
            return False


prompt_manager = PromptManager()