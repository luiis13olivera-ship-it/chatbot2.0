from flask import Blueprint, request, jsonify, g, session, redirect, url_for, render_template_string
import sqlite3
import os
from datetime import datetime
import threading
import requests # Necesario para la comunicación interna

# 1. DEFINICIÓN DEL BLUEPRINT (Reemplaza a 'app = Flask')
admin_bp = Blueprint('admin_bp', __name__)

# Configuración de la base de datos
DATABASE = 'autopartes.db'

# Credenciales de administradores
ADMIN_USERS = {
    "Pedro_48": "PZ22",
    "Abad_48": "AR56", 
    "Sergio_48": "SE63",
    "Olivera_48": "LO69"
}

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Funciones de base de datos (Sin cambios en lógica, solo indentación)
def obtener_inventario_bajo(limite=5):
    try:
        db = get_db()
        productos = db.execute('''
            SELECT * FROM productos 
            WHERE stock <= ? AND activo = 1
            ORDER BY stock ASC
        ''', (limite,)).fetchall()
        return [dict(producto) for producto in productos]
    except: return []

def enviar_respuesta_chatbot_async(payload):
    """Envía la respuesta al chatbot (simulado para Render)"""
    def enviar():
        # NOTA: En Render, la comunicación interna por HTTP a localhost puede fallar 
        # si solo hay un worker. Lo ideal es integrar la lógica, pero esto es un intento seguro.
        try:
            print(f"🔧 DEBUG: Intentando enviar respuesta interna...")
            # Aquí iría la lógica de socket o request interno
            pass 
        except Exception as e:
            print(f"❌ DEBUG ASYNC: Error en envío: {e}")
    
    thread = threading.Thread(target=enviar)
    thread.daemon = True
    thread.start()

