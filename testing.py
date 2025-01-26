from tool import load_example_tool, register_function_as_tool

# tool simulating IVCAP tool - requires json file
load_example_tool('examples/multiply-tool.json', lambda a, b: a * b)

# register local function as tool
def add(a: int, b: int) -> int:
    """Add two integers and returns the result integer"""
    return a + b
register_function_as_tool(add)