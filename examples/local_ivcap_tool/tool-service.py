import os
import sys
from time import sleep

from fastapi.responses import FileResponse
this_dir = os.path.dirname(__file__)
top_dir = os.path.abspath(os.path.join(this_dir, "../.."))
sys.path.append(top_dir)

from fastapi import Body, FastAPI
from signal import signal, SIGTERM

from logger import getLogger, service_log_config
from pydantic import BaseModel, Field

import math

logger = getLogger("app")

# shutdown pod cracefully
signal(SIGTERM, lambda _1, _2: sys.exit(0))

title="AI tool to check for prime numbers"
description = """
AI tool to help dtermining if a number is a prime number.
"""

app = FastAPI(
    title=title,
    description=description,
    version=os.environ.get("VERSION", "???"),
    contact={
        "name": "Max Ott",
        "email": "max.ott@data61.csiro.au",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/license/MIT",
    },
    docs_url="/api",
    root_path=os.environ.get("IVCAP_ROOT_PATH", "")
)

###
# A more complex tool may want to define a ServiceRequest and ServiceResponse model

# class ServiceRequest(BaseModel):
#     number: int = Field(description="number to check")

# class ServiceResponse(BaseModel):
#     number: int= Field(description="number to check if prime")
#     is_prime: bool = Field(description="true if number is prime, false otherwise")

# @app.post("/")
# def run(req: ServiceRequest) -> ServiceResponse:
#     """
#     Checks if a number is prime.
#
#     Args:
#         req (Props): containing the number to check
#
#     Returns:
#         a Response object
#     """
#     res = is_prime(req.number) # may want to check if the parameters are as expected
#     return ServiceResponse(number=req.number, is_prime=res)

@app.post("/")
def is_prime(number: int = Body(..., embed=True)) -> bool:
    """
    Checks if a number is prime.

    Args:
        number: The number to check.

    Returns:
        True if the number is prime, False otherwise.
    """
    if number <= 1:
        return False
    if number <= 3:
        return True
    if number % 2 == 0 or number % 3 == 0:
        return False

    for i in range(5, int(math.sqrt(number)) + 1, 6):
        if number % i == 0 or number % (i + 2) == 0:
            return False

    return True


@app.get("/")
def get_metadata():
    fp = os.path.join(this_dir, 'is-prime.tool.json')
    return FileResponse(fp, media_type="application/json")

# Allows platform to check if everything is OK
@app.get("/_healtz")
def healtz():
    return {"version": os.environ.get("VERSION", "???")}

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description=title)
    parser.add_argument('--host', type=str, default=os.environ.get("HOST", "0.0.0.0"), help='Host address')
    parser.add_argument('--port', type=int, default=os.environ.get("PORT", "8090"), help='Port number')
    args = parser.parse_args()

    logger.info(f"{title} - {os.getenv('VERSION')}")
    uvicorn.run(app, host=args.host, port=args.port, log_config=service_log_config())