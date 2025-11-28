from flask import Blueprint, request, jsonify, g, session, redirect, url_for, render_template_string 
import sqlite3
import os
from datetime import datetime
import webbrowser
import threading
import time

admin_bp = Blueprint('admin_bp', __name__)

# Configuración de la base de datos - MISMA QUE EL PROYECTO PRINCIPAL
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'autopartes.db')

# Credenciales de administradores - MISMAS QUE EL PROYECTO PRINCIPAL
ADMIN_USERS = {
    "Pedro_48": "PZ22",
    "Abad_48": "AR56", 
    "Sergio_48": "SE63",
    "Olivera_48": "LO69"
}

def get_db():
    """Obtiene la conexión a la base de datos - MISMA CONEXIÓN QUE APP.PY"""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    """Cierra la conexión a la base de datos"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Inicializa la base de datos verificando la conexión"""
    try:
        db = get_db()
        # Verificar si la tabla productos existe
        db.execute('SELECT 1 FROM productos LIMIT 1')
        print("✅ Conectado a la base de datos existente")
        return True
    except sqlite3.OperationalError as e:
        print(f"❌ Error conectando a la base de datos: {e}")
        print("💡 Asegúrate de que el proyecto principal (app.py) se haya ejecutado al menos una vez")
        return False

# Funciones para gestionar productos
def obtener_productos(categoria=None, marca=None, modelo=None):
    """Obtiene productos con filtros opcionales"""
    try:
        db = get_db()
        query = 'SELECT * FROM productos WHERE activo = 1'
        params = []
        
        if categoria:
            query += ' AND categoria LIKE ?'
            params.append(f'%{categoria}%')
        
        if marca:
            query += ' AND marca LIKE ?'
            params.append(f'%{marca}%')
        
        if modelo:
            query += ' AND modelo LIKE ?'
            params.append(f'%{modelo}%')
        
        productos = db.execute(query, params).fetchall()
        return [dict(producto) for producto in productos]
    except Exception as e:
        print(f"Error obteniendo productos: {e}")
        return []

def obtener_producto_por_id(producto_id):
    """Obtiene un producto por su ID"""
    try:
        db = get_db()
        producto = db.execute('SELECT * FROM productos WHERE id = ?', (producto_id,)).fetchone()
        return dict(producto) if producto else None
    except Exception as e:
        print(f"Error obteniendo producto por ID: {e}")
        return None

