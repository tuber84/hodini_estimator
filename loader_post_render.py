import sys

# Путь к проекту
project_path = "c:/_proekty/python/hodini_work"
if project_path not in sys.path:
    sys.path.append(project_path)

import render_estimator

# Вызываем финализацию и отправку уведомления
render_estimator.finish_render()
