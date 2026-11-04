"""Llena lapampa.db con datos inventados para probar el programa (no toca una base que ya tenga ventas)."""
import random, sys
from datetime import datetime, timedelta
import app  # al importarlo crea la base vacía con su estructura

c = app.db()
if c.execute('SELECT COUNT(*) FROM ventas').fetchone()[0]:
    sys.exit('Ya hay ventas en lapampa.db: no se agregó nada.')
random.seed(1)
for n in ('ANA PEREZ', 'CARLOS RUIZ', 'MARIA LOPEZ GOMEZ'): c.execute('INSERT OR IGNORE INTO clientes(nombre) VALUES(?)', (n,))
for n in ('LECHE', 'PAN', 'GASEOSAS', 'ARRIENDO', 'SERVICIOS'): c.execute('INSERT OR IGNORE INTO proveedores(nombre) VALUES(?)', (n,))
hoy = datetime.now()
for d in range(60, -1, -1):
    f = (hoy - timedelta(days=d)).strftime('%Y-%m-%d')
    for _ in range(random.randint(30, 70)):
        v = random.choice((2000, 3500, 5000, 8000, 12000, 20000)); m = random.choices(('Efectivo', 'Nequi', 'Bancolombia'), (85, 10, 5))[0]
        c.execute('INSERT INTO ventas(fecha,valor,valor_entregado,medio_pago,hora) VALUES(?,?,?,?,?)',
                  (f, v, v if m != 'Efectivo' else v, m, f'{random.choice((7,8,9,12,13,17,18)):02d}:{random.randint(0,59):02d}:00'))
    for pid in random.sample(range(1, 6), 2):
        c.execute("INSERT INTO pagos(fecha,categoria,proveedor_id,valor,medio_pago,quien) VALUES(?,'proveedor',?,?,'Efectivo',?)",
                  (f, pid, random.randint(20, 300) * 1000, random.choice(('Ana', 'Luis'))))
c.commit(); print('Listo: datos de ejemplo cargados. Ejecuta: python app.py')
