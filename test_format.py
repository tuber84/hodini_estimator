
from utils import format_duration

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

print("\n--- Expected Output ---")
print("0.5s -> 0.5 сек")
print("60.0s -> 1 мин 0 сек")
print("125.0s -> 2 мин 5 сек")
