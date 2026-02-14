import threading
import re
import hou
import time
import datetime
import os
import json
import socket
import urllib.request
import urllib.parse
import urllib.error
import sys

# Глобальный словарь для хранения статистики рендера
# Мы используем словарь, чтобы состояние сохранялось между вызовами функций
render_stats = {
    'start_time': None,
    'last_frame_time': None,
    'frames_rendered': 0,
    'total_frames': 0,
    'frame_times': [], # Список кортежей (номер_кадра, время)
    'hip_name': "Unknown",
    'rop_name': "Unknown",
    'camera_name': "Unknown",
    'renderer': "Unknown",
    'resolution': "Unknown",
    'hostname': "Unknown",
    'lights': [],
    'output_path': "Unknown",
    'total_size_bytes': 0
}

# --- File Watcher Globals ---
watcher_thread = None
stop_watcher_event = None

# --- CONFIGURATION ---
# Check if stdout supports colors (e.g., not redirected to a file)
# Houdini console often returns True for isatty() but doesn't support ANSI colors properly.
# Disabling by default to avoid garbage characters.
USE_COLORS = False

class Colors:
    RESET = "\033[0m" if USE_COLORS else ""
    BOLD = "\033[1m" if USE_COLORS else ""
    RED = "\033[91m" if USE_COLORS else ""
    GREEN = "\033[92m" if USE_COLORS else ""
    YELLOW = "\033[93m" if USE_COLORS else ""
    BLUE = "\033[94m" if USE_COLORS else ""
    MAGENTA = "\033[95m" if USE_COLORS else ""
    CYAN = "\033[96m" if USE_COLORS else ""
    WHITE = "\033[97m" if USE_COLORS else ""

def log(message, color=Colors.RESET, icon=""):
    """
    Helper for formatted logging.
    """
    prefix = f"{Colors.CYAN}[RenderEstimator]{Colors.RESET}"
    icon_str = f"{icon} " if icon else ""
    print(f"{prefix} {color}{icon_str}{message}{Colors.RESET}")

def get_output_path_parm(node):
    """
    Пытается найти параметр пути выходного файла.
    Приоритет: outputimage (USD), picture (Mantra), vm_picture.
    """
    # Для USD/Karma приоритет outputimage
    type_name = node.type().name()
    if 'usd' in type_name or 'karma' in type_name:
         p = node.parm('outputimage')
         if p: return p
    
    for p in ['picture', 'outputimage', 'vm_picture', 'copoutput']:
        parm = node.parm(p)
        if parm:
            return parm
    return None

