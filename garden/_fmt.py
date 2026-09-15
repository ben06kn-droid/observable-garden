def pct(x: float) -> str:
    if x == 0:
        return "0%"
    if x < 0.01:
        return "<1%"
    if 0.99 < x < 1:
        return ">99%"
    return f"{100 * x:.0f}%"
