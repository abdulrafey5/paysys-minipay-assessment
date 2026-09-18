import logging
from contextlib import contextmanager
from typing import Optional

import psycopg2
import psycopg2.errors
import psycopg2.extras
from fastapi import FastAPI, Depends, HTTPException, Header, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, condecimal

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("minipay-api")

app = FastAPI(title="MiniPay API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def get_conn():
    return psycopg2.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        dbname=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        connect_timeout=3,
    )


@contextmanager
def db_cursor():
    conn = get_conn()
    try:
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    if not config.API_KEY:
        return  # auth disabled when no key is configured (local/dev only)
    if x_api_key != config.API_KEY:
        raise HTTPException(status_code=401, detail="invalid or missing API key")


class CustomerCreate(BaseModel):
    customer_ref: str = Field(..., min_length=1, max_length=40)
    name: str = Field(..., min_length=1, max_length=120)


class PaymentCreate(BaseModel):
    customer_ref: str = Field(..., min_length=1)
    transaction_ref: str = Field(..., min_length=1, max_length=50)
    amount: condecimal(gt=0, max_digits=14, decimal_places=2)
    force_failure: bool = Field(default=False, description="Testing aid: deterministically force a FAILED outcome")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.get("/health")
def health():
    try:
        with db_cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
        return {"status": "ok", "db": "reachable"}
    except Exception as e:
        logger.error("health check failed: %s", e)
        return JSONResponse(status_code=503, content={"status": "degraded", "db": "unreachable"})


@app.post("/api/customers", status_code=201, dependencies=[Depends(require_api_key)])
def create_customer(payload: CustomerCreate):
    try:
        with db_cursor() as cur:
            cur.execute(
                "INSERT INTO customers(customer_ref, name) VALUES (%s, %s) "
                "RETURNING id, customer_ref, name, created_at;",
                (payload.customer_ref, payload.name),
            )
            row = cur.fetchone()
        return dict(row)
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="customer_ref already exists")


@app.get("/api/customers/{customer_ref}/payments", dependencies=[Depends(require_api_key)])
def list_customer_payments(customer_ref: str):
    with db_cursor() as cur:
        cur.execute("SELECT id FROM customers WHERE customer_ref = %s;", (customer_ref,))
        cust = cur.fetchone()
        if not cust:
            raise HTTPException(status_code=404, detail="customer not found")
        cur.execute(
            "SELECT transaction_ref, amount, status, created_at, completed_at, failure_code "
            "FROM transactions WHERE customer_id = %s ORDER BY created_at DESC;",
            (cust["id"],),
        )
        rows = [dict(r) for r in cur.fetchall()]
    return {"customer_ref": customer_ref, "payments": rows}


@app.post("/api/payments", status_code=201, dependencies=[Depends(require_api_key)])
def create_payment(payload: PaymentCreate):
    with db_cursor() as cur:
        cur.execute("SELECT id FROM customers WHERE customer_ref = %s;", (payload.customer_ref,))
        cust = cur.fetchone()
        if not cust:
            raise HTTPException(status_code=404, detail="customer not found")

        # Idempotency: resubmitting a known transaction_ref returns the existing record, not a duplicate
        cur.execute(
            "SELECT id, transaction_ref, amount, status, created_at, completed_at, failure_code "
            "FROM transactions WHERE transaction_ref = %s;",
            (payload.transaction_ref,),
        )
        existing = cur.fetchone()
        if existing:
            return JSONResponse(
                status_code=200,
                content=jsonable_encoder(dict(existing)),
                headers={"Idempotent-Replay": "true"},
            )

        cur.execute(
            "INSERT INTO transactions(transaction_ref, customer_id, amount, status, created_at) "
            "VALUES (%s, %s, %s, 'PROCESSING', now()) RETURNING id;",
            (payload.transaction_ref, cust["id"], payload.amount),
        )
        tx_id = cur.fetchone()["id"]

        # Simulated synchronous processing outcome (demo business logic, not a real payment rail)
        success = (not payload.force_failure) and (hash(payload.transaction_ref) % 100 < 90)
        new_status = "SUCCESS" if success else "FAILED"
        failure_code = None if success else "UPSTREAM_ERROR"
        http_status = 200 if success else 500

        cur.execute(
            "UPDATE transactions SET status=%s, completed_at=now(), failure_code=%s WHERE id=%s "
            "RETURNING id, transaction_ref, amount, status, created_at, completed_at, failure_code;",
            (new_status, failure_code, tx_id),
        )
        tx = dict(cur.fetchone())

        cur.execute(
            "INSERT INTO callbacks(transaction_id, attempt_no, http_status, callback_status, attempted_at) "
            "VALUES (%s, 1, %s, %s, now());",
            (tx_id, http_status, new_status),
        )

    return tx


@app.get("/api/payments/{transaction_ref}", dependencies=[Depends(require_api_key)])
def get_payment(transaction_ref: str):
    with db_cursor() as cur:
        cur.execute(
            "SELECT t.id, t.transaction_ref, t.amount, t.status, t.created_at, t.completed_at, "
            "t.failure_code, c.customer_ref FROM transactions t "
            "JOIN customers c ON c.id = t.customer_id WHERE t.transaction_ref = %s;",
            (transaction_ref,),
        )
        tx = cur.fetchone()
        if not tx:
            raise HTTPException(status_code=404, detail="transaction not found")
        result = dict(tx)
        if tx["completed_at"] is not None:
            result["processing_duration_seconds"] = (tx["completed_at"] - tx["created_at"]).total_seconds()
        else:
            result["processing_duration_seconds"] = None
    return result
