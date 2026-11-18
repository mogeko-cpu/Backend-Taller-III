import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from flask import Flask, jsonify, request
from psycopg2.pool import ThreadedConnectionPool

app = Flask(__name__)

pool = ThreadedConnectionPool(
    minconn=1,
    maxconn=int(os.getenv("DB_POOL_MAX", "10")),
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "postgres"),
    dbname=os.getenv("DB_NAME", "orders_db"),
)


def validate(data):
    if not isinstance(data, dict):
        return "Body must be a JSON object"
    if not data.get("customerId"):
        return "customerId is required"
    items = data.get("items")
    if not isinstance(items, list) or not items:
        return "items must be a non-empty list"
    for i, it in enumerate(items):
        if not isinstance(it, dict) or not it.get("productId"):
            return f"items[{i}].productId is required"
        q, p = it.get("quantity"), it.get("price")
        if not isinstance(q, int) or q <= 0:
            return f"items[{i}].quantity must be a positive integer"
        if not isinstance(p, (int, float)) or p < 0:
            return f"items[{i}].price must be a non-negative number"
    return None


@app.post("/api/orders")
def create_order():
    data = request.get_json(silent=True)
    error = validate(data)
    if error:
        return jsonify({"error": error}), 400

    items = data["items"]
    total = sum(Decimal(str(it["price"])) * it["quantity"] for it in items)
    total = total.quantize(Decimal("0.01"))
    items_count = sum(it["quantity"] for it in items)
    order_id = f"ORD-{uuid.uuid4()}"

    conn = pool.getconn()
    try:
        with conn:  # commit / rollback automático
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO orders (order_id, customer_id, total_amount, items_count)
                       VALUES (%s, %s, %s, %s) RETURNING created_at""",
                    (order_id, data["customerId"], total, items_count),
                )
                created_at = cur.fetchone()[0]
                cur.executemany(
                    """INSERT INTO order_items (order_id, product_id, quantity, price)
                       VALUES (%s, %s, %s, %s)""",
                    [(order_id, it["productId"], it["quantity"], it["price"]) for it in items],
                )
    except Exception as e:
        return jsonify({"error": "Database error", "detail": str(e)}), 500
    finally:
        pool.putconn(conn)

    return jsonify({
        "orderId": order_id,
        "customerId": data["customerId"],
        "totalAmount": float(total),
        "itemsCount": items_count,
        "createdAt": created_at.isoformat(),
        "processedAt": datetime.now(timezone.utc).isoformat(),
    }), 201


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5001")))
