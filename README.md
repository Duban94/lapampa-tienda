# La Pampa — control de ventas, pagos y créditos para una tienda

Programa de escritorio (corre en el navegador, sin internet) para una tienda pequeña: ventas por medio de pago,
pagos a proveedores, créditos de clientes con abonos y saldo a favor, equipos y mantenimientos, estadísticas,
historial, importación/exportación a Excel y copias de seguridad. Interfaz con letra grande pensada para
personas con baja visión (botones **A− / A+**).

> **Hecho con IA.** Este proyecto fue construido por Duban Ocampo conversando con [Claude Code](https://claude.com/claude-code)
> (Anthropic) para un negocio real. Se publica como punto de partida: haz un *fork* y adáptalo a tu negocio.

## Qué incluye
- **Ventas:** efectivo (con cálculo de devuelta), Nequi, Bancolombia y crédito (con nota de lo que se llevó). Guarda la hora para analizar horas pico.
- **Pagos y compras:** "Pagado a", quién pagó, administración de nombres de gastos (agregar, renombrar, unir).
- **Créditos:** buscador de clientes por cualquier parte del nombre, abonos y saldo a favor.
- **Equipos y mantenimientos**, **Estadísticas** (día/mes/año/total, por medio de pago, por quién pagó) e **Historial** con filtros.
- Editar o anular cualquier registro; no deja registrar fechas futuras.
- **Respaldos** automáticos cada 30 min, copia a una carpeta en la nube (Drive/OneDrive), cargar una copia, importar días desde Excel.
- **Instalador para Windows** con acceso directo en el Escritorio.

## Probarlo (Mac / Windows / Linux)
Necesitas Python 3.10+.
```bash
pip install -r requirements.txt
python crear_demo.py      # opcional: datos de ejemplo inventados
python app.py             # abre http://127.0.0.1:5055
```
Sin `crear_demo.py` arranca con la base vacía. Los datos viven en `lapampa.db` junto al programa (ignorado por git).

## Crear el instalador de Windows
En un PC con Windows e internet, doble clic en `CREAR_INSTALADOR.bat` (usa PyInstaller e Inno Setup).
Genera `Instalador\Instalar_LaPampa.exe`. Detalles y cómo actualizar sin perder datos: [`LEEME.txt`](LEEME.txt).

## Adaptarlo a tu negocio
- Medios de pago: `app.py` (`venta()`) y `templates/index.html` (botones `.mp`).
- Nombre y logo: `templates/index.html` (cabecera) e `icono.ico`.
- Todo el servidor está en `app.py` (Flask + SQLite) y toda la interfaz en `templates/index.html`.

## Privacidad
`.gitignore` excluye `*.db`, `Respaldos/` y `LaPampa.log`: **nunca subas la base de datos real de un negocio**.

## Licencia
[MIT](LICENSE) — úsalo, cámbialo y compártelo libremente.
