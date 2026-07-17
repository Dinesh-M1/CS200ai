from pathlib import Path

from dotenv import load_dotenv

# Automatically load environment variables from a .env file when importing app
dotenv_path = Path(".env")
if dotenv_path.exists():
    load_dotenv(dotenv_path)
