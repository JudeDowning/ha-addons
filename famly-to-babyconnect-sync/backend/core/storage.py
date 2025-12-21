from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from .config import DB_PATH
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
from .models import Base

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)

def init_db() -> None:
    """
    Create database tables if they do not exist.
    """
    Base.metadata.create_all(bind=engine)

@contextmanager
def get_session() -> Session:
    """
    Context manager that yields a database session and ensures it is closed.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