# Decorador de Autenticación (Adaptado para Blueprint)
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            # CORRECCIÓN IMPORTANTE: Redirección usando el nombre del blueprint
            return redirect(url_for('admin_bp.admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- RUTAS DEL SISTEMA (Endpoints convertidos a @admin_bp) ---

@admin_bp.route('/')
def index():
    return redirect(url_for('admin_bp.admin_login'))

@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username in ADMIN_USERS and ADMIN_USERS[username] == password:
            session['admin_logged_in'] = True
            session['username'] = username
            return redirect(url_for('admin_bp.seleccionar_perfil'))
        else:
            # HTML de Error (Simplificado para el ejemplo, pero funcional)
            return render_template_string(LOGIN_HTML, error="Usuario o contraseña incorrectos")
    
    return render_template_string(LOGIN_HTML)

@admin_bp.route('/seleccionar_perfil', methods=['GET', 'POST'])
@login_required
def seleccionar_perfil():
    if request.method == 'POST':
        perfil = request.form.get('perfil')
        if perfil in ['admin_db', 'soporte']:
            session['perfil_activo'] = perfil
            if perfil == 'admin_db':
                return redirect(url_for('admin_bp.admin_dashboard'))
            else:
                return redirect(url_for('admin_bp.soporte_dashboard'))
    
    # HTML Renderizado con url_for corregidos
    return render_template_string(PERFIL_HTML, username=session.get('username', 'Usuario'))

@admin_bp.route('/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('username', None)
    session.pop('perfil_activo', None)
    return redirect(url_for('admin_bp.admin_login'))

# Dashboard para Admin DB
@app.route('/dashboard') # ¡OJO! En tu código original esto estaba suelto.
@admin_bp.route('/dashboard') # Lo cambiamos a admin_bp
@login_required
def admin_dashboard():
    db = get_db()
    # Estadísticas
    try:
        total_productos = db.execute('SELECT COUNT(*) as count FROM productos').fetchone()['count']
        total_ventas = db.execute('SELECT COUNT(*) as count FROM compras').fetchone()['count']
        total_usuarios = db.execute('SELECT COUNT(*) as count FROM usuarios').fetchone()['count']
        ventas_hoy = db.execute("SELECT COUNT(*) as count FROM compras WHERE DATE(fecha_compra) = DATE('now')").fetchone()['count']
        inventario_bajo = obtener_inventario_bajo()
        ventas_recientes = db.execute('SELECT c.*, u.nombre as cliente FROM compras c JOIN usuarios u ON c.usuario_id = u.id ORDER BY c.fecha_compra DESC LIMIT 5').fetchall()
    except:
        total_productos = total_ventas = total_usuarios = ventas_hoy = 0
        inventario_bajo = []
        ventas_recientes = []

    return render_template_string(DASHBOARD_DB_HTML, 
                                tp=total_productos, tv=total_ventas, tu=total_usuarios, vh=ventas_hoy,
                                inv=inventario_bajo, vr=ventas_recientes, user=session.get('username'))

# Dashboard para Soporte
@admin_bp.route('/soporte_dashboard')
@login_required
def soporte_dashboard():
    db = get_db()
    try:
        pp = db.execute("SELECT COUNT(*) as count FROM preguntas_soporte WHERE estado = 'pendiente'").fetchone()['count']
        pr = db.execute("SELECT COUNT(*) as count FROM preguntas_soporte WHERE estado = 'respondida'").fetchone()['count']
        pt = db.execute("SELECT COUNT(*) as count FROM preguntas_soporte").fetchone()['count']
        rec = db.execute("SELECT * FROM preguntas_soporte WHERE estado = 'pendiente' ORDER BY fecha_pregunta DESC LIMIT 5").fetchall()
    except:
        pp = pr = pt = 0
        rec = []
    
    return render_template_string(DASHBOARD_SOPORTE_HTML, pp=pp, pr=pr, pt=pt, rec=rec, user=session.get('username'))

@admin_bp.route('/soporte_gestion')
@login_required
def soporte_gestion():
    db = get_db()
    try:
        pendientes = db.execute("SELECT * FROM preguntas_soporte WHERE estado = 'pendiente' ORDER BY fecha_pregunta DESC").fetchall()
        respondidas = db.execute("SELECT * FROM preguntas_soporte WHERE estado = 'respondida' ORDER BY fecha_respuesta DESC LIMIT 10").fetchall()
    except:
        pendientes = []
        respondidas = []
        
    return render_template_string(GESTION_SOPORTE_HTML, pen=pendientes, res=respondidas)

@admin_bp.route('/responder_pregunta', methods=['POST'])
@login_required
def responder_pregunta():
    pregunta_id = request.form.get('pregunta_id')
    respuesta = request.form.get('respuesta')
    usuario_soporte = session.get('username')
    
    if pregunta_id and respuesta:
        db = get_db()
        db.execute('''
            UPDATE preguntas_soporte 
            SET respuesta = ?, estado = 'respondida', fecha_respuesta = CURRENT_TIMESTAMP, usuario_soporte = ?
            WHERE id = ?
        ''', (respuesta, usuario_soporte, pregunta_id))
        db.commit()
        
    return redirect(url_for('admin_bp.soporte_gestion'))

@admin_bp.route('/inventario')
@login_required
def admin_inventario():
    db = get_db()
    productos = db.execute('SELECT * FROM productos ORDER BY categoria, nombre').fetchall()
    
    # Generar HTML de filas
    rows = ""
    for p in productos:
        stock_class = "stock-bajo" if p['stock'] <= 5 else ""
        rows += f"<tr><td>{p['codigo']}</td><td>{p['nombre']}</td><td>{p['marca']}</td><td>{p['categoria']}</td><td class='{stock_class}'>{p['stock']}</td><td>S/ {p['precio']:.2f}</td><td>{p['numero_serie']}</td></tr>"
        
    return render_template_string(INVENTARIO_HTML, rows=rows)

@admin_bp.route('/ventas')
@login_required
def admin_ventas():
    db = get_db()
    ventas = db.execute('SELECT c.*, u.nombre as cliente_nombre FROM compras c JOIN usuarios u ON c.usuario_id = u.id ORDER BY c.fecha_compra DESC').fetchall()
    
    rows = ""
    for v in ventas:
        rows += f"<tr><td>#{v['id']}</td><td>{v['cliente_nombre']}</td><td>S/ {v['monto_total']:.2f}</td><td>{v['estado']}</td><td>{v['metodo_pago']}</td><td>{v['fecha_compra']}</td></tr>"
        
    return render_template_string(VENTAS_HTML, rows=rows)

@admin_bp.route('/actualizar_estado_venta', methods=['POST'])
@login_required
def actualizar_estado_venta():
    try:
        data = request.get_json()
        venta_id = data.get('venta_id')
        nuevo_estado = data.get('nuevo_estado')
        
        if venta_id and nuevo_estado:
            db = get_db()
            db.execute('UPDATE compras SET estado = ? WHERE id = ?', (nuevo_estado, venta_id))
            db.commit()
            return jsonify({'estado': 'success', 'mensaje': 'Actualizado'})
        return jsonify({'estado': 'error', 'mensaje': 'Datos incompletos'}), 400
    except Exception as e:
        return jsonify({'estado': 'error', 'mensaje': str(e)}), 500

# API para el chatbot (pública, sin login requerido para que el bot pueda escribir)
@admin_bp.route('/api/pregunta_no_comprendida', methods=['POST'])
def recibir_pregunta_no_comprendida():
    try:
        data = request.get_json()
        pregunta = data.get('pregunta', '')
        categoria = data.get('categoria', 'Consulta General')
        
        if pregunta:
            db = get_db()
            db.execute("INSERT INTO preguntas_soporte (pregunta, estado, categoria) VALUES (?, 'pendiente', ?)", (pregunta, categoria))
            db.commit()
            return jsonify({'estado': 'success'})
        return jsonify({'estado': 'error'}), 400
    except:
        return jsonify({'estado': 'error'}), 500

# --- PLANTILLAS HTML (Minificadas para ahorrar espacio en el archivo, se expanden al renderizar) ---

# Variable CSS común para reutilizar
CSS_COMMON = """
:root {--primary:#2563eb;--bg:#0f172a;--glass:rgba(15,23,42,0.8);--text:#f1f5f9;--border:#334155;}
body{background:linear-gradient(135deg,#0f172a,#1e293b);color:var(--text);font-family:sans-serif;margin:0;padding:20px;min-height:100vh}
.container{max-width:1200px;margin:0 auto;background:var(--glass);padding:30px;border-radius:20px;border:1px solid var(--border)}
.btn{background:var(--primary);color:white;padding:10px 20px;border-radius:8px;text-decoration:none;display:inline-block;border:none;cursor:pointer}
table{width:100%;border-collapse:collapse;margin-top:20px} th,td{padding:12px;border-bottom:1px solid var(--border);text-align:left}
input,select,textarea{background:#1e293b;border:1px solid var(--border);color:white;padding:10px;border-radius:5px;width:100%}
.card{background:rgba(30,41,59,0.6);padding:20px;border-radius:15px;margin-bottom:20px}
.header{display:flex;justify-content:space-between;align-items:center;margin-bottom:30px;border-bottom:1px solid var(--border);padding-bottom:20px}
"""

LOGIN_HTML = f"""<!DOCTYPE html><html><head><style>{CSS_COMMON} body{{display:flex;justify-content:center;align-items:center}}</style></head>
<body><div class="container" style="max-width:400px"><h2>🔐 Acceso Admin</h2>
<form method="POST"><input name="username" placeholder="Usuario" style="margin-bottom:10px" required>
<input type="password" name="password" placeholder="Password" style="margin-bottom:10px" required>
<button class="btn" style="width:100%">Entrar</button></form>
{{% if error %}}<p style="color:red">{{{{ error }}}}</p>{{% endif %}}
<br><a href="/" style="color:#aaa">← Volver al Chat</a></div></body></html>"""

PERFIL_HTML = f"""<!DOCTYPE html><html><head><style>{CSS_COMMON}</style></head>
<body><div class="container" style="text-align:center;max-width:800px"><h1>Hola, {{{{ username }}}}</h1><h2>Selecciona tu Perfil</h2>
<form method="POST" style="display:flex;gap:20px;justify-content:center;margin-top:40px">
<button name="perfil" value="admin_db" class="card" style="border:none;cursor:pointer;color:white;flex:1"><h1>📊</h1><h3>Base de Datos</h3></button>
<button name="perfil" value="soporte" class="card" style="border:none;cursor:pointer;color:white;flex:1"><h1>💬</h1><h3>Soporte</h3></button>
</form><br><a href="{{{{ url_for('admin_bp.admin_logout') }}}}" style="color:#aaa">Cerrar Sesión</a></div></body></html>"""

DASHBOARD_DB_HTML = f"""<!DOCTYPE html><html><head><style>{CSS_COMMON}</style></head>
<body><div class="container"><div class="header"><div><h1>📊 Dashboard BD</h1></div>
<div><a href="{{{{ url_for('admin_bp.seleccionar_perfil') }}}}" class="btn">🔄 Perfil</a> <a href="{{{{ url_for('admin_bp.admin_logout') }}}}" class="btn" style="background:red">Salir</a></div></div>
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:20px">
<div class="card"><h3>Productos</h3><h1>{{{{ tp }}}}</h1></div><div class="card"><h3>Ventas</h3><h1>{{{{ tv }}}}</h1></div>
<div class="card"><h3>Usuarios</h3><h1>{{{{ tu }}}}</h1></div><div class="card"><h3>Hoy</h3><h1>{{{{ vh }}}}</h1></div></div>
<br><a href="{{{{ url_for('admin_bp.admin_inventario') }}}}" class="btn">📦 Ver Inventario</a> <a href="{{{{ url_for('admin_bp.admin_ventas') }}}}" class="btn">🛒 Ver Ventas</a>
<h3>⚠️ Stock Bajo</h3><table>{{% for p in inv %}}<tr><td>{{{{ p.nombre }}}}</td><td style="color:red">{{{{ p.stock }}}}</td></tr>{{% endfor %}}</table>
</div></body></html>"""

DASHBOARD_SOPORTE_HTML = f"""<!DOCTYPE html><html><head><style>{CSS_COMMON}</style></head>
<body><div class="container"><div class="header"><div><h1>💬 Soporte</h1></div>
<div><a href="{{{{ url_for('admin_bp.seleccionar_perfil') }}}}" class="btn">🔄 Perfil</a> <a href="{{{{ url_for('admin_bp.admin_logout') }}}}" class="btn" style="background:red">Salir</a></div></div>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:20px">
<div class="card"><h3>Pendientes</h3><h1>{{{{ pp }}}}</h1></div><div class="card"><h3>Respondidas</h3><h1>{{{{ pr }}}}</h1></div><div class="card"><h3>Total</h3><h1>{{{{ pt }}}}</h1></div></div>
<br><a href="{{{{ url_for('admin_bp.soporte_gestion') }}}}" class="btn">📝 Gestionar Preguntas</a>
<h3>Recientes</h3><table>{{% for p in rec %}}<tr><td>{{{{ p.categoria }}}}</td><td>{{{{ p.pregunta }}}}</td></tr>{{% endfor %}}</table>
</div></body></html>"""

GESTION_SOPORTE_HTML = f"""<!DOCTYPE html><html><head><style>{CSS_COMMON}</style></head>
<body><div class="container"><div class="header"><h1>📝 Gestión de Preguntas</h1><a href="{{{{ url_for('admin_bp.soporte_dashboard') }}}}" class="btn">Volver</a></div>
<h2>Pendientes</h2>
{{% for p in pen %}}<div class="card">
<p><strong>{{{{ p.categoria }}}}:</strong> {{{{ p.pregunta }}}}</p>
<form method="POST" action="{{{{ url_for('admin_bp.responder_pregunta') }}}}">
<input type="hidden" name="pregunta_id" value="{{{{ p.id }}}}"><textarea name="respuesta" placeholder="Respuesta..." required></textarea>
<button class="btn" style="margin-top:10px">Enviar</button></form></div>{{% endfor %}}
<h2>Historial</h2>
{{% for r in res %}}<div class="card" style="opacity:0.7"><p>Q: {{{{ r.pregunta }}}}</p><p style="color:#10B981">A: {{{{ r.respuesta }}}}</p></div>{{% endfor %}}
</div></body></html>"""

INVENTARIO_HTML = f"""<!DOCTYPE html><html><head><style>{CSS_COMMON}</style></head>
<body><div class="container"><div class="header"><h1>📦 Inventario</h1><a href="{{{{ url_for('admin_bp.admin_dashboard') }}}}" class="btn">Volver</a></div>
<table><thead><tr><th>Cod</th><th>Nombre</th><th>Marca</th><th>Cat</th><th>Stock</th><th>Precio</th><th>Serie</th></tr></thead>
<tbody>{{{{ rows | safe }}}}</tbody></table></div></body></html>"""

VENTAS_HTML = f"""<!DOCTYPE html><html><head><style>{CSS_COMMON}</style></head>
<body><div class="container"><div class="header"><h1>🛒 Ventas</h1><a href="{{{{ url_for('admin_bp.admin_dashboard') }}}}" class="btn">Volver</a></div>
<table><thead><tr><th>ID</th><th>Cliente</th><th>Monto</th><th>Estado</th><th>Pago</th><th>Fecha</th></tr></thead>
<tbody>{{{{ rows | safe }}}}</tbody></table></div></body></html>"""
