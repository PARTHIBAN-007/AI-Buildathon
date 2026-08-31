from __future__ import annotations

from datetime import datetime
from sqlalchemy import Column, String, Numeric, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Checkout(Base):
    __tablename__ = "checkouts"
    id = Column(PGUUID(as_uuid=True), primary_key=True)
    razorpay_order_id = Column(String, unique=True, nullable=True)
    customer_phone = Column(String, index=True, nullable=False)
    cart_items = Column(JSON, nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(50), default="FAILED")
    discount_offered = Column(Numeric(5, 2), default=0.0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"
    id = Column(PGUUID(as_uuid=True), primary_key=True)
    checkout_id = Column(ForeignKey("checkouts.id", ondelete="CASCADE"))
    celery_task_id = Column(String(255), nullable=False)
    job_type = Column(String(50), nullable=False)
    status = Column(String(50), default="PENDING")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    checkout = relationship("Checkout", backref="scheduled_jobs")
