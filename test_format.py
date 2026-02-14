
from utils import format_duration, format_frame_list

print("--- Testing Format Duration ---")

durations = [
    0.5,
    1.0,
    59.9,
    60.0,
    61.0,
    65.5,
    125.0,
    3600.0,
    3665.0
]

for d in durations:
    print(f"{d}s -> {format_duration(d)}")

print("\n--- Testing Format Frame List ---")
frame_lists = [
    [1],
    [1, 2, 3],
    [1, 3, 5],
    [1, 2, 3, 5, 6, 7, 10],
    [10, 9, 1, 2], # Unsorted and duplicates test (conceptually)
]

for fl in frame_lists:
    print(f"{fl} -> {format_frame_list(fl)}")

print("\n--- Expected Output ---")
print("0.5s -> 0.5 сек")
print("60.0s -> 1 мин 0 сек")
print("[1] -> 1")
print("[1, 2, 3] -> 1-3")
print("[1, 3, 5] -> 1, 3, 5")
print("[1, 2, 3, 5, 6, 7, 10] -> 1-3, 5-7, 10")
