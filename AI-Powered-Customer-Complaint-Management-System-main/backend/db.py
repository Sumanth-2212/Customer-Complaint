"""PostgreSQL async database models & session for the Complaint Intake app."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy import String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    complaint_source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(240), nullable=True)

    product_name: Mapped[str | None] = mapped_column(String(240), nullable=True)
    product_strength: Mapped[str | None] = mapped_column(String(120), nullable=True)
    batch_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    manufacturing_date: Mapped[str | None] = mapped_column(String(40), nullable=True)
    expiry_date: Mapped[str | None] = mapped_column(String(40), nullable=True)
    quantity_affected: Mapped[str | None] = mapped_column(String(60), nullable=True)

    complaint_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    complaint_date: Mapped[str | None] = mapped_column(String(40), nullable=True)
    complaint_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    initial_severity: Mapped[str | None] = mapped_column(String(40), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(40), nullable=True)

    status: Mapped[str] = mapped_column(String(40), default="Pending Triage")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "complaint_source": self.complaint_source,
            "customer_name": self.customer_name,
            "product_name": self.product_name,
            "product_strength": self.product_strength,
            "batch_number": self.batch_number,
            "manufacturing_date": self.manufacturing_date,
            "expiry_date": self.expiry_date,
            "quantity_affected": self.quantity_affected,
            "complaint_type": self.complaint_type,
            "complaint_date": self.complaint_date,
            "complaint_description": self.complaint_description,
            "initial_severity": self.initial_severity,
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    complaint_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("complaints.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(240))
    mime_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    storage_path: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "complaint_id": self.complaint_id,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Recall(Base):
    __tablename__ = "recalls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_number: Mapped[str] = mapped_column(String(120), index=True)
    product_name: Mapped[str | None] = mapped_column(String(240), nullable=True)
    affected_units: Mapped[str | None] = mapped_column(String(60), nullable=True)
    complaint_ids: Mapped[str | None] = mapped_column(Text, nullable=True)  # csv
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    initiated_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="Initiated")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "batch_number": self.batch_number,
            "product_name": self.product_name,
            "affected_units": self.affected_units,
            "complaint_ids": self.complaint_ids,
            "reason": self.reason,
            "initiated_by": self.initiated_by,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
