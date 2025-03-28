from tool import register_builtin_tool

# tool simulating IVCAP tool - requires json file
# load_example_tool('examples/multiply-tool.json', lambda a, b: a * b)


import math
from pydantic import BaseModel, Field

class R(BaseModel):
    number: int= Field(description="number to check if prime")
    is_prime: bool = Field(description="true if number is prime, false otherwise")


def is_prime(number: int) -> R:
    """
    Checks if a number is prime.

    Args:
        number: The number to check.

    Returns:
        True if the number is prime, False otherwise.
    """
    if number <= 1:
        return R(number=number, is_prime=False)
    if number <= 3:
        return R(number=number, is_prime=True)
    if number % 2 == 0 or number % 3 == 0:
        return R(number=number, is_prime=False)

    for i in range(5, int(math.sqrt(number)) + 1, 6):
        if number % i == 0 or number % (i + 2) == 0:
            return R(number=number, is_prime=False)
    return R(number=number, is_prime=True)
register_builtin_tool(is_prime)