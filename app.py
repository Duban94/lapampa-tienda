import os, sys, json, sqlite3, threading, webbrowser, socket, time, io, glob, shutil, logging, traceback
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file

VERSION = '2.1'
FROZEN = getattr(sys, 'frozen', False)
if FROZEN:  # sin consola (--windowed) stdout/stderr no existen
    if sys.stdout is None: sys.stdout = open(os.devnull, 'w')
    if sys.stderr is None: sys.stderr = open(os.devnull, 'w')
BASE = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
# Instalado: los datos viven en %LOCALAPPDATA%\LaPampa (se conservan al actualizar o desinstalar el programa).
# Si ya hay una lapampa.db junto al .exe (instalación anterior), se sigue usando esa: nada se mueve ni se pierde.
DATOS = BASE if (not FROZEN or os.path.exists(os.path.join(BASE, 'lapampa.db'))) else os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'LaPampa')
os.makedirs(DATOS, exist_ok=True)
DB = os.path.join(DATOS, 'lapampa.db')
CFG = os.path.join(DATOS, 'config.json')
RESP = os.path.join(DATOS, 'Respaldos')
SEMILLA = os.path.join(getattr(sys, '_MEIPASS', BASE), 'lapampa.db')
if FROZEN and not os.path.exists(DB) and os.path.exists(SEMILLA):
    shutil.copyfile(SEMILLA, DB)  # primera vez: arranca con el historial incluido
logging.basicConfig(filename=os.path.join(DATOS, 'LaPampa.log'), level=logging.WARNING, format='%(asctime)s %(message)s')
PORT = 5055  # el 5000 lo usa AirPlay en los Mac nuevos
app = Flask(__name__, template_folder=os.path.join(getattr(sys, '_MEIPASS', BASE), 'templates'))

SCHEMA = '''
CREATE TABLE IF NOT EXISTS clientes(id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT UNIQUE,telefono TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS proveedores(id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS ventas(id INTEGER PRIMARY KEY AUTOINCREMENT,fecha TEXT,valor INTEGER,valor_entregado INTEGER DEFAULT 0,medio_pago TEXT,cliente_id INTEGER,hora TEXT,nota TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS pagos(id INTEGER PRIMARY KEY AUTOINCREMENT,fecha TEXT,categoria TEXT,proveedor_id INTEGER,valor INTEGER,medio_pago TEXT,nota TEXT DEFAULT '',quien TEXT DEFAULT '',hora TEXT);
CREATE TABLE IF NOT EXISTS credito_mov(id INTEGER PRIMARY KEY AUTOINCREMENT,fecha TEXT,cliente_id INTEGER,tipo TEXT,valor INTEGER,medio_pago TEXT DEFAULT '',nota TEXT DEFAULT '',hora TEXT);
CREATE TABLE IF NOT EXISTS equipos(id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT,fecha_compra TEXT,valor INTEGER,nota TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS mantenimientos(id INTEGER PRIMARY KEY AUTOINCREMENT,equipo_id INTEGER,fecha TEXT,descripcion TEXT,costo INTEGER);
CREATE INDEX IF NOT EXISTS i_v ON ventas(fecha);CREATE INDEX IF NOT EXISTS i_p ON pagos(fecha);CREATE INDEX IF NOT EXISTS i_c ON credito_mov(cliente_id);
'''
def db():
    c = sqlite3.connect(DB, timeout=10); c.row_factory = sqlite3.Row; return c
def q(sql, a=()):
    c = db()
    try: return [dict(r) for r in c.execute(sql, a)]
    finally: c.close()
def run(sql, a=()):
    c = db()
    try: cur = c.execute(sql, a); c.commit(); return cur.lastrowid
    finally: c.close()
def hoy(): return datetime.now().strftime('%Y-%m-%d')
def fecha_ok(f):
    f = f or hoy()
    try: datetime.strptime(f, '%Y-%m-%d')
    except ValueError: raise ValueError('Fecha inválida')
    if f > hoy(): raise ValueError('No se puede registrar en una fecha futura')
    return f
def hora_de(f):  # la hora solo es real si el registro es del día de hoy (sirve para analizar horas pico)
    return datetime.now().strftime('%H:%M:%S') if f == hoy() else None
@app.errorhandler(ValueError)
def _val(e): return jsonify(error=str(e)), 400
@app.errorhandler(Exception)
def _err(e):  # un error nunca debe dejar la pantalla rota: se anota en LaPampa.log y se avisa
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException): return e
    logging.error(traceback.format_exc()); return jsonify(error='No se pudo completar. Intenta de nuevo (el detalle quedó en LaPampa.log)'), 500