def file_watcher_loop(paths_to_watch, start_time):
    """
    Фоновый поток, который следит за появлением файлов.
    """
    global render_stats, stop_watcher_event
    
    # paths_to_watch = {frame_number: file_path}
    pending_frames = paths_to_watch.copy()
    
    log(f"FileWatcher started. Watching {len(pending_frames)} files.", Colors.BLUE, "👀")
    
    # Трейкинг активности для таймаута
    last_activity_time = start_time # Use start_time initially
    
    def check_for_updates():
        nonlocal last_activity_time
        # Проверяем файлы
        completed_frames = []
        for frame, path in pending_frames.items():
            if os.path.exists(path):
                # Проверяем время модификации
                try:
                    mtime = os.path.getmtime(path)
                    # Если файл изменен ПОСЛЕ старта рендера (с небольшим запасом)
                    if mtime >= start_time - 1.0:
                        completed_frames.append(frame)
                except:
                   pass
        
        # Обрабатываем найденные кадры
        if completed_frames:
            last_activity_time = time.time()
            current_time = time.time()
            for frame in completed_frames:
                # Удаляем из списка ожидания
                if frame in pending_frames:
                    # Capture path for size calculation
                    f_path = pending_frames[frame]
                    del pending_frames[frame]
                    
                    try:
                        if os.path.exists(f_path):
                            s_bytes = os.path.getsize(f_path)
                            render_stats['total_size_bytes'] += s_bytes
                    except:
                        pass
                
                # Обновляем статистику
                last_time = render_stats['last_frame_time']
                if last_time is None: last_time = render_stats['start_time']
                
                duration = current_time - last_time
                render_stats['last_frame_time'] = current_time
                render_stats['frames_rendered'] += 1
                render_stats['frame_times'].append((frame, duration))
                
                # Расчет прогресса
                elapsed = current_time - render_stats['start_time']
                count = render_stats['frames_rendered']
                total = render_stats['total_frames']
                avg = elapsed / count if count > 0 else 0
                rem_frames = total - count
                rem_time = avg * rem_frames
                
                rem_str = str(datetime.timedelta(seconds=int(rem_time)))
                
                # Formatted message
                msg = (f"Кадр {frame} готов! "
                       f"{Colors.YELLOW}⏱ {duration:.1f}s{Colors.RESET} "
                       f"{Colors.MAGENTA}⏳ Осталось: {rem_str}{Colors.RESET} "
                       f"({Colors.CYAN}~{avg:.1f}s/fr{Colors.RESET})")
                
                log(msg, Colors.GREEN, "✅")
                
                try:
                    # Strip colors for UI status message
                    clean_msg = f"RenderEstimator: Frame {frame} done. Rem: {rem_str}"
                    hou.ui.setStatusMessage(clean_msg)
                except:
                    pass

    while (stop_watcher_event is not None and not stop_watcher_event.is_set()) and pending_frames:
        check_for_updates()
        
        # Таймаут неактивности (10 минут)
        if time.time() - last_activity_time > 600:
            log("File Watcher timed out (no new frames for 10 min). Stopping.", Colors.RED, "💀")
            break
            
        # Спим немного
        time.sleep(1.0)
    
    # Final check for any fast frames appearing just as we stopped
    if pending_frames:
        check_for_updates()
    
    log("FileWatcher finished.", Colors.BLUE, "🏁")
    
    # Отправляем финальный отчет (Watcher берет ответственность на себя)
    finalize_and_send_report()

def resolve_frame_in_path(path, frame):
    """
    Заменяет $F и $F<digits> на номер кадра.
    """
    def repl(match):
        padding = match.group(1)
        if padding:
            return f"{int(frame):0{int(padding)}d}"
        else:
            return str(int(frame))
    
    # $F followed by optional digits
    return re.sub(r'\$F(\d*)', repl, path)

def try_start_file_watcher(rop):
    """
    Пытается запустить File Watcher.
    Возвращает True, если watcher был запущен.
    """
    global render_stats, watcher_thread, stop_watcher_event
    
    if watcher_thread and watcher_thread.is_alive():
        log("File Watcher already running.", Colors.YELLOW)
        return True
        
    try:
        # Проверяем, есть ли выходной файл
        path_parm = get_output_path_parm(rop)
        
        if not path_parm:
            log("Cannot find output path parameter. File Watcher skipped.", Colors.RED, "❌")
            return False

        # Генерируем пути
        paths_to_watch = {}
        
        # Получаем диапазон кадров (start, end, step)
        f_start = rop.evalParm('f1')
        f_end = rop.evalParm('f2')
        f_step = rop.evalParm('f3')
        if f_step == 0: f_step = 1
        
        # evalAtFrame
        curr_frame = f_start
        while curr_frame <= f_end + 0.0001:
            path = path_parm.evalAtFrame(curr_frame)
            # Fix: Если в пути остались $F (из-за экранирования \$F для USD), заменяем их вручную
            if '$F' in path:
                path = resolve_frame_in_path(path, curr_frame)
            
            paths_to_watch[int(curr_frame)] = path
            curr_frame += f_step
        
        if paths_to_watch:
            stop_watcher_event = threading.Event()
            watcher_thread = threading.Thread(target=file_watcher_loop, args=(paths_to_watch, render_stats['start_time']))
            watcher_thread.daemon = True
            watcher_thread.start()
            log("File Watcher started successfully (Lazy/Explicit).", Colors.GREEN, "🚀")
            return True
        else:
             log("No paths to watch generated.", Colors.YELLOW)
             return False

    except Exception as e:
        log(f"Error starting File Watcher: {e}", Colors.RED, "💥")
        return False

