"""
main.py  –  SFBS entry point
Run modes:
  python main.py server   → starts FastAPI server (default)
  python main.py gui      → launches Tkinter desktop GUI
  python main.py test     → runs all unit + integration tests
"""

import sys


def run_server():
    import uvicorn
    uvicorn.run(
        "server.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


def run_gui():
    from gui.app import SFBSApp
    SFBSApp().run()


def run_tests():
    import pytest
    raise SystemExit(
        pytest.main(["tests/", "-v", "--cov=.", "--cov-report=term-missing"])
    )


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "server"
    match mode:
        case "server": run_server()
        case "gui":    run_gui()
        case "test":   run_tests()
        case _:
            print(f"Unknown mode: {mode!r}")
            print("Usage: python main.py [server|gui|test]")
            sys.exit(1)
