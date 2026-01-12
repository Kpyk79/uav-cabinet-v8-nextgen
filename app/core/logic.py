from datetime import datetime

def calculate_duration(takeoff_str: str, landing_str: str) -> int:
    fmt = "%H:%M"
    try:
        t_off = datetime.strptime(takeoff_str, fmt)
        t_land = datetime.strptime(landing_str, fmt)
        delta = t_land - t_off
        duration = int(delta.total_seconds() / 60)
        if duration < 0:
            duration += 1440
        return duration
    except ValueError:
        return 0
