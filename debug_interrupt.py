
from langgraph.types import interrupt
from langgraph.errors import GraphInterrupt
import inspect

try:
    interrupt("test")
except Exception as e:
    print(f"Caught exception type: {type(e)}")
    print(f"Is instance of GraphInterrupt: {isinstance(e, GraphInterrupt)}")
    print(f"Exception module: {type(e).__module__}")
    print(f"Exception name: {type(e).__name__}")
