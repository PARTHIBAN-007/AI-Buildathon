from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID

import anyio
from sqlalchemy import or_, select

from src.infrastructure.postgres.core import SessionLocal
from src.infrastructure.postgres.models import AgentState, Checkout, ScheduledJob


def _uuid(value: str | UUID | None) -> UUID | None:
    """Safely coerces UUID or returns None if invalid format without raising ValueError."""
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    val_str = str(value).strip()
    try:
        return UUID(val_str)
    except ValueError:
        return None


async def create_checkout(
    *,
    customer_phone: str,
    cart_items: list[dict[str, Any]] | list[Any],
    total_amount: float | int,
    razorpay_order_id: str | None = None,
    razorpay_payment_link_id: str | None = None,
    status: str = "PENDING",
    discount_offered: float | int = 0.0,
) -> Checkout:
    def _txn():
        with SessionLocal() as session:
            try:
                checkout = Checkout(
                    customer_phone=customer_phone,
                    cart_items=list(cart_items),
                    total_amount=float(total_amount),
                    razorpay_order_id=razorpay_order_id,
                    razorpay_payment_link_id=razorpay_payment_link_id,
                    status=status,
                    discount_offered=float(discount_offered),
                )
                session.add(checkout)
                session.commit()
                session.refresh(checkout)
                session.expunge(checkout)
                return checkout
            except Exception:
                session.rollback()
                raise

    return await anyio.to_thread.run_sync(_txn)


async def update_checkout_payment_link(
    checkout_id: str, payment_link_id: str, discount_pct: float = 0.0
) -> None:
    """Updates the razorpay_payment_link_id and discount_offered on the Checkout model."""
    if not checkout_id or str(checkout_id).strip().lower() == "none":
        return

    clean_id = str(checkout_id).strip()

    def _update():
        with SessionLocal() as session:
            checkout = None
            parsed_id = _uuid(clean_id)
            
            if parsed_id:
                checkout = session.get(Checkout, str(parsed_id))
            elif clean_id.startswith("order_"):
                checkout = session.execute(
                    select(Checkout).where(Checkout.razorpay_order_id == clean_id)
                ).scalars().first()
            else:
                checkout = session.get(Checkout, clean_id)
                if not checkout:
                    checkout = session.execute(
                        select(Checkout).where(
                            or_(
                                Checkout.razorpay_order_id == clean_id,
                                Checkout.razorpay_payment_link_id == clean_id,
                            )
                        )
                    ).scalars().first()

            if checkout:
                checkout.razorpay_payment_link_id = payment_link_id
                if discount_pct > 0:
                    checkout.discount_offered = discount_pct
                session.commit()

    await anyio.to_thread.run_sync(_update)


async def list_active_checkouts(customer_phone: str) -> List[Checkout]:
    """Returns active unpaid Checkout ORM objects ordered by latest creation time."""
    def _qry() -> List[Checkout]:
        with SessionLocal() as session:
            result = session.execute(
                select(Checkout)
                .where(Checkout.customer_phone == customer_phone)
                .where(Checkout.status.not_in(["PAID", "CANCELLED"]))
                .order_by(Checkout.created_at.desc())
            )
            rows = result.scalars().all()
            for row in rows:
                session.expunge(row)
            return list(rows)

    return await anyio.to_thread.run_sync(_qry)


async def get_checkout(checkout_id: str | UUID) -> Optional[Checkout]:
    """Fetches a single Checkout ORM object by ID, Razorpay Order ID, or Payment Link ID."""
    def _qry() -> Optional[Checkout]:
        if not checkout_id:
            return None

        clean_id = str(checkout_id).strip()
        if not clean_id or clean_id.lower() == "none":
            return None

        with SessionLocal() as session:
            # 1. Direct query by order_ ID
            if clean_id.startswith("order_"):
                stmt = select(Checkout).where(Checkout.razorpay_order_id == clean_id)
                row = session.execute(stmt).scalars().first()
                if row:
                    session.expunge(row)
                    return row

            # 2. Query by UUID or string primary key ID
            parsed_id = _uuid(clean_id)
            target_id = str(parsed_id) if parsed_id else clean_id

            stmt = select(Checkout).where(Checkout.id == target_id)
            checkout = session.execute(stmt).scalars().first()
            if checkout:
                session.expunge(checkout)
                return checkout

            # 3. Fallback: match razorpay_order_id or payment_link_id
            stmt = select(Checkout).where(
                or_(
                    Checkout.razorpay_order_id == clean_id,
                    Checkout.razorpay_payment_link_id == clean_id,
                )
            )
            checkout = session.execute(stmt).scalars().first()
            if checkout:
                session.expunge(checkout)
                return checkout

            return None

    return await anyio.to_thread.run_sync(_qry)


