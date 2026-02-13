import sys
from importlib import reload

# Путь к проекту (динамически от HIP файла)
import hou
import os

# --- ОТКЛЮЧЕНА ЖЕСТКАЯ КОНФИГУРАЦИЯ В КОДЕ ---
# Скрипт теперь ищет переменную CUSTOM_SCRIPT_PATH в файле .env рядом с .hip файлом
# ---------------------------------------------

import hou
import os
import sys

# Функция для чтения .env файла (чтобы не тянуть зависимость python-dotenv в лоадеры)
def get_custom_path_from_env(hip_dir):
    env_path = os.path.join(hip_dir, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("CUSTOM_SCRIPT_PATH="):
                        # Извлекаем значение после равно, убираем кавычки если есть
                        path_val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if path_val:
                            return path_val
        except Exception:
            pass # Игнорируем ошибки чтения, идем по дефолту
    return None

project_path = None
hip_dir = os.path.dirname(hou.hipFile.path())

# 1. Проверяем .env файл и ТОЛЬКО его
env_custom_path = get_custom_path_from_env(hip_dir)
if env_custom_path and os.path.exists(os.path.join(env_custom_path, "render_estimator.py")):
    project_path = env_custom_path
else:
    # Если путь не задан или неверен - ошибка
    print(f"[RenderEstimator] CRITICAL ERROR: Could not find 'render_estimator.py'.")
    print(f"Please set CUSTOM_SCRIPT_PATH in the .env file located at: {os.path.join(hip_dir, '.env')}")

if project_path:
    if project_path not in sys.path:
        sys.path.append(project_path)
else:
    print("[RenderEstimator] Error: Could not find render_estimator.py! Please set CUSTOM_SCRIPT_PATH in the loader script.")

import render_estimator

# Перезагружаем модуль на случай изменений
reload(render_estimator)

# Запускаем инициализацию рендера
render_estimator.start_render()