def cfg():
    try: return json.load(open(CFG, encoding='utf-8'))
    except Exception: return {}
def copia(prefijo):
    """Copia de seguridad puntual de la base actual en Respaldos (no la borra el limpiador automático)."""
    os.makedirs(RESP, exist_ok=True)
    ruta = os.path.join(RESP, f"{prefijo}-{datetime.now():%Y-%m-%d_%H%M%S}.db")
    src, dst = db(), sqlite3.connect(ruta); src.backup(dst); dst.close(); src.close(); return ruta
NUEVAS = (('ventas', 'hora', 'TEXT'), ('ventas', 'nota', "TEXT DEFAULT ''"), ('pagos', 'hora', 'TEXT'), ('credito_mov', 'hora', 'TEXT'))
def migrar():
    """Deja cualquier base (vieja o nueva) con la estructura actual. Si va a cambiar una base con datos, la copia antes."""
    c = db()
    try:
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='ventas'").fetchone():
            if any(col not in [r[1] for r in c.execute(f'PRAGMA table_info({t})')] for t, col, _ in NUEVAS): copia('antes-de-actualizar')
        c.executescript(SCHEMA)
        for t, col, tipo in NUEVAS:
            if col not in [r[1] for r in c.execute(f'PRAGMA table_info({t})')]: c.execute(f'ALTER TABLE {t} ADD COLUMN {col} {tipo}')
        c.execute('CREATE INDEX IF NOT EXISTS i_vh ON ventas(hora)')
        c.execute("INSERT OR IGNORE INTO clientes(nombre) VALUES('MOSTRADOR')"); c.commit()
    finally: c.close()
migrar()

# ---------- respaldos ----------
def respaldar():
    nombre = f"lapampa-{datetime.now():%Y-%m-%d}.db"; hechos = []
    for carpeta in (RESP, cfg().get('carpeta_nube', '')):
        if not carpeta: continue
        try:
            os.makedirs(carpeta, exist_ok=True)
            src, dst = db(), sqlite3.connect(os.path.join(carpeta, nombre))
            src.backup(dst); dst.close(); src.close(); hechos.append(carpeta)
            for viejo in sorted(glob.glob(os.path.join(carpeta, 'lapampa-*.db')))[:-30]: os.remove(viejo)
        except Exception as e: print('Respaldo falló en', carpeta, e)
    return hechos
def bucle_respaldo():
    while True: respaldar(); time.sleep(1800)

# ---------- clientes y proveedores ----------
DEUDA = '''COALESCE((SELECT SUM(valor) FROM ventas WHERE cliente_id=c.id AND medio_pago='Credito'),0)
 +COALESCE((SELECT SUM(valor) FROM credito_mov WHERE cliente_id=c.id AND tipo='saldo_inicial'),0)
 -COALESCE((SELECT SUM(valor) FROM credito_mov WHERE cliente_id=c.id AND tipo='abono'),0)'''
@app.route('/')
def index(): return render_template('index.html')

@app.route('/api/clientes', methods=['GET', 'POST'])
def clientes():
    if request.method == 'POST':
        j = request.json; n = (j.get('nombre') or '').upper().strip()
        if not n: return jsonify(error='Falta el nombre'), 400
        run('INSERT OR IGNORE INTO clientes(nombre,telefono) VALUES(?,?)', (n, j.get('telefono', '')))
        cid = q('SELECT id FROM clientes WHERE nombre=?', (n,))[0]['id']
        if int(j.get('saldo') or 0) > 0:
            run("INSERT INTO credito_mov(fecha,cliente_id,tipo,valor,nota) VALUES(?,?,'saldo_inicial',?,'Saldo inicial')", (hoy(), cid, int(j['saldo'])))
        return jsonify(ok=1, id=cid)
    return jsonify(q(f"SELECT c.id,c.nombre,c.telefono,{DEUDA} AS deuda FROM clientes c WHERE c.nombre<>'MOSTRADOR' ORDER BY c.nombre"))

@app.route('/api/cliente/<int:i>')
def cliente_mov(i):
    return jsonify(q('''SELECT 'venta' t,id,fecha,'Fiado' tipo,valor,'' medio,COALESCE(nota,'') nota FROM ventas WHERE cliente_id=? AND medio_pago='Credito'
      UNION ALL SELECT 'credito_mov',id,fecha,CASE tipo WHEN 'abono' THEN 'Abono' ELSE 'Saldo inicial' END,valor,medio_pago,COALESCE(nota,'') FROM credito_mov WHERE cliente_id=?
      ORDER BY fecha DESC,id DESC''', (i, i)))

