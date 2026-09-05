from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Checkout(Base):
    __tablename__ = "checkouts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    razorpay_order_id = Column(String(255), unique=True, nullable=True, index=True)
    razorpay_payment_link_id = Column(String(255), unique=True, nullable=True, index=True)
    customer_phone = Column(String(50), index=True, nullable=False)
    cart_items = Column(JSON, nullable=False, default=list)
    total_amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(50), default="PENDING", index=True)  # PENDING, PAID, FAILED, CANCELLED
    discount_offered = Column(Numeric(5, 2), default=0.0)
    call_attempt_count = Column(Integer, default=0)
    last_call_triggered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    scheduled_jobs = relationship("ScheduledJob", back_populates="checkout", cascade="all, delete-orphan")


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    checkout_id = Column(String(36), ForeignKey("checkouts.id", ondelete="CASCADE"), nullable=True, index=True)
    phone = Column(String(50), nullable=True, index=True)
    celery_task_id = Column(String(255), nullable=True, index=True)
    job_type = Column(String(50), nullable=False)
    status = Column(String(50), default="PENDING", index=True)  # PENDING, CANCELLED, COMPLETED, FAILED
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    checkout = relationship("Checkout", back_populates="scheduled_jobs")


class AgentState(Base):
    __tablename__ = "agent_states"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    thread_id = Column(String(255), unique=True, nullable=False, index=True)
    state = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )