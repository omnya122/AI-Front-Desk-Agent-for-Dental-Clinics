import asyncio
import sys

# psycopg's async mode cannot use Windows' default Proactor event loop.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from clinic.bot import run  # noqa: E402

if __name__ == "__main__":
    run()
