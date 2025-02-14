#
# This file contains the list of built-in tools
#
from tool import register_builtin_tool

# tool simulating IVCAP tool - requires json file
# load_example_tool('examples/multiply-tool.json', lambda a, b: a * b)

### ADD

def addInt(a: int, b: int) -> int:
    """Add two integers and returns the result integer

    Args:
        a: First number
        b: Second number

    Returns:
       The addition of the two input numbers
    """
    return a + b
register_builtin_tool(addInt)

def addFloat(a: float, b: float) -> float:
    """Add two float numbers and returns the result as float"""
    return a + b
register_builtin_tool(addFloat)

### MULTIPLY

def mulInt(a: int, b: int) -> int:
    """Multiply two integers and returns the result integer"""
    return a * b
register_builtin_tool(mulInt)

def mulFloat(a: int, b: int) -> int:
    """Multiply two float numbers and returns the result as float"""
    return a * b
register_builtin_tool(mulFloat)

### DIVIDE

def divInt(a: int, b: int) -> int:
    """Divide two integers and returns the result integer"""
    return a * b
register_builtin_tool(divInt)

def divFloat(a: int, b: int) -> int:
    """Divide two float numbers and returns the result as float"""
    return a * b
register_builtin_tool(divFloat)

if __name__ == "__main__":
    import logging
    from tool import builtinTools, tool_to_ivcap_definition

    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger("builtin-tools")

    for t in builtinTools:
        md = t.metadata
        fn = f"ivcap/{md.name}.tool.json"
        logger.info(f"Write IVCAP tool definition for '{md.name}' to '{fn}'")
        td = tool_to_ivcap_definition(t)
        with open(fn, 'w') as file:
            file.write(td.model_dump_json(indent=2, by_alias=True))