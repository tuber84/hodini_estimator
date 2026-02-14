import sys
import os
import time
from unittest.mock import MagicMock
import io

# Force detailed encoding handling for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Mock hou module
sys.modules['hou'] = MagicMock()
import hou
hou.hipFile.basename.return_value = "test_scene.hip"
hou.pwd.return_value.path.return_value = "/out/rop1"
hou.frame.return_value = 1.0

# Mock socket
import socket
socket.gethostname = MagicMock(return_value="test-host")

# Add current dir to path
sys.path.append(os.getcwd())
import render_estimator

def test_reproduction():
    print("--- Starting Reproduction Test ---")
    
    # 1. Initialize logic
    render_estimator.render_stats = {
        'start_time': None, 
        'last_frame_time': None,
        'frames_rendered': 0, 
        'total_frames': 0, 
        'frame_times': [],
        'hip_name': "Unknown", 
        'rop_name': "Unknown", 
        'camera_name': "Unknown", 
        'renderer': "Unknown",
        'resolution': "Unknown", 
        'hostname': "Unknown", 
        'lights': []
    }
    
    # 2. Simulate Start
    render_estimator.start_render()
    render_estimator.render_stats['total_frames'] = 2
    
    # 3. Simulate "Single Process" timing
    # Start time was 30 seconds ago
    start_time = time.time() - 30
    render_estimator.render_stats['start_time'] = start_time
    render_estimator.render_stats['last_frame_time'] = start_time # Irrelevant for this test as we inject frame_times
    
    # Inject 2 frames that took "0 seconds" (according to script execution time in Single Process mode)
    render_estimator.render_stats['frame_times'] = [(1, 0.001), (2, 0.001)]
    render_estimator.render_stats['frames_rendered'] = 2
    
    # 4. Run finish_render() and capture output
    # We'll monkeypatch send_telegram_notification to just print the message
    # so we can inspect it easily.
    original_send = render_estimator.send_telegram_notification
    captured_message = None
    
    def mock_send(msg):
        nonlocal captured_message
        captured_message = msg
        print("\n[MOCK TELEGRAM] Sending message:")
        print(msg)
        
    render_estimator.send_telegram_notification = mock_send
    
    try:
        render_estimator.finish_render()
    finally:
        render_estimator.send_telegram_notification = original_send
        
    # 5. Analyze result
    if captured_message:
        # Check for 0.0s in Min/Max time
        # We expect this to be present in the BUGGY version
        if "Мин. время: 0.0s" in captured_message:
            print("\n[RESULT] BUG CONFIRMED: Found 'Мин. время: 0.0s'")
        else:
            print("\n[RESULT] BUG NOT FOUND (or fixed): 'Мин. время: 0.0s' not in message")
            
        # Also check for Max time
        if "Макс. время: 0.0s" in captured_message:
            print("[RESULT] BUG CONFIRMED: Found 'Макс. время: 0.0s'")
            
    else:
        print("\n[RESULT] ERROR: No message captured")

if __name__ == "__main__":
    test_reproduction()
