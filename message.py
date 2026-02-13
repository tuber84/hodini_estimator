import ctypes

# Сообщение и заголовок
message = "Привет, мир!"
title = "Сообщение"

# Выводим сообщение
ctypes.windll.user32.MessageBoxW(0, message, title, 1)