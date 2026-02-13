import hou
import time
import datetime
import signal_cash
import socket

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
    'lights': []
}

def start_render():
    """
    Функция для 'Pre-Render Script'.
    Инициализирует статистику перед началом рендера.
    """
    global render_stats
    render_stats['start_time'] = time.time()
    render_stats['last_frame_time'] = time.time()
    render_stats['frames_rendered'] = 0
    render_stats['frame_times'] = []
    
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

        # --- Определение разрешения ---
        res_val = "Unknown"
        
        # 1. Стандартные паметры (Mantra/Redshift/Standard ROPs)
        if rop_node.parm('resx') and rop_node.parm('resy'):
             res_val = f"{rop_node.evalParm('resx')}x{rop_node.evalParm('resy')}"
        elif rop_node.parm('tres1') and rop_node.parm('tres2'): # Иногда так называется
             res_val = f"{rop_node.evalParm('tres1')}x{rop_node.evalParm('tres2')}"
        
        # 2. Переопределения в Solaris (Karma ROP)
        # Если есть override_resolution (и он включен или просто существует как единственное место)
        if res_val == "Unknown":
            if rop_node.parm('override_resolution') and rop_node.evalParm('override_resolution'):
                 if rop_node.parm('res1') and rop_node.parm('res2'):
                     res_val = f"{rop_node.evalParm('res1')}x{rop_node.evalParm('res2')}"
        
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
        
    except Exception as e:
        print(f"[RenderEstimator] Ошибка при инициализации: {e}")
        # Если не удалось получить данные, ставим дефолт (бесконечность или 0)
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
    render_stats['frames_rendered'] += 1
    
    # Время с начала рендера
    elapsed_total = current_time - render_stats['start_time']
    
    # Время последнего кадра
    frame_duration = current_time - render_stats['last_frame_time']
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
    
    # Вывод сообщения
    msg = (f"[RenderEstimator] Кадр {render_stats['frames_rendered']}/{render_stats['total_frames']} готов. "
           f"Прошло: {elapsed_str}. Осталось: {time_str} ({avg_time_per_frame:.1f} сек/кадр)")
    
    print(msg)
    
    # Также можно обновлять статус бар Houdini
    try:
        hou.ui.setStatusMessage(msg)
    except:
        pass

def finish_render():
    """
    Функция для 'Post-Render Script'.
    Отправляет итоговую статистику в Telegram.
    """
    global render_stats
    
    if render_stats['start_time'] is None:
        return

    total_time = time.time() - render_stats['start_time']
    total_time_str = str(datetime.timedelta(seconds=int(total_time)))
    
    avg_time = 0
    min_time_str = "N/A"
    max_time_str = "N/A"
    
    if render_stats['frames_rendered'] > 0:
        avg_time = total_time / render_stats['frames_rendered']
        
        # Вычисляем мин/макс
        if render_stats['frame_times']:
            # frame_times это список (frame, duration)
            try:
                min_frame = min(render_stats['frame_times'], key=lambda x: x[1])
                max_frame = max(render_stats['frame_times'], key=lambda x: x[1])
                
                min_time_str = f"{min_frame[1]:.1f}s (f{min_frame[0]})"
                max_time_str = f"{max_frame[1]:.1f}s (f{max_frame[0]})"
            except:
                pass
    
    msg = (
        f"✅ Рендер завершен!\n\n"
        f"📂 Файл: {render_stats['hip_name']}\n"
        f"🕸 Нода: {render_stats['rop_name']}\n"
        f"🖥 Хост: {render_stats['hostname']}\n"
        f"🎨 Рендер: {render_stats['renderer']}\n"
        f"📷 Камера: {render_stats['camera_name']}\n"
        f"💡 Свет: {', '.join(render_stats['lights'][:5]) + ('...' if len(render_stats['lights']) > 5 else '') if render_stats['lights'] else 'Не найдено'}\n"
        f"📐 Разрешение: {render_stats['resolution']}\n"
        f"📊 Статистика:\n"
        f"• Всего кадров: {render_stats['frames_rendered']}\n"
        f"• Общее время: {total_time_str}\n"
        f"• Среднее на кадр: {avg_time:.1f} сек\n"
        f"• Мин. время: {min_time_str}\n"
        f"• Макс. время: {max_time_str}"
    )
    
    print(msg)
    
    try:
        signal_cash.send_telegram(msg)
    except Exception as e:
        print(f"[RenderEstimator] Ошибка отправки Telegram: {e}")

