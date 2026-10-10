from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from policy.compile import compile_policy  # noqa: E402
from policy.prompts import SAMPLE_POLICY  # noqa: E402


def main() -> int:
    result = compile_policy(SAMPLE_POLICY)
    print(result.model_dump_json(indent=2))
    print(f"model={os.getenv('ANTHROPIC_MODEL') or 'claude-haiku-5-5'}")
    return 0 if not result.used_fallback else 1


if __name__ == "__main__":
    raise SystemExit(main())