@app.route('/api/gastos_nombres')
def gastos_nombres():  # lista para administrar: cuántos pagos y cuánto suma cada nombre
    return jsonify(q('''SELECT pr.id,pr.nombre,COUNT(p.id) n,COALESCE(SUM(p.valor),0) t FROM proveedores pr
      LEFT JOIN pagos p ON p.proveedor_id=pr.id GROUP BY pr.id ORDER BY pr.nombre'''))

@app.route('/api/proveedores/<int:i>', methods=['PUT', 'DELETE'])
def proveedor(i):
    if not q('SELECT 1 FROM proveedores WHERE id=?', (i,)): return jsonify(error='Ese nombre ya no existe'), 404
    if request.method == 'DELETE':
        if q('SELECT COUNT(*) n FROM pagos WHERE proveedor_id=?', (i,))[0]['n']: return jsonify(error='Tiene pagos registrados: renómbralo o únelo con otro en vez de borrarlo'), 400
        run('DELETE FROM proveedores WHERE id=?', (i,)); return jsonify(ok=1)
    n = (request.json.get('nombre') or '').upper().strip()
    if not n: return jsonify(error='Escribe el nombre'), 400
    otro = q('SELECT id FROM proveedores WHERE nombre=? AND id<>?', (n, i))
    if not otro: run('UPDATE proveedores SET nombre=? WHERE id=?', (n, i)); return jsonify(ok=1, unido=0)
    copia('antes-de-unir')  # ya existía ese nombre: se juntan los pagos de los dos
    run('UPDATE pagos SET proveedor_id=? WHERE proveedor_id=?', (otro[0]['id'], i)); run('DELETE FROM proveedores WHERE id=?', (i,))
    return jsonify(ok=1, unido=1)

@app.route('/api/proveedores', methods=['GET', 'POST'])
def proveedores():
    if request.method == 'POST':
        n = (request.json.get('nombre') or '').upper().strip()
        if n: run('INSERT OR IGNORE INTO proveedores(nombre) VALUES(?)', (n,))
        return jsonify(ok=1)
    return jsonify(q('SELECT * FROM proveedores ORDER BY nombre'))

# ---------- registros ----------
@app.route('/api/ventas', methods=['POST'])
def venta():
    j = request.json; v = int(j['valor']); m = j['medio']
    if v <= 0 or m not in ('Efectivo', 'Nequi', 'Bancolombia', 'Credito'): return jsonify(error='Datos inválidos'), 400
    if m == 'Credito' and not j.get('cliente_id'): return jsonify(error='Elige el cliente'), 400
    f = fecha_ok(j.get('fecha'))
    run('INSERT INTO ventas(fecha,valor,valor_entregado,medio_pago,cliente_id,hora,nota) VALUES(?,?,?,?,?,?,?)',
        (f, v, int(j.get('entregado') or 0) if m == 'Efectivo' else 0, m, j.get('cliente_id') if m == 'Credito' else None, hora_de(f), (j.get('nota') or '').strip() if m == 'Credito' else ''))
    return jsonify(ok=1)

@app.route('/api/ventas_dia')
def ventas_dia():
    return jsonify(q('''SELECT v.*,c.nombre cliente FROM ventas v LEFT JOIN clientes c ON c.id=v.cliente_id
      WHERE fecha=? ORDER BY v.id DESC''', (request.args.get('fecha') or hoy(),)))

@app.route('/api/pagos', methods=['POST'])
def pago():
    j = request.json; n = (j.get('nombre') or '').upper().strip(); v = int(j['valor'])
    if not n or v <= 0: return jsonify(error='Falta "Pagado a" o el valor'), 400
    run('INSERT OR IGNORE INTO proveedores(nombre) VALUES(?)', (n,))
    pid = q('SELECT id FROM proveedores WHERE nombre=?', (n,))[0]['id']
    f = fecha_ok(j.get('fecha'))
    run('INSERT INTO pagos(fecha,categoria,proveedor_id,valor,medio_pago,nota,quien,hora) VALUES(?,?,?,?,?,?,?,?)',
        (f, 'proveedor', pid, v, j['medio'], j.get('nota', ''), (j.get('quien') or '').strip().title(), hora_de(f)))
    return jsonify(ok=1)

@app.route('/api/credito_mov', methods=['POST'])
def credito_mov():
    j = request.json; v = int(j['valor'])
    if v <= 0 or not j.get('cliente_id'): return jsonify(error='Elige cliente y valor'), 400
    f = fecha_ok(j.get('fecha'))  # desde este módulo solo se registran abonos; si abona de más queda saldo a favor
    run('INSERT INTO credito_mov(fecha,cliente_id,tipo,valor,medio_pago,nota,hora) VALUES(?,?,?,?,?,?,?)',
        (f, j['cliente_id'], 'abono', v, j.get('medio', ''), j.get('nota', ''), hora_de(f)))
    return jsonify(ok=1)

