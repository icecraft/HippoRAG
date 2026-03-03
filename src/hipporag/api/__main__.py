"""
Allow running the API module directly with: python -m hipporag.api
"""

from .app import run_server

if __name__ == "__main__":
    run_server()
