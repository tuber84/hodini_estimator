
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
