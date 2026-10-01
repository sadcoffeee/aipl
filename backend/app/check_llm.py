# Written by an LLM to speed up testing the inference server. Not a part of the final app.
from __future__ import annotations

import json
import sys

from . import config, llm


def main() -> int:
    print(f"Base URL : {config.LLM_BASE_URL}")
    print(f"Model : {config.LLM_MODEL or '(not set)'}")
    print("Checking...\n")

    result = llm.check_connection()

    if not result["reachable"]:
        print("X Could not reach the inference server.")
        print(f"  {result['error']}\n")
        print("Things to check:")
        print("- is the engine running, and on that port?")
        print("- does the URL end in /v1 ?")
        print("- from another machine: is it bound to 0.0.0.0, not 127.0.0.1?")
        return 1

    print(f"Reachable. Models loaded: {', '.join(result['models']) or '(none)'}")

    if result["modelAvailable"] is False:
        print(f"X '{result['configuredModel']}' is not one of them.")
        print("  Set AIPL_LLM_MODEL to a name from the list above.")
        return 1

    if result["error"]:
        print(f"X {result['error']}")
        return 1

    print(f"Replied in {result['latencyMs']} ms: {result['reply']!r}")
    print(
        "Structured output (JSON schema) accepted."
        if result["structuredOutput"]
        else "! Structured output (JSON schema) was rejected"
    )
    print("\nFull result:")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())