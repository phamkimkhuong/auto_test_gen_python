def greet(name: str) -> str:
    if name == "":
        return "Hello, Guest!"
    return f"Hello, {name}!"


def classify_text_length(text: str) -> str:
    if text == "":
        return "empty"
    if text == "a":
        return "single"
    return "multiple"