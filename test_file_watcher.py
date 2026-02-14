import sys
import os
import time
import threading
from unittest.mock import MagicMock
import io

# Force detailed encoding handling
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Mock hou module
sys.modules['hou'] = MagicMock()
import hou

# Add current dir to path
sys.path.append(os.getcwd())
import render_estimator

def test_file_watcher():
    print("--- Testing File Watcher ---")
    
    # 1. Setup mock ROP and paths
    rop = MagicMock()
    rop.path.return_value = "/out/rop"
    
    # Mock parameters
    # Picture path: using a temp directory
    temp_dir = os.path.join(os.getcwd(), "test_render_output")
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
        
    def eval_parm(name):
        if name == 'husk_all_frames_in_one_process': return 1 # Enable Single Process
        if name == 'f1': return 1
        if name == 'f2': return 5
        if name == 'f3': return 1
        if name == 'picture': return os.path.join(temp_dir, "frame.$F4.exr")
        return None
        
    rop.evalParm.side_effect = eval_parm
    
    # Mock .parm() calls
    def get_parm(name):
        p = MagicMock()
        if name == 'picture':
            p.evalAtFrame.side_effect = lambda f: os.path.join(temp_dir, f"frame.{int(f):04d}.exr")
            return p
        if name == 'husk_all_frames_in_one_process': return p
        if name == 'f1' or name == 'f2' or name == 'f3': return p
        return None
        
    rop.parm.side_effect = get_parm
    hou.pwd.return_value = rop
    
    # 2. Start Render (should trigger watcher)
    print("Starting render (mock)...")
    render_estimator.start_render()
    
    # Check if thread started
    if render_estimator.watcher_thread and render_estimator.watcher_thread.is_alive():
        print("PASS: Watcher thread started.")
    else:
        print("FAIL: Watcher thread NOT started.")
        return

    # 3. Simulate file creation
    print("Simulating file creation...")
    output_files = []
    
    try:
        start_t = render_estimator.render_stats['start_time']
        
        for i in range(1, 4): # Create first 3 frames
            time.sleep(1.1) # Wait > 1s for file watcher loop
            
            fname = f"frame.{i:04d}.exr"
            fpath = os.path.join(temp_dir, fname)
            
            # Create file
            with open(fpath, 'w') as f:
                f.write("test data")
            output_files.append(fpath)
            print(f"Created {fname}")
            
            # Allow watcher to pick it up
            time.sleep(1.1)
            
            # Check stats
            last_frame = render_estimator.render_stats['frames_rendered']
            print(f"Stats reported: {last_frame} frames rendered")
            
            if last_frame == i:
                 print(f"PASS: Frame {i} detected.")
            else:
                 print(f"FAIL: Frame {i} NOT detected.")

    finally:
        # Cleanup
        print("Cleaning up...")
        render_estimator.finish_render()
        
        # Verify thread stopped
        if not render_estimator.watcher_thread or not render_estimator.watcher_thread.is_alive():
             print("PASS: Watcher thread stopped.")
        else:
             print("FAIL: Watcher thread did NOT stop.")

        for f in output_files:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)

if __name__ == "__main__":
    test_file_watcher()