def crear_producto(codigo, nombre, marca, modelo, precio, stock, descripcion, garantia, categoria, numero_serie):
    """Crea un nuevo producto"""
    try:
        db = get_db()
        db.execute('''
            INSERT INTO productos (codigo, nombre, marca, modelo, precio, stock, descripcion, garantia, categoria, numero_serie)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (codigo, nombre, marca, modelo, precio, stock, descripcion, garantia, categoria, numero_serie))
        db.commit()
        return True
    except sqlite3.IntegrityError as e:
        print(f"Error de integridad al crear producto: {e}")
        return False
    except Exception as e:
        print(f"Error creando producto: {e}")
        return False

def actualizar_producto(producto_id, codigo, nombre, marca, modelo, precio, stock, descripcion, garantia, categoria, numero_serie):
    """Actualiza un producto existente"""
    try:
        db = get_db()
        db.execute('''
            UPDATE productos 
            SET codigo=?, nombre=?, marca=?, modelo=?, precio=?, stock=?, descripcion=?, garantia=?, categoria=?, numero_serie=?
            WHERE id=?
        ''', (codigo, nombre, marca, modelo, precio, stock, descripcion, garantia, categoria, numero_serie, producto_id))
        db.commit()
        return True
    except Exception as e:
        print(f"Error actualizando producto: {e}")
        return False

def eliminar_producto(producto_id):
    """Elimina un producto (borrado lógico)"""
    try:
        db = get_db()
        db.execute('UPDATE productos SET activo = 0 WHERE id = ?', (producto_id,))
        db.commit()
        return True
    except Exception as e:
        print(f"Error eliminando producto: {e}")
        return False

# Funciones para reportes y consultas
def obtener_ventas_por_periodo(fecha_inicio=None, fecha_fin=None):
    """Obtiene ventas por periodo"""
    try:
        db = get_db()
        if fecha_inicio and fecha_fin:
            ventas = db.execute('''
                SELECT c.*, u.nombre as cliente
                FROM compras c
                JOIN usuarios u ON c.usuario_id = u.id
                WHERE c.fecha_compra BETWEEN ? AND ?
                ORDER BY c.fecha_compra DESC
            ''', (fecha_inicio, fecha_fin)).fetchall()
        else:
            ventas = db.execute('''
                SELECT c.*, u.nombre as cliente
                FROM compras c
                JOIN usuarios u ON c.usuario_id = u.id
                ORDER BY c.fecha_compra DESC
            ''').fetchall()
        
        return [dict(venta) for venta in ventas]
    except Exception as e:
        print(f"Error obteniendo ventas: {e}")
        return []

def obtener_inventario_bajo(limite=5):
    """Obtiene productos con stock bajo"""
    try:
        db = get_db()
        productos = db.execute('''
            SELECT * FROM productos 
            WHERE stock <= ? AND activo = 1
            ORDER BY stock ASC
        ''', (limite,)).fetchall()
        
        return [dict(producto) for producto in productos]
    except Exception as e:
        print(f"Error obteniendo inventario bajo: {e}")
        return []

def obtener_estadisticas():
    """Obtiene estadísticas generales del sistema"""
    try:
        db = get_db()
        
        total_productos = db.execute('SELECT COUNT(*) as count FROM productos WHERE activo = 1').fetchone()['count']
        total_ventas = db.execute('SELECT COUNT(*) as count FROM compras').fetchone()['count']
        total_usuarios = db.execute('SELECT COUNT(*) as count FROM usuarios').fetchone()['count']
        
        ventas_hoy = db.execute('''
            SELECT COUNT(*) as count FROM compras 
            WHERE DATE(fecha_compra) = DATE('now')
        ''').fetchone()['count']
        
        ventas_mes = db.execute('''
            SELECT COUNT(*) as count FROM compras 
            WHERE strftime('%Y-%m', fecha_compra) = strftime('%Y-%m', 'now')
        ''').fetchone()['count']
        
        total_ingresos_result = db.execute('''
            SELECT COALESCE(SUM(monto_total), 0) as total FROM compras 
            WHERE estado = 'completado'
        ''').fetchone()
        total_ingresos = total_ingresos_result['total'] if total_ingresos_result else 0
        
        return {
            'total_productos': total_productos,
            'total_ventas': total_ventas,
            'total_usuarios': total_usuarios,
            'ventas_hoy': ventas_hoy,
            'ventas_mes': ventas_mes,
            'total_ingresos': float(total_ingresos) if total_ingresos else 0
        }
    except Exception as e:
        print(f"Error obteniendo estadísticas: {e}")
        return {
            'total_productos': 0,
            'total_ventas': 0,
            'total_usuarios': 0,
            'ventas_hoy': 0,
            'ventas_mes': 0,
            'total_ingresos': 0
        }

# Sistema de autenticación
def login_required(f):
    """Decorator para requerir autenticación"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Templates HTML CORREGIDOS
LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Acceso Administrativo - Autopartes Verese Sac</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #10a37f;
            --primary-dark: #0d8c6c;
            --sidebar: #1a1b26;
            --text-primary: #e0e6f0;
            --text-secondary: #a0a6b8;
            --border: #2a2b3c;
            --gradient-1: #10a37f;
            --gradient-2: #1e40af;
            --success: #10B981;
            --danger: #EF4444;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
        }
        
        body {
            background: linear-gradient(135deg, var(--gradient-1) 0%, var(--gradient-2) 100%);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .login-container {
            background: var(--sidebar);
            padding: 40px;
            border-radius: 16px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.3), 0 0 0 1px var(--border);
            width: 100%;
            max-width: 440px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        .login-header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .logo-container {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .logo-icon {
            width: 60px;
            height: 60px;
            background: linear-gradient(135deg, var(--gradient-1), var(--gradient-2));
            border-radius: 15px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.8rem;
            font-weight: bold;
            color: white;
            box-shadow: 0 6px 25px rgba(16, 163, 127, 0.5), 0 0 0 3px rgba(25, 195, 125, 0.4), inset 0 2px 15px rgba(255, 255, 255, 0.3);
        }
        
        .logo-text {
            display: flex;
            flex-direction: column;
            text-align: left;
        }
        
        .logo-main {
            font-size: 1.4rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--text-primary), var(--gradient-1));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .logo-sub {
            font-size: 0.9rem;
            font-weight: 500;
            color: var(--text-secondary);
        }
        
        .login-title {
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 8px;
            color: var(--text-primary);
        }
        
        .login-subtitle {
            color: var(--text-secondary);
            font-size: 0.95rem;
        }
        
        .form-group {
            margin-bottom: 24px;
        }
        
        .form-label {
            display: block;
            margin-bottom: 8px;
            color: var(--text-primary);
            font-weight: 500;
            font-size: 0.9rem;
        }
        
        .form-input {
            width: 100%;
            padding: 14px 16px;
            background: #161722;
            border: 1px solid var(--border);
            border-radius: 10px;
            color: var(--text-primary);
            font-size: 0.95rem;
            transition: all 0.3s ease;
        }
        
        .form-input:focus {
            outline: none;
            border-color: var(--gradient-1);
            box-shadow: 0 0 0 3px rgba(16, 163, 127, 0.1);
        }
        
        .btn {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, var(--gradient-1), var(--gradient-2));
            border: none;
            border-radius: 10px;
            color: white;
            cursor: pointer;
            transition: all 0.3s ease;
            font-weight: 600;
            font-size: 1rem;
            box-shadow: 0 4px 15px rgba(16, 163, 127, 0.3);
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(16, 163, 127, 0.4);
        }
        
        .error-message {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 8px;
            padding: 12px 16px;
            margin-top: 20px;
            color: var(--danger);
            font-size: 0.9rem;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .admin-hint {
            background: rgba(16, 163, 127, 0.1);
            border: 1px solid rgba(16, 163, 127, 0.3);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
            font-size: 0.85rem;
            color: var(--text-secondary);
        }
        
        .hint-title {
            font-weight: 600;
            color: var(--success);
            margin-bottom: 5px;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-header">
            <div class="logo-container">
                <div class="logo-icon">V</div>
                <div class="logo-text">
                    <div class="logo-main">Autopartes</div>
                    <div class="logo-sub">Verese Sac</div>
                </div>
            </div>
            <h1 class="login-title">🔐 Acceso Administrativo</h1>
            <p class="login-subtitle">Sistema de gestión de base de datos</p>
        </div>
        
        <div class="admin-hint">
            <div class="hint-title">👥 Usuarios Autorizados:</div>
            <div>Pedro_48, Abad_48, Sergio_48, Olivera_48</div>
        </div>
        
        <form method="POST">
            <div class="form-group">
                <label class="form-label">Usuario:</label>
                <input type="text" name="username" class="form-input" placeholder="Ingresa tu usuario" required>
            </div>
            <div class="form-group">
                <label class="form-label">Contraseña:</label>
                <input type="password" name="password" class="form-input" placeholder="Ingresa tu contraseña" required>
            </div>
            <button type="submit" class="btn">Ingresar al Sistema</button>
        </form>
        
        {% if error %}
        <div class="error-message">
            ❌ {{ error }}
        </div>
        {% endif %}
        
        <div style="text-align: center; margin-top: 20px; padding-top: 20px; border-top: 1px solid var(--border);">
            <a href="http://127.0.0.1:5000" style="color: var(--text-secondary); text-decoration: none; font-size: 0.9rem;">
                ← Volver al Chat Principal
            </a>
        </div>
    </div>
</body>
</html>
'''

BASE_TEMPLATE = '''
<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><title>{{ title }}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
:root{--primary:#10a37f;--bg:#1a1b26;--card:#1e1f2e;--text:#e0e6f0;}
body{background:linear-gradient(135deg,#10a37f,#1e40af);font-family:'Inter',sans-serif;margin:0;min-height:100vh;padding:20px;color:var(--text)}
.container{max-width:1200px;margin:0 auto;background:var(--bg);border-radius:16px;overflow:hidden;box-shadow:0 20px 40px rgba(0,0,0,0.3)}
.header{background:rgba(16,163,127,0.1);padding:20px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #2a2b3c}
.btn{background:var(--primary);color:white;padding:8px 16px;border-radius:8px;text-decoration:none;font-size:0.9rem;display:inline-block}
.btn.sec{background:var(--card);border:1px solid #2a2b3c} .btn.danger{background:#EF4444}
table{width:100%;border-collapse:collapse;margin-top:20px} th,td{padding:15px;text-align:left;border-bottom:1px solid #2a2b3c}
th{background:rgba(0,0,0,0.2)} .card{background:var(--card);padding:20px;border-radius:12px;margin-bottom:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px}
.form-group{margin-bottom:15px} label{display:block;margin-bottom:5px} input,select,textarea{width:100%;padding:10px;background:#161722;border:1px solid #2a2b3c;color:white;border-radius:8px}
</style></head><body>
<div class="container">
<div class="header">
    <div><h1>{{ header_title }}</h1></div>
    <div style="display:flex;gap:10px">
        <a href="{{ url_for('admin_bp.admin_dashboard') }}" class="btn sec">📊 Dash</a>
        <a href="{{ url_for('admin_bp.admin_inventario') }}" class="btn sec">📦 Inv</a>
        <a href="{{ url_for('admin_bp.admin_ventas') }}" class="btn sec">🛒 Ventas</a>
        <a href="{{ url_for('admin_bp.admin_logout') }}" class="btn danger">🚪 Salir</a>
    </div>
</div>
<div style="padding:30px">{{ content | safe }}</div>
</div></body></html>
'''

# Ruta de login para administración
@admin_bp.route('/', methods=['GET', 'POST'])
@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in ADMIN_USERS and ADMIN_USERS[username] == password:
            session['admin_logged_in'] = True
            # CORRECCIÓN 4: Redirección con namespace correcto
            return redirect(url_for('admin_bp.admin_dashboard'))
        return render_template_string(LOGIN_TEMPLATE, error='Datos incorrectos')
    return render_template_string(LOGIN_TEMPLATE)

@admin_bp.route('/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_bp.admin_login'))

