import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv()

connection_url = (
    f"postgresql://{os.getenv("SUPABASE_USER")}"
    f":{os.getenv("SUPABASE_PASS")}@{os.getenv("SUPABASE_URL")}:{os.getenv("SUPABASE_PORT")}"
    f"/{os.getenv("SUPABASE_NAME")}"
)

db = create_engine(connection_url, pool_pre_ping=True)

Base = declarative_base()

SessionFactory = sessionmaker(
    bind=db,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)

_session = SessionFactory