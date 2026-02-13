import sys
import os
import hou

# Попытка найти путь к скрипту через параметры ноды
# Так как __file__ не работает при запуске из поля Script
def get_script_dir():
    node = hou.pwd()
    candidates = ['prerender', 'lprerender', 'tprerender']
    for name in candidates:
        parm = node.parm(name)
        if parm:
            val = parm.eval()
            # Проверяем, что в параметре указан путь к ЭТОМУ скрипту
            if 'loader_pre_render.py' in val:
                # val может быть "C:/Path/loader_pre_render.py"
                return os.path.dirname(val)
    return None

script_dir = get_script_dir()
if script_dir:
    if script_dir not in sys.path:
        sys.path.append(script_dir)
else:
    # Фолбэк: пробуем найти через стандартный __file__, если вдруг запущено иначе
    try:
        d = os.path.dirname(os.path.abspath(__file__))
        if d not in sys.path:
            sys.path.append(d)
    except:
        pass

try:
    import render_estimator
    # Reload только для Pre-Render, чтобы подхватывать изменения кода без перезапуска Houdini
    import importlib
    importlib.reload(render_estimator)
    
    render_estimator.start_render()
except Exception as e:
    print(f"[Loader] Error: {e}")