@admin_bp.route('/dashboard')
@login_required
def admin_dashboard():
    s = obtener_estadisticas()
    inv = obtener_inventario_bajo()
    
    html = f'''
    <div class="grid">
        <div class="card"><h3>📦 Productos</h3><h2>{s['total_productos']}</h2></div>
        <div class="card"><h3>🛒 Ventas</h3><h2>{s['total_ventas']}</h2></div>
        <div class="card"><h3>💰 Ingresos</h3><h2>S/ {s['total_ingresos']:.2f}</h2></div>
    </div>
    <div class="card">
        <h3>⚠️ Stock Bajo</h3>
        <table><thead><tr><th>Producto</th><th>Stock</th></tr></thead>
        <tbody>
        {"".join(f"<tr><td>{p['nombre']}</td><td style='color:#EF4444;font-weight:bold'>{p['stock']}</td></tr>" for p in inv) or "<tr><td colspan='2'>Todo ok</td></tr>"}
        </tbody></table>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title="Dashboard", header_title="Dashboard", content=html)

@admin_bp.route('/inventario')
@login_required
def admin_inventario():
    prods = obtener_productos()
    rows = ""
    for p in prods:
        rows += f'''<tr>
            <td>{p['codigo']}</td><td>{p['nombre']}</td><td>{p['stock']}</td><td>S/ {p['precio']}</td>
            <td>
                <a href="/admin/producto/editar/{p['id']}" class="btn sec">✏️</a>
                <a href="/admin/producto/eliminar/{p['id']}" class="btn danger" onclick="return confirm('¿Borrar?')">🗑️</a>
            </td>
        </tr>'''
    
    html = f'''
    <div style="margin-bottom:20px"><a href="/admin/producto/nuevo" class="btn">➕ Nuevo Producto</a></div>
    <table><thead><tr><th>Cod</th><th>Nombre</th><th>Stock</th><th>Precio</th><th>Acciones</th></tr></thead>
    <tbody>{rows}</tbody></table>
    '''
    return render_template_string(BASE_TEMPLATE, title="Inventario", header_title="Inventario", content=html)

@admin_bp.route('/ventas')
@login_required
def admin_ventas():
    ventas = obtener_ventas_por_periodo()
    rows = "".join(f"<tr><td>#{v['id']}</td><td>{v['cliente']}</td><td>S/ {v['monto_total']}</td><td>{v['estado']}</td></tr>" for v in ventas)
    html = f'<table><thead><tr><th>ID</th><th>Cliente</th><th>Monto</th><th>Estado</th></tr></thead><tbody>{rows}</tbody></table>'
    return render_template_string(BASE_TEMPLATE, title="Ventas", header_title="Historial Ventas", content=html)

@admin_bp.route('/producto/nuevo', methods=['GET', 'POST'])
@login_required
def admin_nuevo_producto():
    if request.method == 'POST':
        f = request.form
        if crear_producto(f['c'], f['n'], f['m'], f['mod'], float(f['p']), int(f['s']), f['d'], f['g'], f['cat'], f['ns']):
            # CORRECCIÓN 5: Redirección correcta
            return redirect(url_for('admin_bp.admin_inventario'))
    
    form = '''
    <form method="POST">
    <div class="grid">
        <div class="form-group"><label>Código</label><input name="c" required></div>
        <div class="form-group"><label>Nombre</label><input name="n" required></div>
        <div class="form-group"><label>Marca</label><input name="m" required></div>
        <div class="form-group"><label>Precio</label><input name="p" type="number" step="0.01" required></div>
        <div class="form-group"><label>Stock</label><input name="s" type="number" required></div>
        <div class="form-group"><label>Categoría</label><input name="cat" required></div>
        <div class="form-group"><label>Serie</label><input name="ns" required></div>
    </div>
    <div class="form-group"><label>Modelo</label><input name="mod"></div>
    <div class="form-group"><label>Descripción</label><textarea name="d"></textarea></div>
    <div class="form-group"><label>Garantía</label><input name="g"></div>
    <button type="submit" class="btn">Guardar</button>
    </form>
    '''
    return render_template_string(BASE_TEMPLATE, title="Nuevo", header_title="Nuevo Producto", content=form)

@admin_bp.route('/producto/editar/<int:producto_id>', methods=['GET', 'POST'])
@login_required
def admin_editar_producto(producto_id):
    p = obtener_producto_por_id(producto_id)
    if not p: return "No encontrado", 404
    
    if request.method == 'POST':
        f = request.form
        actualizar_producto(producto_id, f['c'], f['n'], f['m'], f['mod'], float(f['p']), int(f['s']), f['d'], f['g'], f['cat'], f['ns'])
        return redirect(url_for('admin_bp.admin_inventario'))

    form = f'''
    <form method="POST">
    <div class="grid">
        <div class="form-group"><label>Código</label><input name="c" value="{p['codigo']}"></div>
        <div class="form-group"><label>Nombre</label><input name="n" value="{p['nombre']}"></div>
        <div class="form-group"><label>Marca</label><input name="m" value="{p['marca']}"></div>
        <div class="form-group"><label>Precio</label><input name="p" value="{p['precio']}"></div>
        <div class="form-group"><label>Stock</label><input name="s" value="{p['stock']}"></div>
        <div class="form-group"><label>Categoría</label><input name="cat" value="{p['categoria']}"></div>
        <div class="form-group"><label>Serie</label><input name="ns" value="{p['numero_serie']}"></div>
    </div>
    <input name="mod" type="hidden" value="{p['modelo']}">
    <input name="d" type="hidden" value="{p['descripcion']}">
    <input name="g" type="hidden" value="{p['garantia']}">
    <button type="submit" class="btn">Actualizar</button>
    </form>
    '''
    return render_template_string(BASE_TEMPLATE, title="Editar", header_title="Editar Producto", content=form)

@admin_bp.route('/producto/eliminar/<int:producto_id>')
@login_required
def admin_eliminar_producto(producto_id):
    eliminar_producto_db(producto_id)
    return redirect(url_for('admin_bp.admin_inventario'))