async def find_checkout_by_ids(
    *,
    checkout_id: str | UUID | None = None,
    razorpay_order_id: str | None = None,
    razorpay_payment_link_id: str | None = None,
) -> Checkout | None:
    """Finds a checkout record matching checkout_id, razorpay_payment_link_id, or razorpay_order_id."""
    def _qry():
        with SessionLocal() as session:
            raw_checkout_id = str(checkout_id).strip() if checkout_id else None
            effective_order_id = razorpay_order_id

            # If LLM passed order_... inside checkout_id, route it to order ID filter
            if raw_checkout_id and raw_checkout_id.startswith("order_") and not effective_order_id:
                effective_order_id = raw_checkout_id

            parsed_id = _uuid(raw_checkout_id) if raw_checkout_id else None
            conditions = []
            
            if parsed_id:
                conditions.append(Checkout.id == str(parsed_id))
            elif raw_checkout_id and not raw_checkout_id.startswith("order_"):
                conditions.append(Checkout.id == raw_checkout_id)

            if razorpay_payment_link_id:
                conditions.append(Checkout.razorpay_payment_link_id == razorpay_payment_link_id)
            if effective_order_id:
                conditions.append(Checkout.razorpay_order_id == effective_order_id)

            if not conditions:
                return None

            result = session.execute(select(Checkout).where(or_(*conditions)))
            checkout = result.scalars().first()
            if checkout:
                session.expunge(checkout)
            return checkout

    return await anyio.to_thread.run_sync(_qry)


async def upsert_checkout(
    *,
    checkout_id: str | UUID | None = None,
    razorpay_order_id: str | None = None,
    razorpay_payment_link_id: str | None = None,
    customer_phone: str,
    total_amount: float | int = 0.0,
    status: str = "PENDING",
    cart_items: list[dict[str, Any]] | None = None,
) -> Checkout:
    """Creates a checkout or updates an existing record matching any provided ID."""
    def _txn():
        with SessionLocal() as session:
            try:
                checkout = None
                raw_checkout_id = str(checkout_id).strip() if checkout_id else None
                effective_order_id = razorpay_order_id

                if raw_checkout_id and raw_checkout_id.startswith("order_") and not effective_order_id:
                    effective_order_id = raw_checkout_id

                parsed_id = _uuid(raw_checkout_id) if raw_checkout_id else None

                if parsed_id:
                    checkout = session.get(Checkout, str(parsed_id))
                if checkout is None and razorpay_payment_link_id:
                    checkout = session.execute(
                        select(Checkout).where(Checkout.razorpay_payment_link_id == razorpay_payment_link_id)
                    ).scalar_one_or_none()
                if checkout is None and effective_order_id:
                    checkout = session.execute(
                        select(Checkout).where(Checkout.razorpay_order_id == effective_order_id)
                    ).scalar_one_or_none()

                now = datetime.now(timezone.utc)

                if checkout:
                    checkout.status = status
                    if effective_order_id:
                        checkout.razorpay_order_id = effective_order_id
                    if razorpay_payment_link_id:
                        checkout.razorpay_payment_link_id = razorpay_payment_link_id
                    if customer_phone and customer_phone != "UNKNOWN":
                        checkout.customer_phone = customer_phone
                    if total_amount > 0:
                        checkout.total_amount = float(total_amount)
                    checkout.updated_at = now
                else:
                    checkout = Checkout(
                        customer_phone=customer_phone,
                        cart_items=cart_items or [],
                        total_amount=float(total_amount),
                        razorpay_order_id=effective_order_id,
                        razorpay_payment_link_id=razorpay_payment_link_id,
                        status=status,
                    )
                    if parsed_id:
                        checkout.id = str(parsed_id)
                    session.add(checkout)

                session.commit()
                session.refresh(checkout)
                session.expunge(checkout)
                return checkout
            except Exception:
                session.rollback()
                raise

    return await anyio.to_thread.run_sync(_txn)