@app.route('/api/equipos', methods=['GET', 'POST'])
def equipos():
    if request.method == 'POST':
        j = request.json
        run('INSERT INTO equipos(nombre,fecha_compra,valor,nota) VALUES(?,?,?,?)', (j['nombre'].strip(), fecha_ok(j.get('fecha')), int(j.get('valor') or 0), j.get('nota', '')))
        return jsonify(ok=1)
    return jsonify(q('''SELECT e.*,COALESCE((SELECT SUM(costo) FROM mantenimientos WHERE equipo_id=e.id),0) mant FROM equipos e ORDER BY fecha_compra DESC'''))

@app.route('/api/mantenimientos', methods=['GET', 'POST'])
def mants():
    if request.method == 'POST':
        j = request.json
        run('INSERT INTO mantenimientos(equipo_id,fecha,descripcion,costo) VALUES(?,?,?,?)', (j['equipo_id'], fecha_ok(j.get('fecha')), j['descripcion'].strip(), int(j.get('costo') or 0)))
        return jsonify(ok=1)
    return jsonify(q('SELECT * FROM mantenimientos ORDER BY fecha DESC'))

@app.route('/api/borrar/<tabla>/<int:i>', methods=['DELETE'])
def borrar(tabla, i):
    if tabla not in ('ventas', 'pagos', 'credito_mov', 'equipos', 'mantenimientos'): return jsonify(error='?'), 400
    if tabla == 'equipos': run('DELETE FROM mantenimientos WHERE equipo_id=?', (i,))
    run(f'DELETE FROM {tabla} WHERE id=?', (i,)); return jsonify(ok=1)

# ---------- editar registros ----------
TABLAS = ('ventas', 'pagos', 'credito_mov', 'equipos', 'mantenimientos')
@app.route('/api/registro/<tabla>/<int:i>')
def registro(tabla, i):
    if tabla not in TABLAS: return jsonify(error='?'), 400
    sql = {'ventas': 'SELECT v.*,c.nombre cliente FROM ventas v LEFT JOIN clientes c ON c.id=v.cliente_id WHERE v.id=?',
           'pagos': 'SELECT p.*,pr.nombre nombre FROM pagos p LEFT JOIN proveedores pr ON pr.id=p.proveedor_id WHERE p.id=?',
           'equipos': 'SELECT *,fecha_compra fecha FROM equipos WHERE id=?'}.get(tabla, f'SELECT * FROM {tabla} WHERE id=?')
    r = q(sql, (i,))
    return jsonify(r[0]) if r else (jsonify(error='Ese registro ya no existe'), 404)

@app.route('/api/editar/<tabla>/<int:i>', methods=['PUT'])
def editar(tabla, i):
    if tabla not in TABLAS: return jsonify(error='?'), 400
    j = request.json; ant = q(f'SELECT * FROM {tabla} WHERE id=?', (i,))
    if not ant: return jsonify(error='Ese registro ya no existe'), 404
    ant = ant[0]; f = fecha_ok(j.get('fecha')); v = int(j.get('valor') or j.get('costo') or 0); nota = (j.get('nota') or '').strip()
    if tabla == 'ventas':
        m = j.get('medio')
        if v <= 0 or m not in ('Efectivo', 'Nequi', 'Bancolombia', 'Credito'): return jsonify(error='Datos inválidos'), 400
        if m == 'Credito' and not j.get('cliente_id'): return jsonify(error='Elige el cliente'), 400
        ent = (int(j.get('entregado') or 0) or v) if m == 'Efectivo' else 0
        if m == 'Efectivo' and ent < v: return jsonify(error='Lo entregado es menor que la compra'), 400
        run('UPDATE ventas SET fecha=?,valor=?,valor_entregado=?,medio_pago=?,cliente_id=?,nota=?,hora=? WHERE id=?',
            (f, v, ent, m, j['cliente_id'] if m == 'Credito' else None, nota if m == 'Credito' else '', ant['hora'] if f == ant['fecha'] else None, i))
    elif tabla == 'pagos':
        n = (j.get('nombre') or '').upper().strip()
        if not n or v <= 0: return jsonify(error='Falta "Pagado a" o el valor'), 400
        run('INSERT OR IGNORE INTO proveedores(nombre) VALUES(?)', (n,)); pid = q('SELECT id FROM proveedores WHERE nombre=?', (n,))[0]['id']
        run('UPDATE pagos SET fecha=?,proveedor_id=?,valor=?,medio_pago=?,nota=?,quien=?,hora=? WHERE id=?',
            (f, pid, v, j.get('medio') or 'Efectivo', nota, (j.get('quien') or '').strip().title(), ant['hora'] if f == ant['fecha'] else None, i))
    elif tabla == 'credito_mov':
        if v <= 0: return jsonify(error='Falta el valor'), 400
        run('UPDATE credito_mov SET fecha=?,valor=?,medio_pago=?,nota=?,hora=? WHERE id=?', (f, v, j.get('medio') or '', nota, ant['hora'] if f == ant['fecha'] else None, i))
    elif tabla == 'equipos':
        if not (j.get('nombre') or '').strip(): return jsonify(error='Escribe el nombre'), 400
        run('UPDATE equipos SET nombre=?,fecha_compra=?,valor=?,nota=? WHERE id=?', (j['nombre'].strip(), f, v, nota, i))
    else:
        if not (j.get('descripcion') or '').strip(): return jsonify(error='Describe el trabajo'), 400
        run('UPDATE mantenimientos SET fecha=?,descripcion=?,costo=? WHERE id=?', (f, j['descripcion'].strip(), v, i))
    return jsonify(ok=1)

