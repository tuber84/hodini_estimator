import sys
from importlib import reload

# Путь к проекту
project_path = "c:/_proekty/python/hodini_work"
if project_path not in sys.path:
    sys.path.append(project_path)

import render_estimator

# Перезагружаем модуль на случай изменений
reload(render_estimator)

# Запускаем инициализацию рендера
render_estimator.start_render()
