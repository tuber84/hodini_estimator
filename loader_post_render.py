import sys

# Путь к проекту (динамически от HIP файла)
import hou
import os

# --- СТРОГАЯ КОНФИГУРАЦИЯ ЧЕРЕЗ .ENV ---
# Скрипт требует переменную CUSTOM_SCRIPT_PATH в файле .env рядом с .hip файлом.
# Переменная должна указывать на папку, где лежит render_estimator.py.
# Автоматический поиск отключен для надежности.
# ----------------------------------------

import hou
import os
import sys

# Функция для чтения .env файла
def get_custom_path_from_env(hip_dir):
    env_path = os.path.join(hip_dir, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("CUSTOM_SCRIPT_PATH="):
                        path_val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if path_val:
                            return path_val
        except Exception:
            pass
    return None

project_path = None
hip_dir = os.path.dirname(hou.hipFile.path())

# 1. Проверяем .env файл и ТОЛЬКО его
env_custom_path = get_custom_path_from_env(hip_dir)
if env_custom_path and os.path.exists(os.path.join(env_custom_path, "render_estimator.py")):
    project_path = env_custom_path
else:
    print(f"[RenderEstimator] CRITICAL ERROR: Could not find 'render_estimator.py'. Please set CUSTOM_SCRIPT_PATH in .env file.")

if project_path:
    if project_path not in sys.path:
        sys.path.append(project_path)

import render_estimator

# Вызываем финализацию и отправку уведомления
render_estimator.finish_render()