# ---------- cargar una copia / importar días desde Excel ----------
def guardar_subida(nombre_ext):
    f = request.files.get('archivo')
    if not f or not f.filename: raise ValueError('Elige un archivo')
    ruta = os.path.join(DATOS, '_subida' + nombre_ext(f.filename)); f.save(ruta); return ruta, f.filename

@app.route('/api/restaurar', methods=['POST'])
def restaurar():
    ruta, _ = guardar_subida(lambda n: '.db')
    try:
        c = sqlite3.connect(ruta)
        try:
            ok = c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            tablas = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            n = c.execute('SELECT COUNT(*) FROM ventas').fetchone()[0] if 'ventas' in tablas else 0
        except sqlite3.DatabaseError: ok, tablas, n = False, set(), 0
        finally: c.close()
        if not ok or not {'ventas', 'pagos', 'clientes'} <= tablas: raise ValueError('Ese archivo no es una base de datos de La Pampa')
        copia('antes-de-cargar')  # por si te equivocas de archivo: la base actual queda guardada
        src, dst = sqlite3.connect(ruta), db(); src.backup(dst); src.close(); dst.close()
    finally:
        try: os.remove(ruta)
        except OSError: pass
    migrar()
    return jsonify(ok=1, ventas=n)

def a_fecha(v):
    from datetime import date
    if isinstance(v, datetime): return v.strftime('%Y-%m-%d')
    if isinstance(v, date): return v.strftime('%Y-%m-%d')
    if isinstance(v, (int, float)) and 40000 < v < 60000: return (datetime(1899, 12, 30) + timedelta(days=float(v))).strftime('%Y-%m-%d')
    t = str(v or '').strip()[:10]
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try: return datetime.strptime(t, fmt).strftime('%Y-%m-%d')
        except ValueError: pass
    return None
def entero(v):
    if isinstance(v, (int, float)): return int(round(v))
    s = ''.join(ch for ch in str(v or '') if ch.isdigit()); return int(s) if s else 0
def clave(v): return ''.join(ch for ch in str(v or '').lower() if ch.isalnum())
def medio_de(v):
    t = str(v or '').lower()
    return 'Nequi' if 'nequi' in t else 'Bancolombia' if 'banco' in t else 'Credito' if 'credit' in t or 'crédit' in t else 'Efectivo'

def filas_hojas(ruta, ext):
    """Genera (nombre_hoja, iterador de filas) de un .xlsx o .xlsb."""
    if ext == '.xlsb':
        from pyxlsb import open_workbook
        with open_workbook(ruta) as wb:
            for n in wb.sheets:
                with wb.get_sheet(n) as sh: yield n, ([c.v for c in r] for r in sh.rows())
    else:
        from openpyxl import load_workbook
        wb = load_workbook(ruta, read_only=True, data_only=True)
        for ws in wb.worksheets: yield ws.title, (list(r) for r in ws.iter_rows(values_only=True))

