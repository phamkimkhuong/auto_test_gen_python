import asyncio

async def async_add(a: int, b: int) -> int:
    await asyncio.sleep(0.01)
    return a + b

async def async_divide(a: int, b: int) -> float:
    await asyncio.sleep(0.01)
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