def start_render():
    """
    Функция для 'Pre-Render Script'.
    Инициализирует статистику перед началом рендера.
    """
    global render_stats, watcher_thread, stop_watcher_event
    
    # Сброс
    render_stats['start_time'] = time.time()
    render_stats['last_frame_time'] = time.time()
    render_stats['frames_rendered'] = 0
    render_stats['frame_times'] = []
    
    # Останавливаем старый поток если был
    if stop_watcher_event:
        stop_watcher_event.set()
    if watcher_thread and watcher_thread.is_alive():
        watcher_thread.join(timeout=2.0)
        
    watcher_thread = None
    stop_watcher_event = None
    
    # Сохраняем информацию о сцене
    try:
        render_stats['hip_name'] = hou.hipFile.basename()
        render_stats['rop_name'] = hou.pwd().path()
        render_stats['hostname'] = socket.gethostname()
        
        # --- Определение рендерера ---
        renderer_val = "Unknown"
        rop_node = hou.pwd()
        
        # Пробуем параметр renderer (обычно есть у Karma/Solaris)
        r_parm = rop_node.parm('renderer')
        if r_parm:
            renderer_val = r_parm.eval()
            # Очистка имени (например BRAY_HdKarmaXPU -> Karma XPU)
            if 'KarmaXPU' in renderer_val: renderer_val = 'Karma XPU'
            elif 'KarmaCPU' in renderer_val: renderer_val = 'Karma CPU'
        else:
            # Фолбэк на тип ноды
            type_name = rop_node.type().name()
            if 'mantra' in type_name: renderer_val = 'Mantra'
            elif 'redshift' in type_name: renderer_val = 'Redshift'
            elif 'vray' in type_name: renderer_val = 'V-Ray'
            elif 'arnold' in type_name: renderer_val = 'Arnold'
            elif 'karma' in type_name: renderer_val = 'Karma'
            else: renderer_val = type_name
            
        render_stats['renderer'] = renderer_val

        # --- Output Path ---
        out_parm = get_output_path_parm(rop_node)
        if out_parm:
            try:
                # Store unexpanded string to show variables like $F
                val = out_parm.unexpandedString()
                if not val: val = out_parm.eval()
                render_stats['output_path'] = val
            except:
                render_stats['output_path'] = "Unknown"
        else:
            render_stats['output_path'] = "Unknown"

        # --- Определение разрешения ---
        res_val = "Unknown"
        res_source = "None"
        
        # Debug params


        # 1. Стандартные паметры (Mantra/Redshift/Standard ROPs)
        if rop_node.parm('resx') and rop_node.parm('resy'):
             res_val = f"{rop_node.evalParm('resx')}x{rop_node.evalParm('resy')}"
             res_source = "ROP resx/resy"
        elif rop_node.parm('tres1') and rop_node.parm('tres2'): # Иногда так называется
             res_val = f"{rop_node.evalParm('tres1')}x{rop_node.evalParm('tres2')}"
             res_source = "ROP tres"
        
        # 2. Переопределения в Solaris (Karma ROP)
        # Если есть override_resolution (и он включен)
        # Karma ROP часто имеет resolution (res1, res2)
        if rop_node.parm('override_resolution'):
            is_overridden = rop_node.evalParm('override_resolution')
            if is_overridden:
                 if rop_node.parm('res1') and rop_node.parm('res2'):
                     res_val = f"{rop_node.evalParm('res1')}x{rop_node.evalParm('res2')}"
                     res_source = "ROP Override"
            else:
                # Если override ВЫКЛЮЧЕН, мы должны игнорировать локальные параметры ROP
                # и искать в USD.
                # Если мы уже нашли что-то через resx/tres, нужно сбросить, если мы уверены, что это Solaris
                if 'karma' in render_stats['renderer'].lower() or 'usd' in render_stats['renderer'].lower():
                    # log("Override is OFF. Ignoring ROP params, looking in USD...", Colors.CYAN)
                    res_val = "Unknown"
                    res_source = "Forced USD lookup"
        

        render_stats['resolution'] = res_val # Предварительно сохраняем, может обновиться через USD

        # --- Поиск камеры и доп. данных через USD ---
        # Пытаемся найти камеру
        # Проверяем разные параметры, так как имя может отличаться в разных рендерах (Mantra, Karma, Redshift и т.д.)
        camera_parms = ['camera', 'render_camera', 'camera_path', 'cam']
        found_camera = "Unknown"
        
        node = hou.pwd()
        
        # 1. Поиск по стандартным параметрам ROP
        for parm_name in camera_parms:
            parm = node.parm(parm_name)
            if parm:
                val = parm.eval()
                if val and isinstance(val, str) and val != "":
                    found_camera = val
                    break
        
        # 2. Если не нашли и есть rendersettings (Solaris/Subnet), пробуем через USD
        if found_camera == "Unknown":
            rs_parm = node.parm('rendersettings')
            if rs_parm:
                try:
                    # Пытаемся получить stage
                    stage = None
                    if hasattr(node, 'stage'):
                        stage = node.stage()
                    
                    # Если у ноды нет stage (например, это ROP), берем из инпута
                    if not stage and node.inputs():
                        input_node = node.inputs()[0]
                        if hasattr(input_node, 'stage'):
                            stage = input_node.stage()
                            
                    if stage:
                        rs_path = rs_parm.eval()
                        if rs_path:
                            # Используем USD API
                            prim = stage.GetPrimAtPath(rs_path)
                            if prim and prim.IsValid():
                                # Ищем relationship 'camera'
                                rel = prim.GetRelationship('camera')
                                if rel:
                                    targets = rel.GetTargets()
                                    if targets:
                                        found_camera = str(targets[0])
                                
                                # Если разрешение еще не найдено, ищем в Render Settings
                                if render_stats['resolution'] == "Unknown":
                                    attr_res = prim.GetAttribute('resolution')
                                    if attr_res and attr_res.IsValid():
                                        res_vec = attr_res.Get()
                                        if res_vec:
                                            # res_vec обычно Gf.Vec2i
                                            render_stats['resolution'] = f"{res_vec[0]}x{res_vec[1]}"

                except Exception as e:
                    # print(f"[RenderEstimator] USD extraction error: {e}")
                    pass

        # 3. Очистка имени (оставляем только имя ноды)
        if isinstance(found_camera, str) and '/' in found_camera:
            found_camera = found_camera.split('/')[-1]
            
        render_stats['camera_name'] = found_camera

        # --- Поиск источников света ---
        found_lights = []
        try:
            # 1. USD / Solaris
            # Используем stage который мы могли найти ранее
            usd_lights_found = False
            
            # Повторно пытаемся получить stage, если он не был инициализирован (код дублируется, но так надежнее без рефакторинга)
            stage = None
            if hasattr(node, 'stage'):
                stage = node.stage()
            if not stage and node.inputs():
                try:
                    input_node = node.inputs()[0]
                    if hasattr(input_node, 'stage'):
                        stage = input_node.stage()
                except:
                    pass
            
            if stage:
                # Сканируем stage на наличие источников света
                try:
                    for prim in stage.Traverse():
                        t_name = prim.GetTypeName()
                        # Простая проверка по имени типа (UsdLuxDomeLight, UsdLuxSphereLight, KarmaSkyDomeLight и т.д.)
                        if "UsdLux" in t_name or "Light" in t_name: 
                             found_lights.append(prim.GetName())
                except:
                    pass

            # 2. Standard / OBJ (если не нашли в USD или это не USD рендер)
            if not found_lights:
                # Ищем в /obj
                obj_context = hou.node("/obj")
                if obj_context:
                    for child in obj_context.children():
                        # Проверяем тип ноды
                        type_name = child.type().name().lower()
                        # Список распространенных типов источников света
                        light_types = ['hlight', 'envlight', 'sunlight', 'skylight', 'arealight', 'pointlight', 'spotlight', 
                                      'rslight', 'rsdome', 'rssun', # Redshift
                                      'arnold_light', 'skydome_light', # Arnold
                                      'octane_light', 'octane_daylight'] # Octane
                        
                        if any(lt in type_name for lt in light_types):
                            found_lights.append(child.name())
                            
        except Exception as e:
            print(f"[RenderEstimator] Light extraction error: {e}")
            pass
            
        render_stats['lights'] = found_lights

    except:
        render_stats['hip_name'] = "Unknown"
        render_stats['rop_name'] = "Unknown"
        render_stats['camera_name'] = "Unknown"
    
    # Пытаемся получить диапазон кадров из ROP ноды, которая вызывает скрипт
    try:
        # hou.pwd() возвращает текущую ноду (ROP)
        rop = hou.pwd()
        
        # Получаем диапазон кадров (start, end, step)
        f_start = rop.evalParm('f1')
        f_end = rop.evalParm('f2')
        f_step = rop.evalParm('f3')
        
        # Вычисляем общее количество кадров
        if f_step == 0: f_step = 1 # Защита от деления на ноль
        render_stats['total_frames'] = int((f_end - f_start) / f_step) + 1
        
        print(f"[RenderEstimator] Начало рендера. Кадров: {render_stats['total_frames']}")
        
        # --- ЗАПУСК FILE WATCHER ---
        should_start_watcher = False
        # Пробуем несколько вариантов имен параметров
        sp_parms = ['husk_all_frames_in_one_process', 'tr_all_frames_in_one_process', 'all_frames_in_one_process', 'allframesatonce']
        for p_name in sp_parms:
            if rop.parm(p_name) and rop.evalParm(p_name):
                should_start_watcher = True
                print(f"[RenderEstimator] Detected 'Single Process' mode via {p_name}.")
                break
        
        if not should_start_watcher:
             print("[RenderEstimator] 'Single Process' flag not found. File Watcher will NOT start explicitly.")
             
        if should_start_watcher:
            try_start_file_watcher(rop)
            
    except Exception as e:
        print(f"[RenderEstimator] Ошибка при инициализации: {e}")
        render_stats['total_frames'] = 0

