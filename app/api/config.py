import os

DB_HOST = os.getenv("MINIPAY_DB_HOST", "localhost")
DB_PORT = int(os.getenv("MINIPAY_DB_PORT", "5432"))
DB_NAME = os.getenv("MINIPAY_DB_NAME", "minipay")
DB_USER = os.getenv("MINIPAY_DB_USER", "minipay")
DB_PASSWORD = os.getenv("MINIPAY_DB_PASSWORD", "minipay_local_dev_only")
API_KEY = os.getenv("MINIPAY_API_KEY", "")  # empty string = auth disabled (local/dev convenience only)
