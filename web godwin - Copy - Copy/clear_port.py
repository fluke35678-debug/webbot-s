import os
import subprocess
import sys
import io

# Force UTF-8 for Windows console
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def clear_port(port):
    try:
        # หา PID ที่ใช้ Port นั้น
        result = subprocess.check_output(f"netstat -ano | findstr :{port}", shell=True).decode()
        lines = result.strip().split('\n')
        for line in lines:
            if 'LISTENING' in line:
                pid = line.strip().split()[-1]
                print(f"Stopping process {pid} on port {port}...")
                os.system(f"taskkill /F /PID {pid}")
    except Exception:
        print(f"No active process found on port {port} or error occurred.")

if __name__ == "__main__":
    clear_port(8000)
