import sys
import os
import hou

def get_script_dir():
    node = hou.pwd()
    # Параметры Post-Frame
    candidates = ['postframe', 'lpostframe', 'tpostframe']
    for name in candidates:
        parm = node.parm(name)
        if parm:
            val = parm.eval()
            if 'loader_post_frame.py' in val:
                return os.path.dirname(val)
    return None

script_dir = get_script_dir()
if script_dir and script_dir not in sys.path:
    sys.path.append(script_dir)

try:
    import render_estimator
    render_estimator.post_frame()
except Exception as e:
    print(f"[Loader] Error: {e}")
