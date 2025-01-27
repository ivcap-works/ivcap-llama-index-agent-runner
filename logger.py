import json
import logging
from logging.config import dictConfig
import os

def getLogger(name: str) -> logging.Logger:
    return logging.getLogger(name)

def service_log_config():
    return LOGGING_CONFIG

script_dir = os.path.dirname(__file__)
cfg_path = os.path.join(script_dir, "logging.json")
LOGGING_CONFIG={}
with open(cfg_path, 'r') as file:
    LOGGING_CONFIG = json.load(file)
    dictConfig(LOGGING_CONFIG)