def post_frame():
    """
    Функция для 'Post-Frame Script'.
    Вызывается после каждого кадра, считает время и прогноз.
    """
    global render_stats
    
    # Если рендер не был инициализирован (например, запустили с середины или без pre-render), выходим
    if render_stats['start_time'] is None:
        return

    current_time = time.time()
    
    # В Single Process режиме этот скрипт вызывается ОЧЕНЬ быстро во время генерации.
    # Мы не хотим, чтобы он портил статистику "фейковыми" быстрыми кадрами, 
    # ЕСЛИ у нас работает File Watcher.
    
    # Время последнего кадра (или старта)
    last_t = render_stats['last_frame_time']
    if last_t is None: last_t = render_stats['start_time']
    frame_duration = current_time - last_t
    
    # --- LAZY START WATCHER ---
    # Если кадры летят очень быстро (генерация USD), а Watcher не работает
    if frame_duration < 0.2 and not watcher_thread:
         print(f"[RenderEstimator] Fast frame detected ({frame_duration:.4f}s). Attempting LAZY START of File Watcher...")
         # Пытаемся запустить
         if try_start_file_watcher(hou.pwd()):
             # Если запустился, то выходим, чтобы не портить статистику первыми быстрыми кадрами
             # (Watcher сам найдет файлы)
             print("[RenderEstimator] Lazy start successful. Handing over to File Watcher.")
             render_stats['last_frame_time'] = current_time
             return
         else:
             print("[RenderEstimator] Lazy start failed.")

    # Если watcher работает, мы игнорируем быстрые вызовы post_frame
    if watcher_thread and watcher_thread.is_alive():
        # Если это реально генерация
        if frame_duration < 0.5:
            # print(f"[RenderEstimator] Generating scene... (Watcher Active)")
            render_stats['last_frame_time'] = current_time
            return
        else:
             # Если это НЕ генерация (вдруг?), но вотчер работает...
             # Лучше довериться вотчеру, если он включен.
             render_stats['last_frame_time'] = current_time
             return

    # Обычный режим (без Watcher)
    
    # --- File Size Tracking ---
    try:
        current_frame = int(hou.frame())
        out_parm = get_output_path_parm(hou.pwd())
        if out_parm:
             file_path = out_parm.evalAtFrame(current_frame)
             if file_path and os.path.exists(file_path):
                 size_bytes = os.path.getsize(file_path)
                 render_stats['total_size_bytes'] += size_bytes
    except Exception:
        pass

    render_stats['frames_rendered'] += 1
    
    # Время с начала рендера
    elapsed_total = current_time - render_stats['start_time']
    render_stats['last_frame_time'] = current_time
    
    # Сохраняем статистику по кадру
    try:
        current_frame = int(hou.frame())
    except:
        current_frame = render_stats['frames_rendered']
        
    render_stats['frame_times'].append((current_frame, frame_duration))
    
    # Среднее время на кадр
    avg_time_per_frame = elapsed_total / render_stats['frames_rendered']
    
    # Оставшиеся кадры
    remaining_frames = render_stats['total_frames'] - render_stats['frames_rendered']
    
    if remaining_frames < 0:
        remaining_frames = 0
        
    # Прогноз оставшегося времени
    estimated_remaining_seconds = avg_time_per_frame * remaining_frames
    
    # Форматирование времени
    time_str = str(datetime.timedelta(seconds=int(estimated_remaining_seconds)))
    elapsed_str = str(datetime.timedelta(seconds=int(elapsed_total)))
    
    # Обычный режим рендера
    msg = (f"[RenderEstimator] Кадр {render_stats['frames_rendered']}/{render_stats['total_frames']} готов. "
           f"Прошло: {elapsed_str}. Осталось: {time_str} ({avg_time_per_frame:.1f} сек/кадр)")
    
    print(msg)
    
    # Также можно обновлять статус бар Houdini
    try:
        hou.ui.setStatusMessage(msg)
    except:
        pass