def leer_excel(ruta, ext, desde, hasta):
    """Lee las hojas de ventas (Valor a Pagar / Fecha / Forma de Pago / Cliente) y de gastos (Empresa / Valor / Fecha / Facturado)."""
    ventas, pagos = [], []; vistas = set()
    for nombre, filas in filas_hojas(ruta, ext):
        cab = None; tipo = None
        for k, r in enumerate(filas):
            if cab is None:
                ks = [clave(x) for x in r]
                if 'fecha' in ks and ('empresa' in ks or 'pagadoa' in ks): tipo = 'g'
                elif 'fecha' in ks and ('valorapagar' in ks or ('valor' in ks and 'medio' in ks)): tipo = 'v'
                if tipo: cab = {x: n for n, x in enumerate(ks) if x and x not in {}}
                elif k > 15: break
                continue
            g = lambda *ns: next((r[cab[n]] for n in ns if n in cab and cab[n] < len(r)), None)
            f = a_fecha(g('fecha'))
            if not f or not (desde <= f <= hasta): continue
            if tipo == 'v':
                v = entero(g('valorapagar', 'valor'))
                if v <= 0: continue
                m = medio_de(g('formadepago', 'medio')); cl = str(g('cliente') or '').strip().upper()
                ventas.append(dict(fecha=f, valor=v, entregado=max(entero(g('valorentregado', 'entregado')), v) if m == 'Efectivo' else 0, medio=m, cliente=cl if cl not in ('', 'NONE', 'NAN') else ''))
            else:
                v = entero(g('valor')); n = str(g('empresa', 'pagadoa', 'proveedor') or '').strip().upper()
                if v <= 0 or not n: continue
                pagos.append(dict(fecha=f, nombre=n, valor=v, quien=str(g('facturado', 'quien') or '').replace('"', '').strip().title(), medio=medio_de(g('medio')) if 'medio' in cab else 'Efectivo'))
        if tipo: vistas.add(tipo)
    if not vistas: raise ValueError('No encontré las hojas de ventas ni de gastos en ese Excel (deben tener las columnas "Valor a Pagar" y "Fecha", y "Empresa", "Valor" y "Fecha").')
    return ventas, pagos

@app.route('/api/importar', methods=['POST'])
def importar():
    desde, hasta = fecha_ok(request.form.get('desde')), fecha_ok(request.form.get('hasta'))
    if desde > hasta: raise ValueError('La fecha "Desde" es mayor que "Hasta"')
    ruta, nombre = guardar_subida(lambda n: os.path.splitext(n)[1].lower() if os.path.splitext(n)[1].lower() in ('.xlsx', '.xlsb') else '.xlsx')
    try: ventas, pagos = leer_excel(ruta, os.path.splitext(ruta)[1], desde, hasta)
    finally:
        try: os.remove(ruta)
        except OSError: pass
    dias = sorted({x['fecha'] for x in ventas} | {x['fecha'] for x in pagos}); resumen = []
    for d in dias:
        vs, ps = [x for x in ventas if x['fecha'] == d], [x for x in pagos if x['fecha'] == d]
        dv = q("SELECT COUNT(*) n,COALESCE(SUM(valor),0) t FROM ventas WHERE fecha=?", (d,))[0]; dp = q('SELECT COUNT(*) n,COALESCE(SUM(valor),0) t FROM pagos WHERE fecha=?', (d,))[0]
        resumen.append(dict(fecha=d, v_excel=len(vs), v_excel_t=sum(x['valor'] for x in vs), v_base=dv['n'], v_base_t=dv['t'],
                            p_excel=len(ps), p_excel_t=sum(x['valor'] for x in ps), p_base=dp['n'], p_base_t=dp['t']))
    if request.form.get('guardar') != '1': return jsonify(resumen=resumen)
    if not dias: raise ValueError('No hay datos en esas fechas dentro del Excel')
    copia('antes-de-importar')
    c = db()
    try:
        if request.form.get('reemplazar') == '1':  # lo que está a crédito se conserva: el Excel no lo trae
            c.execute("DELETE FROM ventas WHERE fecha BETWEEN ? AND ? AND medio_pago<>'Credito'", (desde, hasta)); c.execute('DELETE FROM pagos WHERE fecha BETWEEN ? AND ?', (desde, hasta))
        for x in ventas:
            cid = None
            if x['medio'] == 'Credito':
                if x['cliente']: c.execute('INSERT OR IGNORE INTO clientes(nombre) VALUES(?)', (x['cliente'],)); cid = c.execute('SELECT id FROM clientes WHERE nombre=?', (x['cliente'],)).fetchone()[0]
                else: x['medio'] = 'Efectivo'; x['entregado'] = x['valor']
            c.execute('INSERT INTO ventas(fecha,valor,valor_entregado,medio_pago,cliente_id) VALUES(?,?,?,?,?)', (x['fecha'], x['valor'], x['entregado'], x['medio'], cid))
        for x in pagos:
            c.execute('INSERT OR IGNORE INTO proveedores(nombre) VALUES(?)', (x['nombre'],)); pid = c.execute('SELECT id FROM proveedores WHERE nombre=?', (x['nombre'],)).fetchone()[0]
            c.execute("INSERT INTO pagos(fecha,categoria,proveedor_id,valor,medio_pago,quien) VALUES(?,'proveedor',?,?,?,?)", (x['fecha'], pid, x['valor'], x['medio'], x['quien']))
        c.commit()
    finally: c.close()
    return jsonify(ok=1, ventas=len(ventas), pagos=len(pagos), resumen=resumen)

