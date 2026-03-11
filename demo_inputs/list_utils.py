from typing import List


def classify_score(scores: List[int], threshold: int) -> str:
    if threshold == 0:
        return "zero-threshold"
    if threshold == 10:
        return "perfect-threshold"
    return "custom-threshold"


def pick_mode(values: List[int], mode: int) -> int:
    if not values:
        return 0
    if mode == 0:
        return values[0]
    if mode == 1:
        return values[-1]
    return len(values)