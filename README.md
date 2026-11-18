# Taller Benchmarking de APIs – Python + Flask

Microservicio `POST /api/orders` en Flask (Gunicorn) + PostgreSQL 16, en Docker.

## 1. Levantar el entorno

```bash
docker compose up -d --build
docker ps                       # evidencia: api-orders y db-orders corriendo
```

Las tablas `orders` y `order_items` se crean solas con `init.sql` al primer arranque.
(Si ya existía el volumen: `docker compose down -v` y volver a subir.)

## 2. Probar la API

PowerShell:
```powershell
curl.exe -X POST http://localhost:5001/api/orders -H "Content-Type: application/json" `
  -d '{\"customerId\":\"C123\",\"items\":[{\"productId\":\"P1\",\"quantity\":2,\"price\":10.5},{\"productId\":\"P2\",\"quantity\":1,\"price\":5.0}]}'
```

Respuesta esperada (201):
```json
{ "orderId": "ORD-…", "customerId": "C123", "totalAmount": 26.0, "itemsCount": 3,
  "createdAt": "…", "processedAt": "…" }
```

Verificar en la BD:
```bash
docker exec -it db-orders psql -U postgres -d orders_db -c "SELECT COUNT(*) FROM orders;"
```

## 3. JMeter

Abrir `jmeter/orders_test_plan.jmx` en JMeter. Ya trae: Thread Group, HTTP Request Defaults
(localhost:5001, /api/orders), Header Manager (Content-Type: application/json), HTTP Request POST
con el JSON, aserción de status 201, Summary Report y Aggregate Report.

El número de usuarios se pasa como propiedad. **En la GUI** se cambia en el Thread Group
(campo "Number of Threads") o se lanza la GUI con la propiedad:

```bash
jmeter -Jusers=10 -t jmeter/orders_test_plan.jmx
```

**Modo CLI** (recomendado para medir; luego cargas el .jtl en la GUI para los pantallazos):

```bash
jmeter -n -t jmeter/orders_test_plan.jmx -Jusers=10  -Jduration=60 -l resultados/baja_10.jtl  -e -o resultados/html_baja_10
jmeter -n -t jmeter/orders_test_plan.jmx -Jusers=50  -Jduration=60 -l resultados/media_50.jtl -e -o resultados/html_media_50
jmeter -n -t jmeter/orders_test_plan.jmx -Jusers=100 -Jduration=60 -l resultados/alta_100.jtl -e -o resultados/html_alta_100
```

Propiedades: `users` (def. 20), `rampup` s (def. 10), `duration` s (def. 60), `host`, `port`.

### Escenario de estrés (de 20 en 20)

PowerShell:
```powershell
foreach ($u in 20,40,60,80,100,120,140,160,180,200) {
  jmeter -n -t jmeter/orders_test_plan.jmx -Jusers=$u -Jduration=60 -l "resultados/estres_$u.jtl"
}
```
Detenerse cuando suba el % de error o el P95 se dispare: ese es el punto de estrés.

> El PDF menciona también 20/70/150 usuarios; con el mismo comando solo cambia `-Jusers`.

## 4. Monitoreo durante cada prueba

En otra terminal, mientras corre JMeter:
```bash
docker stats api-orders db-orders
```
`htop` (Linux/WSL). En Windows sin WSL: Administrador de tareas / `docker stats` como evidencia.

Entre escenarios conviene limpiar la BD para que todos partan igual:
```bash
docker exec -it db-orders psql -U postgres -d orders_db -c "TRUNCATE orders, order_items RESTART IDENTITY;"
```

## 5. Tabla de resultados individuales (Flask)

| Escenario | Usuarios | Avg (ms) | P95 (ms) | Throughput (req/s) | % Error | Observaciones |
|---|---|---|---|---|---|---|
| Baja  | 10  | | | | | |
| Media | 50  | | | | | |
| Alta  | 100 | | | | | |
| Estrés | ? | | | | | |

| Escenario | CPU API (%) | RAM API (MiB) | CPU DB (%) | RAM DB (MiB) | Observaciones |
|---|---|---|---|---|---|
| Baja (10)  | | | | | |
| Media (50) | | | | | |
| Alta (100) | | | | | |
| Estrés (?) | | | | | |

### Evidencias a capturar
- Summary Report y Aggregate Report por escenario
- JMeter durante la carga
- `docker ps`
- `docker stats` / `htop` durante cada prueba

## Notas de diseño (útiles para las conclusiones)
- Se sirve con **Gunicorn** (4 workers × 4 hilos, `gthread`), no con el servidor de desarrollo de Flask,
  que no es apto para carga. Por el GIL, el paralelismo real viene de los procesos.
- Pool de conexiones `psycopg2` por worker (máx. 10 → hasta 40 conexiones; Postgres permite 100).
- Ambos INSERT van en una sola transacción (si falla uno, se hace rollback).
- Sin ORM (SQL directo con `executemany`), para no penalizar el rendimiento.
