import sys
import os

# Добавляем путь к вашему проекту, чтобы Python мог найти скрипт
# ВАЖНО: Измените этот путь, если проект находится в другом месте
project_path = "c:/_proekty/python/hodini_work"
if project_path not in sys.path:
    sys.path.append(project_path)

import signal_cash

# Выполняем отправку уведомления
try:
    signal_cash.send_telegram("Рендер Houdini завершен! 🎉")
except Exception as e:
    print(f"Не удалось отправить уведомление: {e}")
