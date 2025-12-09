from datetime import datetime
from typing import Optional

from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, Text, JSON, ForeignKey, UniqueConstraint

Base = declarative_base()

class Credential(Base):
    """
    Stores credentials for external services like Famly and Baby Connect.

    In a real deployment you should encrypt the password field or use an
    external secrets manager. For now this is a simple placeholder model.
    """
    __tablename__ = "credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_name: Mapped[str] = mapped_column(String(50), index=True)  # "famly" | "baby_connect"
    email: Mapped[str] = mapped_column(String(255))
    password_encrypted: Mapped[str] = mapped_column(Text)  # TODO: encrypt in real implementation
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Event(Base):
    """
    Normalised event model used for both Famly and Baby Connect.
    """
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("source_system", "fingerprint", name="uq_event_source_fingerprint"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_system: Mapped[str] = mapped_column(String(50), index=True)  # "famly" | "baby_connect"
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    child_name: Mapped[str] = mapped_column(String(255))
    event_type: Mapped[str] = mapped_column(String(50))  # "meal" | "nap" | "nappy" | "attendance" | ...
    start_time_utc: Mapped[datetime] = mapped_column(DateTime)
    end_time_utc: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    details_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SyncLink(Base):
    """
    Links a Famly event to a Baby Connect event and tracks status.
    """
    __tablename__ = "sync_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    famly_event_id: Mapped[int] = mapped_column(Integer, ForeignKey("events.id"))
    baby_event_id: Mapped[int] = mapped_column(Integer, ForeignKey("events.id"))
    status: Mapped[str] = mapped_column(String(50), default="synced")  # "synced" | "failed" | "updated"
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    famly_event: Mapped["Event"] = relationship("Event", foreign_keys=[famly_event_id])
    baby_event: Mapped["Event"] = relationship("Event", foreign_keys=[baby_event_id])


class IgnoredEvent(Base):
    """
    Stores fingerprints for Famly events the user chose to ignore.
    """
    __tablename__ = "ignored_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fingerprint: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