@app.route('/api/version')
def version(): return jsonify(version=VERSION)

@app.route('/api/historial')
def historial():
    d, h, quien = request.args.get('desde') or hoy(), request.args.get('hasta') or hoy(), request.args.get('quien') or ''
    return jsonify(q('''SELECT * FROM (
      SELECT v.id,v.fecha,v.hora,'ventas' t,'Venta' tipo,COALESCE(c.nombre,'')||CASE WHEN COALESCE(v.nota,'')<>'' THEN ' — '||v.nota ELSE '' END detalle,v.valor,v.medio_pago medio,'' quien FROM ventas v LEFT JOIN clientes c ON c.id=v.cliente_id
      UNION ALL SELECT p.id,p.fecha,p.hora,'pagos','Pago',COALESCE(pr.nombre,'')||' '||p.nota,p.valor,p.medio_pago,COALESCE(p.quien,'') FROM pagos p LEFT JOIN proveedores pr ON pr.id=p.proveedor_id
      UNION ALL SELECT m.id,m.fecha,m.hora,'credito_mov',CASE m.tipo WHEN 'abono' THEN 'Abono' ELSE 'Saldo inicial' END,c.nombre||CASE WHEN COALESCE(m.nota,'')<>'' THEN ' — '||m.nota ELSE '' END,m.valor,m.medio_pago,'' FROM credito_mov m JOIN clientes c ON c.id=m.cliente_id
      ) WHERE fecha BETWEEN ?1 AND ?2 AND (?3='' OR (t='pagos' AND UPPER(TRIM(quien))=UPPER(?3))) ORDER BY fecha DESC,COALESCE(hora,'') DESC,id DESC LIMIT 1000''', (d, h, quien)))

@app.route('/api/quienes')
def quienes(): return jsonify(sorted({r['quien'].strip().title() for r in q("SELECT DISTINCT quien FROM pagos WHERE TRIM(COALESCE(quien,''))<>''")}))

# ---------- estadísticas ----------
@app.route('/api/estadisticas')
def estadisticas():
    r, f = request.args.get('rango', 'dia'), request.args.get('fecha') or hoy()
    d, h, n = {'dia': (f, f, 0), 'mes': (f[:7] + '-01', f[:7] + '-31', 10), 'anio': (f[:4] + '-01-01', f[:4] + '-12-31', 7)}.get(r, ('0000', '9999', 4))
    p = (d, h)
    one = lambda s: (q(s, p)[0]['t'] or 0)
    out = dict(
        ventas=q('SELECT medio_pago m,SUM(valor) t FROM ventas WHERE fecha BETWEEN ? AND ? GROUP BY 1', p),
        abonos=q("SELECT medio_pago m,SUM(valor) t FROM credito_mov WHERE tipo='abono' AND fecha BETWEEN ? AND ? GROUP BY 1", p),
        pagos=q('''SELECT p.categoria c,COALESCE(pr.nombre,'?') n,SUM(p.valor) t FROM pagos p LEFT JOIN proveedores pr ON pr.id=p.proveedor_id
                   WHERE fecha BETWEEN ? AND ? GROUP BY 1,2 ORDER BY t DESC''', p),
        quien=q('''SELECT COALESCE(NULLIF(UPPER(TRIM(quien)),''),'(SIN DATO)') n,COUNT(*) c,SUM(valor) t FROM pagos WHERE fecha BETWEEN ? AND ? GROUP BY 1 ORDER BY t DESC''', p),
        equipos=one('SELECT SUM(valor) t FROM equipos WHERE fecha_compra BETWEEN ? AND ?'),
        mants=one('SELECT SUM(costo) t FROM mantenimientos WHERE fecha BETWEEN ? AND ?'),
        deuda=q(f'SELECT COALESCE(SUM(CASE WHEN x>0 THEN x ELSE 0 END),0) t FROM (SELECT {DEUDA} x FROM clientes c)')[0]['t'])
    if n:
        out['detalle'] = q(f'''SELECT k,SUM(v) vendido,SUM(c) costos FROM (
          SELECT substr(fecha,1,{n}) k,valor v,0 c FROM ventas WHERE fecha BETWEEN ?1 AND ?2
          UNION ALL SELECT substr(fecha,1,{n}),0,valor FROM pagos WHERE fecha BETWEEN ?1 AND ?2
          UNION ALL SELECT substr(fecha_compra,1,{n}),0,valor FROM equipos WHERE fecha_compra BETWEEN ?1 AND ?2
          UNION ALL SELECT substr(fecha,1,{n}),0,costo FROM mantenimientos WHERE fecha BETWEEN ?1 AND ?2
        ) GROUP BY k ORDER BY k''', p)
    return jsonify(out)

