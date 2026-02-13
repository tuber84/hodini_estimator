import sys
import types
import time
from unittest.mock import MagicMock

# Mocking the 'hou' module
hou = types.ModuleType('hou')
sys.modules['hou'] = hou

# Mocking hou.pwd() and its methods
mock_rop = MagicMock()
mock_rop.evalParm.side_effect = lambda parm: {
    'f1': 1,   # start frame
    'f2': 10,  # end frame
    'f3': 1,   # step
    'res_x': 1920,
    'res_y': 1080
}.get(parm, 0)
mock_rop.parm.side_effect = lambda name: True if name in ['f1', 'f2', 'f3', 'res_x', 'res_y'] else False
mock_rop.path.return_value = "/out/mantra_ipr" # Mock path method

hou.pwd = MagicMock(return_value=mock_rop)
hou.ui = MagicMock()
hou.ui.setStatusMessage = MagicMock()
hou.hipFile = MagicMock()
hou.hipFile.basename.return_value = "my_cool_scene.hip"

# Now import the script to test
# We need to add the current directory to sys.path to import it
import os
sys.path.append(os.getcwd())
# Also add the path where the file is actually located if different from cwd
sys.path.append(r"c:\_proekty\python\hodini_work")

# Mock signal_cash inside render_estimator (or before importing)
# Since we already imported sys.path, we can mock it by creating a module
mock_signal_cash = types.ModuleType('signal_cash')
mock_signal_cash.send_telegram = MagicMock()
sys.modules['signal_cash'] = mock_signal_cash

import render_estimator

print("--- Test Start ---")

# Simulate Start Render
print("Calling start_render()...")
render_estimator.start_render()

# Simulate Rendering Loop
for i in range(1, 4): # Simulate 3 frames
    print(f"\nSimulating frame {i} render (sleeping 0.1s)...")
    time.sleep(0.1)
    
    print("Calling post_frame()...")
    render_estimator.post_frame()

print("\nSimulating Finish Render...")
render_estimator.finish_render()

print("\nVerifying Telegram call...")
if mock_signal_cash.send_telegram.called:
    print("SUCCESS: send_telegram was called!")
    print(f"Message sent: {mock_signal_cash.send_telegram.call_args[0][0]}")
else:
    print("FAILURE: send_telegram was NOT called.")

print("\n--- Test End ---")