async def list_checkouts_by_phone(customer_phone: str) -> list[Checkout]:
    def _qry():
        with SessionLocal() as session:
            result = session.execute(
                select(Checkout)
                .where(Checkout.customer_phone == customer_phone)
                .order_by(Checkout.created_at.desc())
            )
            rows = list(result.scalars().all())
            for row in rows:
                session.expunge(row)
            return rows

    return await anyio.to_thread.run_sync(_qry)


async def get_checkout_by_razorpay_order_id(razorpay_order_id: str) -> Optional[Checkout]:
    """Fetch a Checkout record by its associated Razorpay order_id."""
    if not razorpay_order_id or not str(razorpay_order_id).strip():
        return None

    clean_order_id = str(razorpay_order_id).strip()

    def _qry():
        with SessionLocal() as session:
            stmt = select(Checkout).where(Checkout.razorpay_order_id == clean_order_id)
            result = session.execute(stmt)
            row = result.scalars().first()
            if row:
                session.expunge(row)
            return row

    return await anyio.to_thread.run_sync(_qry)


async def update_checkout_status(
    checkout_id: str | UUID,
    *,
    status: str | None = None,
    razorpay_order_id: str | None = None,
    razorpay_payment_link_id: str | None = None,
) -> Checkout | None:
    def _txn():
        with SessionLocal() as session:
            try:
                checkout = None
                raw_id = str(checkout_id).strip() if checkout_id else ""
                parsed_id = _uuid(checkout_id)

                if parsed_id:
                    checkout = session.get(Checkout, str(parsed_id))
                elif raw_id.startswith("order_"):
                    checkout = session.execute(
                        select(Checkout).where(Checkout.razorpay_order_id == raw_id)
                    ).scalars().first()

                if checkout is None:
                    return None

                if status is not None:
                    checkout.status = status
                if razorpay_order_id is not None:
                    checkout.razorpay_order_id = razorpay_order_id
                if razorpay_payment_link_id is not None:
                    checkout.razorpay_payment_link_id = razorpay_payment_link_id
                checkout.updated_at = datetime.now(timezone.utc)
                
                session.commit()
                session.refresh(checkout)
                session.expunge(checkout)
                return checkout
            except Exception:
                session.rollback()
                raise

    return await anyio.to_thread.run_sync(_txn)


async def record_checkout_call(checkout_id: str | UUID) -> Checkout | None:
    """Increments call_attempt_count and updates last_call_triggered_at timestamp."""
    def _txn():
        with SessionLocal() as session:
            try:
                checkout = None
                raw_id = str(checkout_id).strip() if checkout_id else ""
                parsed_id = _uuid(checkout_id)

                if parsed_id:
                    checkout = session.get(Checkout, str(parsed_id))
                elif raw_id.startswith("order_"):
                    checkout = session.execute(
                        select(Checkout).where(Checkout.razorpay_order_id == raw_id)
                    ).scalars().first()

                if checkout is None:
                    return None
                
                checkout.call_attempt_count = (checkout.call_attempt_count or 0) + 1
                checkout.last_call_triggered_at = datetime.now(timezone.utc)
                checkout.updated_at = datetime.now(timezone.utc)
                
                session.commit()
                session.refresh(checkout)
                session.expunge(checkout)
                return checkout
            except Exception:
                session.rollback()
                raise

    return await anyio.to_thread.run_sync(_txn)


async def create_scheduled_job(
    *,
    phone: str | None = None,
    checkout_id: str | UUID | None = None,
    celery_task_id: str | None = None,
    job_type: str = "voice",
    status: str = "PENDING",
    scheduled_at: datetime | None = None,
) -> ScheduledJob:
    def _txn():
        with SessionLocal() as session:
            try:
                parsed_fk = _uuid(checkout_id)
                job = ScheduledJob(
                    phone=phone,
                    checkout_id=str(parsed_fk) if parsed_fk is not None else None,
                    celery_task_id=celery_task_id,
                    job_type=job_type,
                    scheduled_at=scheduled_at,
                    status=status,
                )
                session.add(job)
                session.commit()
                session.refresh(job)
                session.expunge(job)
                return job
            except Exception:
                session.rollback()
                raise

    return await anyio.to_thread.run_sync(_txn)