# ---------- Excel y configuración ----------
@app.route('/api/exportar')
def exportar():
    from openpyxl import Workbook
    wb = Workbook(); wb.remove(wb.active)
    hojas = {'Ventas': "SELECT v.fecha,v.hora,v.valor,v.valor_entregado entregado,v.medio_pago medio,c.nombre cliente,v.nota FROM ventas v LEFT JOIN clientes c ON c.id=v.cliente_id ORDER BY v.fecha,v.id",
             'Pagos': "SELECT p.fecha,p.hora,pr.nombre pagado_a,p.valor,p.medio_pago medio,p.nota,p.quien FROM pagos p LEFT JOIN proveedores pr ON pr.id=p.proveedor_id ORDER BY p.fecha,p.id",
             'Creditos': f"SELECT c.nombre cliente,c.telefono,{DEUDA} deuda FROM clientes c WHERE c.nombre<>'MOSTRADOR' ORDER BY c.nombre",
             'Abonos': "SELECT m.fecha,m.hora,c.nombre cliente,m.tipo,m.valor,m.medio_pago medio,m.nota FROM credito_mov m JOIN clientes c ON c.id=m.cliente_id ORDER BY m.fecha",
             'Equipos': "SELECT nombre,fecha_compra,valor,nota FROM equipos ORDER BY fecha_compra",
             'Mantenimientos': "SELECT e.nombre equipo,m.fecha,m.descripcion,m.costo FROM mantenimientos m JOIN equipos e ON e.id=m.equipo_id ORDER BY m.fecha"}
    for nom, sql in hojas.items():
        ws = wb.create_sheet(nom); rows = q(sql)
        ws.append(list(rows[0].keys()) if rows else ['(sin datos)'])
        for r in rows: ws.append(list(r.values()))
    b = io.BytesIO(); wb.save(b); b.seek(0)
    return send_file(b, as_attachment=True, download_name=f'LaPampa-{hoy()}.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/api/config', methods=['GET', 'POST'])
def config():
    if request.method == 'POST':
        json.dump({'carpeta_nube': (request.json.get('carpeta_nube') or '').strip()}, open(CFG, 'w', encoding='utf-8'))
        return jsonify(ok=1, hechos=respaldar())
    return jsonify(cfg=cfg(), respaldos=sorted(os.path.basename(x) for x in glob.glob(os.path.join(RESP, '*.db')))[-5:])

@app.route('/api/respaldar', methods=['POST'])
def respaldo_ahora(): return jsonify(hechos=respaldar())

# ---------- arranque (doble clic) ----------
def puerto_libre(p=PORT):
    s = socket.socket()
    try: s.bind(('127.0.0.1', p)); return True
    except OSError: return False
    finally: s.close()

def main():
    url = f'http://127.0.0.1:{PORT}'
    if not puerto_libre():
        webbrowser.open(url); time.sleep(3); return
    threading.Thread(target=lambda: app.run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False, threaded=True), daemon=True).start()
    threading.Thread(target=bucle_respaldo, daemon=True).start()
    webbrowser.open(url)
    try:
        if sys.platform == 'darwin': raise RuntimeError('En Mac se usa la Terminal')
        import tkinter as tk
        w = tk.Tk(); w.title('La Pampa'); w.geometry('520x260'); w.configure(bg='#faf7f2')
        tk.Label(w, text='La Pampa está funcionando', font=('Georgia', 22, 'italic'), bg='#faf7f2', fg='#4b2e1e').pack(pady=(18, 4))
        tk.Label(w, text='Cierra esta ventana para apagarla\n(se hace una copia de seguridad).', bg='#faf7f2', fg='#6b5a4f', font=('Segoe UI', 13)).pack()
        tk.Button(w, text='Abrir La Pampa', command=lambda: webbrowser.open(url), bg='#7a4e33', fg='white', relief='flat', padx=20, pady=8, font=('Segoe UI', 14, 'bold')).pack(pady=10)
        def cerrar(): respaldar(); w.destroy()
        w.protocol('WM_DELETE_WINDOW', cerrar); w.mainloop()
    except Exception:
        print('La Pampa está funcionando en', url, '- para apagarla cierra esta ventana o pulsa Ctrl+C')
        try:
            while True: time.sleep(3600)
        except KeyboardInterrupt: respaldar()

if __name__ == '__main__': main()
