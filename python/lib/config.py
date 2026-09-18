"""Configuration loader: env vars, optionally overridden by a simple key=value
config file (e.g. --config .env.support). Never hardcodes credentials."""
import os


def load_config_file(path):
    if not path or not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


class Config:
    def __init__(self, config_file=None):
        load_config_file(config_file)
        self.db_host = os.getenv("MINIPAY_DB_HOST", "localhost")
        self.db_port = int(os.getenv("MINIPAY_DB_PORT", "5432"))
        self.db_name = os.getenv("MINIPAY_DB_NAME", "minipay")
        self.db_user = os.getenv("MINIPAY_DB_USER", "minipay")
        self.db_password = os.getenv("MINIPAY_DB_PASSWORD", "")
        self.api_url = os.getenv("MINIPAY_API_URL", "http://localhost:8080")
        self.api_key = os.getenv("MINIPAY_API_KEY", "")
        self.stuck_threshold_minutes = int(os.getenv("MINIPAY_STUCK_MINUTES", "15"))

    def validate(self):
        missing = []
        if not self.db_host:
            missing.append("MINIPAY_DB_HOST")
        if not self.db_name:
            missing.append("MINIPAY_DB_NAME")
        if not self.db_user:
            missing.append("MINIPAY_DB_USER")
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