def finalize_and_send_report():
    """
    Формирует и отправляет итоговый отчет.
    Используется как FileWatcher'ом, так и finish_render'ом.
    """
    global render_stats
    
    if render_stats['start_time'] is None:
        return

    total_time = time.time() - render_stats['start_time']
    total_time_str = str(datetime.timedelta(seconds=int(total_time)))
    
    avg_time = 0
    min_time_str = "N/A"
    max_time_str = "N/A"
    
    # Определяем, сколько кадров реально готово
    reported_frames = render_stats['frames_rendered']
    
    # Фолбэк logic: Если frames_rendered 0, но прошло много времени и total_frames > 0
    if reported_frames == 0 and total_time > 10 and render_stats['total_frames'] > 0:
         reported_frames = render_stats['total_frames']

    if reported_frames > 0:
        avg_time = total_time / reported_frames
        
        # Вычисляем мин/макс
        if render_stats['frame_times']:
            try:
                min_frame = min(render_stats['frame_times'], key=lambda x: x[1])
                max_frame = max(render_stats['frame_times'], key=lambda x: x[1])
                
                min_time_str = f"{min_frame[1]:.1f}s ({min_frame[0]} кадр)"
                max_time_str = f"{max_frame[1]:.1f}s ({max_frame[0]} кадр)"
            except:
                pass
    
    # Расчет размера
    total_size_mb = render_stats.get('total_size_bytes', 0) / (1024 * 1024)
    if total_size_mb > 1024:
        size_str = f"{total_size_mb/1024:.2f} GB"
    else:
        size_str = f"{total_size_mb:.2f} MB"
        
    stats_block = (
        f"📊 Статистика:\n"
        f"• Всего кадров: {render_stats['total_frames']} (Рендер: {reported_frames})\n"
        f"• Общее время: {total_time_str}\n"
        f"• Среднее на кадр: {avg_time:.1f} сек\n"
        f"• 💾 Размер: {size_str}"
    )
    
    if min_time_str != "N/A":
        stats_block += (
            f"\n• Мин. время: {min_time_str}\n"
            f"• Макс. время: {max_time_str}"
        )

    msg = (
        f"✅ Рендер завершен!\n\n"
        f"📂 Файл: {render_stats['hip_name']}\n"
        f"🕸 Нода: {render_stats['rop_name']}\n"
        f"🖥 Хост: {render_stats['hostname']}\n"
        f"🎨 Рендер: {render_stats['renderer']}\n"
        f"📷 Камера: {render_stats['camera_name']}\n"
        f"💡 Свет: {', '.join(render_stats['lights'][:5]) + ('...' if len(render_stats['lights']) > 5 else '') if render_stats['lights'] else 'Не найдено'}\n"
        f"📐 Разрешение: {render_stats['resolution']}\n"
        f"📂 Путь: {render_stats.get('output_path', 'Unknown')}\n"
        f"{stats_block}"
    )
    
    try:
        send_telegram_notification(msg)
    except Exception as e:
        print(f"[RenderEstimator] Ошибка отправки Telegram: {e}")


