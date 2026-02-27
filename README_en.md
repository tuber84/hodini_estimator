🇷🇺 [Русский](README.md) | 🇬🇧 [English](README_en.md)

# Houdini Render Estimator & Telegram Notifier

This set of scripts for Houdini allows you to estimate render times and send Telegram notifications upon task completion.

The script automatically collects render statistics (frame time, total time, resolution, camera, lights) and sends a beautifully formatted report directly to your chat.

## ✨ Features

### 1. Time Estimation and Progress
*   **Status Bar**: Shows the current frame, elapsed time, and a *forecast* of the remaining time right in the Houdini status bar.
*   **Console**: Prints detailed information to the Houdini console after each frame.

![Houdini Console](images/example_console.jpg)
![Houdini Console Single](images/example_console_single.jpg)

### 2. Telegram Notifications
After the render is complete, you receive a message with a detailed report:

![Telegram Notification](images/example_telegram.png)

*   **📂 File**: Name of the HIP file.
*   **🕸 Node**: Which ROP node rendered.
*   **🖥 Host**: On which machine the render took place.
*   **🎨 Renderer**: Engine detection (Mantra, Karma CPU/XPU, Redshift, Arnold, V-Ray, Octane).
*   **📷 Camera**: Camera name (supports USD/Solaris and classic OBJ).
*   **💡 Lights**: List of light sources in the scene.
*   **📐 Resolution**: Final image resolution.
*   **📁 Path**: Path where files are saved.
*   **💾 Size**: Total size of all rendered files (in MB/GB).
*   **📊 Time Statistics**:
    *   Total render time.
    *   Average frame time.
    *   Fastest and slowest frames (with frame numbers).
### 3. Simplicity
*   **Zero Config**: Scripts automatically detect their location.
*   **Portable**: Can be placed on a network drive and used by the entire studio.

### 4. Calculation Logic
The script uses a simple but effective "weighted average" method:
```
Remaining time = (Elapsed time / Number of completed frames) * Number of remaining frames
```
*   This means the forecast becomes more accurate with each new frame.
*   If the first frame takes a long time (e.g., shader compilation), the forecast might initially be inflated but will quickly adjust after 2-3 frames.

> **⚠️ Important**: This method assumes frames render at roughly the same speed.
> If your scene is very heterogeneous (e.g., starts with an empty frame, followed by a close-up with SSS and hair), the forecast may be inaccurate during sudden changes.
>
> *In the future, we plan to add a second calculation algorithm — "Sliding Window", which will consider the speed of only the last 5-10 frames for greater sensitivity to changes.*

---

## 🛠 Installation

### Step 1: Download the Scripts
Save the repository folder to a convenient, permanent location on your drive.
For example: `C:/Tools/HoudiniRenderEstimator`

This folder should contain:
- `render_estimator.py` — The main script
- `loader_*.py` — Loader scripts
- `.env` — Settings file

### Step 2: Create a Telegram Bot
To receive notifications, you need to create your own bot. It's free and takes 1 minute.

1.  Write the command `/newbot` to [@BotFather](https://t.me/BotFather).
2.  Choose a name (e.g., `MyRenderBot`) and a username (e.g., `my_studio_render_bot`).
3.  **BotFather will give you an API TOKEN**. Copy it.

Now you need to find your personal ID (where the bot will send messages):
1.  Write to [@userinfobot](https://t.me/userinfobot).
2.  It will reply with your **ID** (a number, e.g., `123456789`). Copy it.

### Step 3: Configure .env
Create (or edit) the `.env` file in the scripts folder (`C:/Tools/HoudiniRenderEstimator/.env`).
Paste the obtained data there:

```ini
TELEGRAM_BOT_TOKEN=YOUR_LONG_TOKEN_FROM_BOTFATHER
TELEGRAM_CHAT_ID=YOUR_ID_FROM_USERINFOBOT
```

### Step 4: Connect in Houdini
In your ROP node (Mantra, Karma, Redshift, etc.), go to the **Scripts** tab.

You don't need to write code! Just pick the script files via the file dialog:

![ROP Node Setup](images/setup_rop.png)

*   **Pre-Render Script**: Choose the `loader_pre_render.py` file from your folder.
    *   *Important: Ensure the script language (right of the field) is set to **Python**, not Hscript!*
*   **Post-Frame Script**: Choose the `loader_post_frame.py` file.
*   **Post-Render Script**: Choose the `loader_post_render.py` file.

✅ **Done!** Start rendering.
The script will automatically grab the necessary libraries and start sending notifications.

---

### 5. "Single Process" Mode (File Watcher)
If the **"Render All Frames with a Single Process"** option is enabled in a USD ROP (Karma), default Houdini scripts cannot track the progress of each frame.
![Single Process](images/single_process_rop.jpg)

However, **Render Estimator** automatically detects this mode and launches a special **File Watcher**:
*   **Background Monitoring**: The script watches for ready files (exr, png, etc.) appearing in the render folder.
*   **Statistics**: Thanks to this, you get *nearly* accurate statistics (time, progress) even in Single Process mode.
*   **Limitation**: Frame time is counted from the moment the file appears on disk, so there might be a 1-2 second margin of error.

> **⚠️ IMPORTANT**: For "File Watcher" (Single Process) mode to work, the script needs to know where files are saved.
>
> Make sure your Karma ROP node has an explicit path with the frame variable defined in the **Override Output Image** field, for example:
> `$HIP/render/$HIPNAME.$OS./$F4.exr`
![Override Output Image](images/rop_override_output_path.jpg)
>
> If you use a default path like `ip` (MPlay) or don't specify a path at all, File Watcher **will not be able to find files** and progress will be stuck at 0%.
