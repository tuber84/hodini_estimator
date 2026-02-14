
def format_duration(seconds):
    """
    Форматирует длительность в "X мин Y сек", если больше 60 сек,
    иначе "Z.z сек".
    """
    if seconds < 60:
        return f"{seconds:.1f} сек"
    else:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m} мин {s} сек"

def format_frame_list(frames):
    """
    Форматирует список кадров в компактную строку с диапазонами.
    Пример: [1, 2, 3, 5, 10] -> "1-3, 5, 10"
    """
    if not frames:
        return ""
        
    # Сортируем и убираем дубликаты
    sorted_frames = sorted(list(set(map(int, frames))))
    
    if not sorted_frames:
        return ""

    ranges = []
    start = sorted_frames[0]
    end = sorted_frames[0]
    
    for i in range(1, len(sorted_frames)):
        frame = sorted_frames[i]
        if frame == end + 1:
            end = frame
        else:
            if start == end:
                ranges.append(str(start))
            else:
                ranges.append(f"{start}-{end}")
            start = frame
            end = frame
            
    # Добавляем последний диапазон
    if start == end:
        ranges.append(str(start))
    else:
        ranges.append(f"{start}-{end}")
        
    return ", ".join(ranges)