def finish_render():
    """
    Функция для 'Post-Render Script'.
    """
    global render_stats, watcher_thread, stop_watcher_event
    
    # Если Watcher работает
    if watcher_thread and watcher_thread.is_alive():
        # Проверяем, есть ли еще кадры для ожидания (в pending_frames внутри watcher thread)
        # Но pending_frames локальная переменная.
        # Мы можем косвенно проверить: frames_rendered < total_frames?
        # Или просто довериться Watcher'у.
        
        # Если это Detached render, watcher должен продолжать работу.
        # Если мы здесь, значит ROP "завершил" работу (или инициировал post-render).
        
        # ПРАВИЛО: Если Watcher запущен, ОН отвечает за отправку отчета.
        # finish_render просто выходит, чтобы не мешать, если watcher еще ждет файлы.
        
        # Единственный нюанс: как остановить watcher если пользователь ОТМЕНИЛ рендер?
        # Мы не знаем точно. Пусть watcher отвалится по таймауту или когда найдет файлы.
        
        print("[RenderEstimator] finish_render called. Handing over final report to active File Watcher.")
        
        # Если мы уверены, что рендер ВСЕ (все кадры найдены), можно ускорить выход watcher
        # Но у нас нет доступа к pending_frames из этого скоупа легко (без переделки в класс).
        # Поэтому просто выходим.
        return

    # Если watcher не работает (обычный рендер), отправляем сами
    finalize_and_send_report()


