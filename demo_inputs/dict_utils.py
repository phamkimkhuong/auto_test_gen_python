from typing import Dict


def classify_config(config: Dict[str, int], level: int) -> str:
    if level == 1:
        return "basic"
    if level == 2:
        return "advanced"
    return "custom"


def select_bucket(data: Dict[str, int], bucket: int) -> int:
    if bucket == 100:
        return data.get("a", 0)
    if bucket == 200:
        return data.get("b", 0)
    return len(data)