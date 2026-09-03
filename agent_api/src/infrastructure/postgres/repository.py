from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import anyio
from sqlalchemy import select

from src.infrastructure.postgres.core import SessionLocal
from src.infrastructure.postgres.models import AgentState, Checkout, ScheduledJob


def _uuid(value: str | UUID) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


async def create_checkout(
    *,
    customer_phone: str,
    cart_items: list[dict[str, Any]] | list[Any],
    total_amount: float | int,
    razorpay_order_id: str | None = None,
    status: str = "PENDING",
    discount_offered: float | int = 0.0,
) -> Checkout:
    checkout = Checkout(
        customer_phone=customer_phone,
        cart_items=list(cart_items),
        total_amount=float(total_amount),
        razorpay_order_id=razorpay_order_id,
        status=status,
        discount_offered=float(discount_offered),
    )

    def _txn():
        session = SessionLocal()
        try:
            session.add(checkout)
            session.commit()
            session.refresh(checkout)
            return checkout
        finally:
            session.close()

    return await anyio.to_thread.run_sync(_txn)


async def get_checkout(checkout_id: str | UUID) -> Checkout | None:
    def _qry():
        session = SessionLocal()
        try:
            result = session.execute(select(Checkout).where(Checkout.id == str(_uuid(checkout_id))))
            return result.scalar_one_or_none()
        finally:
            session.close()

    return await anyio.to_thread.run_sync(_qry)


async def list_checkouts_by_phone(customer_phone: str) -> list[Checkout]:
    def _qry():
        session = SessionLocal()
        try:
            result = session.execute(
                select(Checkout)
                .where(Checkout.customer_phone == customer_phone)
                .order_by(Checkout.created_at.desc())
            )
            return list(result.scalars().all())
        finally:
            session.close()

    return await anyio.to_thread.run_sync(_qry)


async def list_active_checkouts(customer_phone: str) -> list[dict[str, Any]]:
    def _qry():
        session = SessionLocal()
        try:
            result = session.execute(
                select(Checkout)
                .where(Checkout.customer_phone == customer_phone)
                .where(Checkout.status.not_in(["PAID", "CANCELLED"]))
                .order_by(Checkout.created_at.desc())
            )
            rows = result.scalars().all()
            return [
                {
                    "id": str(row.id),
                    "customer_phone": row.customer_phone,
                    "razorpay_order_id": row.razorpay_order_id,
                    "cart_items": row.cart_items,
                    "total_amount": float(row.total_amount),
                    "status": row.status,
                    "discount_offered": float(row.discount_offered or 0.0),
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ]
        finally:
            session.close()

    return await anyio.to_thread.run_sync(_qry)


async def update_checkout_status(
    checkout_id: str | UUID,
    *,
    status: str | None = None,
    razorpay_order_id: str | None = None,
) -> Checkout | None:
    def _txn():
        session = SessionLocal()
        try:
            checkout = session.get(Checkout, str(_uuid(checkout_id)))
            if checkout is None:
                return None
            if status is not None:
                checkout.status = status
            if razorpay_order_id is not None:
                checkout.razorpay_order_id = razorpay_order_id
            checkout.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(checkout)
            return checkout
        finally:
            session.close()

    return await anyio.to_thread.run_sync(_txn)


async def create_scheduled_job(
    *,
    phone: str | None = None,
    checkout_id: str | UUID | None = None,
    celery_task_id: str | None = None,
    job_type: str = "voice",
    status: str = "PENDING",
) -> ScheduledJob:
    job = ScheduledJob(
        phone=phone,
        checkout_id=str(_uuid(checkout_id)) if checkout_id is not None else None,
        celery_task_id=celery_task_id,
        job_type=job_type,
        status=status,
    )

    def _txn():
        session = SessionLocal()
        try:
            session.add(job)
            session.commit()
            session.refresh(job)
            return job
        finally:
            session.close()

    return await anyio.to_thread.run_sync(_txn)


async def update_scheduled_job_status(job_id: str | UUID, status: str) -> ScheduledJob | None:
    def _txn():
        session = SessionLocal()
        try:
            job = session.get(ScheduledJob, str(_uuid(job_id)))
            if job is None:
                return None
            job.status = status
            job.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(job)
            return job
        finally:
            session.close()

    return await anyio.to_thread.run_sync(_txn)


async def set_scheduled_job_celery_id(job_id: str | UUID, celery_task_id: str | None) -> ScheduledJob | None:
    def _txn():
        session = SessionLocal()
        try:
            job = session.get(ScheduledJob, str(_uuid(job_id)))
            if job is None:
                return None
            job.celery_task_id = celery_task_id
            job.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(job)
            return job
        finally:
            session.close()

    return await anyio.to_thread.run_sync(_txn)


async def get_scheduled_job(job_id: str | UUID) -> ScheduledJob | None:
    def _qry():
        session = SessionLocal()
        try:
            job = session.get(ScheduledJob, str(_uuid(job_id)))
            return job
        finally:
            session.close()

    return await anyio.to_thread.run_sync(_qry)


async def list_scheduled_jobs_for_checkout(checkout_id: str | UUID | None = None, phone: str | None = None) -> list[ScheduledJob]:
    def _qry():
        session = SessionLocal()
        try:
            stmt = select(ScheduledJob)
            filters = []
            if checkout_id is not None:
                filters.append(ScheduledJob.checkout_id == str(_uuid(checkout_id)))
            if phone is not None:
                filters.append(ScheduledJob.phone == phone)
            if filters:
                stmt = stmt.where(*filters)
            result = session.execute(stmt.order_by(ScheduledJob.created_at.desc()))
            return list(result.scalars().all())
        finally:
            session.close()

    return await anyio.to_thread.run_sync(_qry)


async def save_agent_state(thread_id: str, state: dict[str, Any]) -> AgentState:
    def _txn():
        session = SessionLocal()
        try:
            record = session.execute(select(AgentState).where(AgentState.thread_id == thread_id))
            record = record.scalar_one_or_none()
            if record is None:
                record = AgentState(thread_id=thread_id, state=state)
                session.add(record)
            else:
                record.state = state
                record.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(record)
            return record
        finally:
            session.close()

    return await anyio.to_thread.run_sync(_txn)


async def load_agent_state(thread_id: str) -> dict[str, Any] | None:
    def _qry():
        session = SessionLocal()
        try:
            result = session.execute(select(AgentState).where(AgentState.thread_id == thread_id))
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return dict(row.state or {})
        finally:
            session.close()

    return await anyio.to_thread.run_sync(_qry)


async def delete_agent_state(thread_id: str) -> bool:
    def _txn():
        session = SessionLocal()
        try:
            result = session.execute(select(AgentState).where(AgentState.thread_id == thread_id))
            row = result.scalar_one_or_none()
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True
        finally:
            session.close()

    return await anyio.to_thread.run_sync(_txn)
