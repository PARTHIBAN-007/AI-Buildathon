from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select

from src.infrastructure.postgres.core import async_session_factory
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
    async with async_session_factory() as session:
        session.add(checkout)
        await session.commit()
        await session.refresh(checkout)
        return checkout


async def get_checkout(checkout_id: str | UUID) -> Checkout | None:
    async with async_session_factory() as session:
        result = await session.execute(
            select(Checkout).where(Checkout.id == str(_uuid(checkout_id)))
        )
        return result.scalar_one_or_none()


async def list_checkouts_by_phone(customer_phone: str) -> list[Checkout]:
    async with async_session_factory() as session:
        result = await session.execute(
            select(Checkout)
            .where(Checkout.customer_phone == customer_phone)
            .order_by(Checkout.created_at.desc())
        )
        return list(result.scalars().all())


async def list_active_checkouts(customer_phone: str) -> list[dict[str, Any]]:
    async with async_session_factory() as session:
        result = await session.execute(
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


async def update_checkout_status(
    checkout_id: str | UUID,
    *,
    status: str | None = None,
    razorpay_order_id: str | None = None,
) -> Checkout | None:
    async with async_session_factory() as session:
        checkout = await session.get(Checkout, str(_uuid(checkout_id)))
        if checkout is None:
            return None
        if status is not None:
            checkout.status = status
        if razorpay_order_id is not None:
            checkout.razorpay_order_id = razorpay_order_id
        checkout.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(checkout)
        return checkout


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
    async with async_session_factory() as session:
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job


async def update_scheduled_job_status(job_id: str | UUID, status: str) -> ScheduledJob | None:
    async with async_session_factory() as session:
        job = await session.get(ScheduledJob, str(_uuid(job_id)))
        if job is None:
            return None
        job.status = status
        job.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(job)
        return job


async def get_scheduled_job(job_id: str | UUID) -> ScheduledJob | None:
    async with async_session_factory() as session:
        job = await session.get(ScheduledJob, str(_uuid(job_id)))
        return job


async def list_scheduled_jobs_for_checkout(checkout_id: str | UUID | None = None, phone: str | None = None) -> list[ScheduledJob]:
    async with async_session_factory() as session:
        stmt = select(ScheduledJob)
        filters = []
        if checkout_id is not None:
            filters.append(ScheduledJob.checkout_id == str(_uuid(checkout_id)))
        if phone is not None:
            filters.append(ScheduledJob.phone == phone)
        if filters:
            stmt = stmt.where(*filters)
        result = await session.execute(stmt.order_by(ScheduledJob.created_at.desc()))
        return list(result.scalars().all())


async def save_agent_state(thread_id: str, state: dict[str, Any]) -> AgentState:
    async with async_session_factory() as session:
        record = await session.execute(
            select(AgentState).where(AgentState.thread_id == thread_id)
        )
        record = record.scalar_one_or_none()
        if record is None:
            record = AgentState(thread_id=thread_id, state=state)
            session.add(record)
        else:
            record.state = state
            record.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(record)
        return record


async def load_agent_state(thread_id: str) -> dict[str, Any] | None:
    async with async_session_factory() as session:
        result = await session.execute(
            select(AgentState).where(AgentState.thread_id == thread_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return dict(row.state or {})


async def delete_agent_state(thread_id: str) -> bool:
    async with async_session_factory() as session:
        result = await session.execute(
            select(AgentState).where(AgentState.thread_id == thread_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await session.delete(row)
        await session.commit()
        return True