def load_env(env_path):
    """
    Простой парсер .env файла.
    Возвращает словарь с переменными.
    """
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    return env_vars


def send_telegram_notification(message):
    """
    Отправляет сообщение в Telegram, используя .env файл для токена и chat_id.
    """
    # 1. Пытаемся найти .env рядом со скриптом
    env_path = None
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        env_path = os.path.join(script_dir, '.env')
    except NameError:
        # Если __file__ не определен (специфика Houdini)
        pass
    
    # Если путь через __file__ не сработал или файл там не найден
    if not env_path or not os.path.exists(env_path):
        # Попробуем путь проекта (через HIP, если они рядом)
        hip_dir = os.path.dirname(hou.hipFile.path())
        env_path = os.path.join(hip_dir, '.env')
        
    # Если всё еще нет, проверяем рабочую директорию
    if not os.path.exists(env_path):
         env_path = os.path.join(os.getcwd(), '.env')
         
    env = load_env(env_path)
    
    token = env.get('TELEGRAM_BOT_TOKEN')
    chat_id = env.get('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print(f"[RenderEstimator] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not found in {env_path}")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message
    }
    
    headers = {'Content-Type': 'application/json'}
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            print(f"[RenderEstimator] Telegram notification sent. Status: {response.getcode()}")
    except urllib.error.HTTPError as e:
        print(f"[RenderEstimator] Telegram HTTP Error: {e.code} - {e.reason}")
        print(e.read().decode())
    except Exception as e:
        print(f"[RenderEstimator] Telegram Error: {e}")

