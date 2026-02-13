import sys

# Путь к проекту (на случай если контекст потерялся, хотя обычно сохраняется)
project_path = "c:/_proekty/python/hodini_work"
if project_path not in sys.path:
    sys.path.append(project_path)

import render_estimator

# Вызываем расчет времени после кадра
render_estimator.post_frame()
