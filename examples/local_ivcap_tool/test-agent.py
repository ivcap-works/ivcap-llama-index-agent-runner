import os
import sys
this_dir = os.path.dirname(__file__)
top_dir = os.path.abspath(os.path.join(this_dir, "../.."))
sys.path.append(top_dir)

from llama_index.core.agent import ReActAgent
from llama_index.llms.openai import OpenAI
from dotenv import load_dotenv
import logging
import argparse

from runner import wait_for_result, run_query
from tool import load_local_url_tool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent")
load_dotenv()

def_query = "Is 997 a prime number?"
parser = argparse.ArgumentParser(description="Test Agent for IsPrime tool")
parser.add_argument("query", nargs='?', default=def_query,
                    help="The query for the agent [\"%(default)s\"]", metavar="QUERY")
parser.add_argument('--model', type=str, default="gpt-3.5-turbo-instruct",
                    help="OpenAI model to use [%(default)s]", metavar="MODEL")
args = parser.parse_args()

query = args.query
logger.info(f"query: '{query}'")

llm = OpenAI(model="gpt-3.5-turbo-instruct")
tools = [
    load_local_url_tool("http://localhost:8090", os.path.join(this_dir, 'is-prime.tool.json')),
]
agent = ReActAgent.from_tools(tools, llm=llm, verbose=False)
result = wait_for_result(run_query(agent, query))
print(f">>>> Final response: {result}")
