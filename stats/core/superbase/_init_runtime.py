import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv()

connection_url = (
    f"postgresql://{os.getenv("SUPERBASE_USER")}"
    f":{os.getenv("SUPERBASE_PASS")}@{os.getenv("SUPERBASE_URL")}:{os.getenv("SUPERBASE_PORT")}"
    f"/{os.getenv("SUPERBASE_NAME")}"
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
