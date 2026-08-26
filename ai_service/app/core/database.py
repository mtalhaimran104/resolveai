import os
from sqlalchemy import create_engine
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "resolve_ai")
MYSQL_USER = os.getenv("MYSQL_USER", "resolve_ai_user")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "resolve_ai_password")
MYSQL_HOST = os.getenv("MYSQL_HOST", "db")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
DATABASE_URL = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
    f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)
