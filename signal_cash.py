import os
import requests

def load_env_file(filepath):
    """
    Manually load environment variables from a .env file.
    This avoids needing the python-dotenv library in Houdini.
    """
    if not os.path.exists(filepath):
        return

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ[key] = value

# Load environment variables from .env file
# We look for .env in the same directory as this script
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, '.env')
load_env_file(env_path)

def send_telegram(text: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    channel_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not channel_id:
        print(f"Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not found. Checked: {env_path}")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        response = requests.post(url, data={
            "chat_id": channel_id,
            "text": text
        })
        response.raise_for_status()
        print(f"Message sent successfully! Status Code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Failed to send message: {e}")
        if 'response' in locals() and response is not None:
             print(f"Response: {response.text}")

if __name__ == '__main__':
    send_telegram("просчет кэша окончен!")