async def update_scheduled_job_status(job_id: str | UUID, status: str) -> ScheduledJob | None:
    def _txn():
        with SessionLocal() as session:
            try:
                parsed_id = _uuid(job_id)
                if parsed_id is None:
                    return None
                job = session.get(ScheduledJob, str(parsed_id))
                if job is None:
                    return None
                job.status = status
                job.updated_at = datetime.now(timezone.utc)
                session.commit()
                session.refresh(job)
                session.expunge(job)
                return job
            except Exception:
                session.rollback()
                raise

    return await anyio.to_thread.run_sync(_txn)


async def cancel_scheduled_job(job_id: str | UUID) -> ScheduledJob | None:
    return await update_scheduled_job_status(job_id, status="CANCELLED")


async def set_scheduled_job_celery_id(job_id: str | UUID, celery_task_id: str | None) -> ScheduledJob | None:
    def _txn():
        with SessionLocal() as session:
            try:
                parsed_id = _uuid(job_id)
                if parsed_id is None:
                    return None
                job = session.get(ScheduledJob, str(parsed_id))
                if job is None:
                    return None
                job.celery_task_id = celery_task_id
                job.updated_at = datetime.now(timezone.utc)
                session.commit()
                session.refresh(job)
                session.expunge(job)
                return job
            except Exception:
                session.rollback()
                raise

    return await anyio.to_thread.run_sync(_txn)


async def get_scheduled_job(job_id: str | UUID) -> ScheduledJob | None:
    def _qry():
        with SessionLocal() as session:
            parsed_id = _uuid(job_id)
            if parsed_id is None:
                return None
            job = session.get(ScheduledJob, str(parsed_id))
            if job:
                session.expunge(job)
            return job

    return await anyio.to_thread.run_sync(_qry)


async def list_scheduled_jobs_for_checkout(
    checkout_id: str | UUID | None = None, phone: str | None = None
) -> list[ScheduledJob]:
    def _qry():
        with SessionLocal() as session:
            stmt = select(ScheduledJob)
            filters = []
            parsed_fk = _uuid(checkout_id)
            if parsed_fk is not None:
                filters.append(ScheduledJob.checkout_id == str(parsed_fk))
            if phone is not None:
                filters.append(ScheduledJob.phone == phone)
            if filters:
                stmt = stmt.where(*filters)
            result = session.execute(stmt.order_by(ScheduledJob.created_at.desc()))
            rows = list(result.scalars().all())
            for row in rows:
                session.expunge(row)
            return rows

    return await anyio.to_thread.run_sync(_qry)


async def save_agent_state(thread_id: str, state: dict[str, Any]) -> AgentState:
    def _txn():
        with SessionLocal() as session:
            try:
                result = session.execute(select(AgentState).where(AgentState.thread_id == thread_id))
                record = result.scalar_one_or_none()
                if record is None:
                    record = AgentState(thread_id=thread_id, state=state)
                    session.add(record)
                else:
                    record.state = state
                    record.updated_at = datetime.now(timezone.utc)
                session.commit()
                session.refresh(record)
                session.expunge(record)
                return record
            except Exception:
                session.rollback()
                raise

    return await anyio.to_thread.run_sync(_txn)


async def load_agent_state(thread_id: str) -> dict[str, Any] | None:
    def _qry():
        with SessionLocal() as session:
            result = session.execute(select(AgentState).where(AgentState.thread_id == thread_id))
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return dict(row.state or {})

    return await anyio.to_thread.run_sync(_qry)


async def delete_agent_state(thread_id: str) -> bool:
    def _txn():
        with SessionLocal() as session:
            try:
                result = session.execute(select(AgentState).where(AgentState.thread_id == thread_id))
                row = result.scalar_one_or_none()
                if row is None:
                    return False
                session.delete(row)
                session.commit()
                return True
            except Exception:
                session.rollback()
                raise

    return await anyio.to_thread.run_sync(_txn)