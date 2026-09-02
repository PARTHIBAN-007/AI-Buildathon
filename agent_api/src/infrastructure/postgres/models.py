from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Checkout(Base):
    __tablename__ = "checkouts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    razorpay_order_id = Column(String, unique=True, nullable=True)
    customer_phone = Column(String, index=True, nullable=False)
    cart_items = Column(JSON, nullable=False, default=list)
    total_amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(50), default="PENDING")
    discount_offered = Column(Numeric(5, 2), default=0.0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    scheduled_jobs = relationship("ScheduledJob", back_populates="checkout", cascade="all, delete-orphan")


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    checkout_id = Column(String(36), ForeignKey("checkouts.id", ondelete="CASCADE"), nullable=True)
    phone = Column(String(50), nullable=True)
    celery_task_id = Column(String(255), nullable=True)
    job_type = Column(String(50), nullable=False)
    status = Column(String(50), default="PENDING")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    checkout = relationship("Checkout", back_populates="scheduled_jobs")


class AgentState(Base):
    __tablename__ = "agent_states"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    thread_id = Column(String(255), unique=True, nullable=False, index=True)
    state = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
