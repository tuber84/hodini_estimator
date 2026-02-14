import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import time
import threading

# Mock hou module
sys.modules['hou'] = MagicMock()
import hou

# Import the module under test
import render_estimator

class TestLazyWatcher(unittest.TestCase):
    def setUp(self):
        # Reset global state
        render_estimator.render_stats = {
            'start_time': None,
            'last_frame_time': None,
            'frames_rendered': 0,
            'frame_times': [],
            'total_frames': 0,
            'hip_name': 'test.hip',
            'rop_name': '/out/rop',
            'camera_name': 'cam1',
            'lights': [],
            'resolution': '1920x1080',
            'renderer': 'Mantra',
            'hostname': 'TestHost'
        }
        render_estimator.watcher_thread = None
        render_estimator.stop_watcher_event = None

    @patch('render_estimator.get_output_path_parm')
    def test_lazy_start(self, mock_get_path):
        print("\n--- Testing Lazy Watcher Start ---")
        
        # 1. Setup Mock ROP
        mock_rop = MagicMock()
        hou.pwd.return_value = mock_rop
        
        # Standard frame range 1-5
        mock_rop.evalParm.side_effect = lambda name: {'f1': 1, 'f2': 5, 'f3': 1}.get(name, 0)
        
        # MOCKING THE CRITICAL PART:
        # "Single Process" flag is FALSE initially
        mock_rop.parm.return_value = MagicMock()
        mock_rop.evalParm.side_effect = lambda name: {'f1': 1, 'f2': 5, 'f3': 1, 'husk_all_frames_in_one_process': 0}.get(name, 0)

        # Output path
        mock_parm_path = MagicMock()
        mock_parm_path.evalAtFrame.side_effect = lambda f: f"C:/render/frame.{int(f):04d}.exr"
        mock_get_path.return_value = mock_parm_path

        # 2. Start Render (Normal Mode)
        render_estimator.start_render()
        
        self.assertIsNone(render_estimator.watcher_thread, "Watcher should NOT start initially")
        
        # 3. Simulate Fast Post-Frame (Generation)
        # Manually set start time to "now"
        render_estimator.render_stats['start_time'] = time.time()
        render_estimator.render_stats['last_frame_time'] = time.time()
        
        # Call post_frame immediately (duration ~0.0s)
        render_estimator.post_frame()
        
        # 4. Verify Lazy Start
        # Check if watcher thread is now running
        if render_estimator.watcher_thread and render_estimator.watcher_thread.is_alive():
            print("PASS: Watcher thread LAZY STARTED successfully.")
        else:
            self.fail("Watcher thread failed to lazy start.")
            
        # Clean up
        if render_estimator.stop_watcher_event:
            render_estimator.stop_watcher_event.set()

if __name__ == '__main__':
    unittest.main()
