from flask import Blueprint, request, jsonify, g, session, redirect, url_for, render_template_string 
import sqlite3
import os
from datetime import datetime
import webbrowser
import threading
import time

admin_bp = Blueprint('admin_bp', __name__, url_prefix='/sistema-admin')

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
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #10a37f;
            --primary-dark: #0d8c6c;
            --sidebar: #1a1b26;
            --text-primary: #e0e6f0;
            --text-secondary: #a0a6b8;
            --border: #2a2b3c;
            --card-bg: #1e1f2e;
            --gradient-1: #10a37f;
            --gradient-2: #1e40af;
            --success: #10B981;
            --warning: #F59E0B;
            --danger: #EF4444;
            --info: #3B82F6;
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
        }
        
        .admin-container {
            max-width: 1400px;
            margin: 0 auto;
            background: var(--sidebar);
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 20px 40px rgba(0,0,0,0.3), 0 0 0 1px var(--border);
            margin: 20px;
        }
        
        .admin-header {
            background: linear-gradient(135deg, rgba(16, 163, 127, 0.1) 0%, rgba(30, 64, 175, 0.1) 100%);
            padding: 24px 30px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header-left {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .admin-logo {
            width: 50px;
            height: 50px;
            background: linear-gradient(135deg, var(--gradient-1), var(--gradient-2));
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.4rem;
            font-weight: bold;
            color: white;
            box-shadow: 0 4px 20px rgba(16, 163, 127, 0.5), 0 0 0 2px rgba(25, 195, 125, 0.4);
        }
        
        .admin-titles h1 {
            font-size: 1.6rem;
            margin-bottom: 4px;
            background: linear-gradient(135deg, var(--text-primary), var(--gradient-1));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 700;
        }
        
        .admin-titles p {
            color: var(--text-secondary);
            font-size: 0.95rem;
        }
        
        .header-actions {
            display: flex;
            gap: 12px;
        }
        
        .admin-btn {
            background: linear-gradient(135deg, var(--gradient-1), var(--gradient-2));
            color: white;
            border: none;
            border-radius: 10px;
            padding: 10px 18px;
            font-size: 0.9rem;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
            text-decoration: none;
            font-weight: 600;
            box-shadow: 0 4px 15px rgba(16, 163, 127, 0.3);
        }
        
        .admin-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(16, 163, 127, 0.4);
        }
        
        .admin-btn.secondary {
            background: var(--card-bg);
            color: var(--text-primary);
            border: 1px solid var(--border);
        }
        
        .admin-btn.secondary:hover {
            background: rgba(255,255,255,0.1);
        }
        
        .admin-btn.logout {
            background: var(--danger);
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            padding: 30px;
        }
        
        .stat-card {
            background: var(--card-bg);
            padding: 24px;
            border-radius: 12px;
            border: 1px solid var(--border);
            transition: all 0.3s ease;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            border-color: var(--gradient-1);
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        .stat-icon {
            width: 50px;
            height: 50px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            margin-bottom: 15px;
            background: linear-gradient(135deg, var(--gradient-1), var(--gradient-2));
        }
        
        .stat-number {
            font-size: 2.2rem;
            font-weight: 700;
            margin-bottom: 5px;
            background: linear-gradient(135deg, var(--text-primary), var(--gradient-1));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .stat-label {
            color: var(--text-secondary);
            font-size: 0.9rem;
            font-weight: 500;
        }
        
        .admin-section {
            background: var(--card-bg);
            margin: 20px 30px;
            padding: 25px;
            border-radius: 12px;
            border: 1px solid var(--border);
        }
        
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .section-header h2 {
            font-size: 1.3rem;
            color: var(--text-primary);
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            background: var(--sidebar);
            border-radius: 8px;
            overflow: hidden;
        }
        
        th {
            background: rgba(30, 64, 175, 0.2);
            padding: 15px 12px;
            text-align: left;
            font-weight: 600;
            font-size: 0.85rem;
            color: var(--text-primary);
            border-bottom: 2px solid var(--border);
        }
        
        td {
            padding: 15px 12px;
            border-bottom: 1px solid var(--border);
            color: var(--text-primary);
        }
        
        tr:hover {
            background: rgba(255, 255, 255, 0.03);
        }
        
        .stock-bajo {
            color: var(--danger);
            font-weight: 600;
        }
        
        .estado-pendiente { color: var(--warning); }
        .estado-proceso { color: var(--info); }
        .estado-completado { color: var(--success); }
        .estado-cancelado { color: var(--danger); }
        
        .navigation {
            display: flex;
            gap: 15px;
            margin: 20px 30px;
            flex-wrap: wrap;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-label {
            display: block;
            margin-bottom: 8px;
            color: var(--text-primary);
            font-weight: 500;
            font-size: 0.9rem;
        }
        
        .form-input, .form-select, .form-textarea {
            width: 100%;
            padding: 12px 16px;
            background: var(--sidebar);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text-primary);
            font-size: 0.95rem;
            transition: all 0.3s ease;
        }
        
        .form-input:focus, .form-select:focus, .form-textarea:focus {
            outline: none;
            border-color: var(--gradient-1);
            box-shadow: 0 0 0 3px rgba(16, 163, 127, 0.1);
        }
        
        .form-textarea {
            resize: vertical;
            min-height: 100px;
        }
        
        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
        
        .alert {
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            border: 1px solid;
        }
        
        .alert-success {
            background: rgba(16, 185, 129, 0.1);
            border-color: rgba(16, 185, 129, 0.3);
            color: var(--success);
        }
        
        .alert-error {
            background: rgba(239, 68, 68, 0.1);
            border-color: rgba(239, 68, 68, 0.3);
            color: var(--danger);
        }
        
        @media (max-width: 768px) {
            .stats-grid {
                grid-template-columns: 1fr;
                padding: 20px;
            }
            
            .admin-section {
                margin: 15px 20px;
                padding: 20px;
            }
            
            .admin-header {
                padding: 20px;
                flex-direction: column;
                gap: 15px;
                align-items: flex-start;
            }
            
            .header-actions {
                width: 100%;
                justify-content: space-between;
            }
            
            .admin-btn {
                flex: 1;
                justify-content: center;
            }
            
            table {
                font-size: 0.8rem;
            }
            
            th, td {
                padding: 10px 8px;
            }
            
            .form-row {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="admin-container">
        <div class="admin-header">
            <div class="header-left">
                <div class="admin-logo">V</div>
                <div class="admin-titles">
                    <h1>{{ header_title }}</h1>
                    <p>Autopartes Verese Sac - Sistema Administrativo</p>
                </div>
            </div>
            <div class="header-actions">
                <a href="{{ url_for('admin_dashboard') }}" class="admin-btn secondary">📊 Dashboard</a>
                <a href="{{ url_for('admin_inventario') }}" class="admin-btn secondary">📦 Inventario</a>
                <a href="{{ url_for('admin_ventas') }}" class="admin-btn secondary">🛒 Ventas</a>
                <a href="http://127.0.0.1:5000" class="admin-btn secondary" target="_blank">💬 Chat Principal</a>
                <a href="{{ url_for('admin_logout') }}" class="admin-btn logout">🚪 Salir</a>
            </div>
        </div>
        
        {{ content | safe }}
    </div>
</body>
</html>
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
            session['admin_username'] = username
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template_string(LOGIN_TEMPLATE, error='Usuario o contraseña incorrectos')
    
    return render_template_string(LOGIN_TEMPLATE)

@admin_bp.route('/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    return redirect(url_for('admin_login'))

# Rutas de administración protegidas
@admin_bp.route('/dashboard')
@login_required
def admin_dashboard():
    """Dashboard administrativo"""
    try:
        estadisticas = obtener_estadisticas()
        inventario_bajo = obtener_inventario_bajo()
        
        # Ventas recientes
        ventas_recientes = obtener_ventas_por_periodo()[:5]  # Últimas 5 ventas
        
        dashboard_content = f'''
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon">📦</div>
                <div class="stat-number">{estadisticas['total_productos']}</div>
                <div class="stat-label">Total Productos</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">🛒</div>
                <div class="stat-number">{estadisticas['total_ventas']}</div>
                <div class="stat-label">Total Ventas</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">👥</div>
                <div class="stat-number">{estadisticas['total_usuarios']}</div>
                <div class="stat-label">Total Usuarios</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">💰</div>
                <div class="stat-number">S/ {estadisticas['total_ingresos']:.2f}</div>
                <div class="stat-label">Ingresos Totales</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">📈</div>
                <div class="stat-number">{estadisticas['ventas_hoy']}</div>
                <div class="stat-label">Ventas Hoy</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">📅</div>
                <div class="stat-number">{estadisticas['ventas_mes']}</div>
                <div class="stat-label">Ventas Este Mes</div>
            </div>
        </div>
        
        <div class="admin-section">
            <div class="section-header">
                <h2>📦 Inventario Bajo</h2>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Producto</th>
                        <th>Stock</th>
                        <th>Categoría</th>
                        <th>Marca</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(f'<tr><td>{p["nombre"]}</td><td class="stock-bajo">{p["stock"]}</td><td>{p["categoria"]}</td><td>{p["marca"]}</td></tr>' for p in inventario_bajo)}
                    {'' if inventario_bajo else '<tr><td colspan="4" style="text-align: center; color: var(--text-secondary); padding: 30px;">🎉 Todo el inventario está en niveles óptimos</td></tr>'}
                </tbody>
            </table>
        </div>
        
        <div class="admin-section">
            <div class="section-header">
                <h2>🛒 Ventas Recientes</h2>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Cliente</th>
                        <th>Monto</th>
                        <th>Estado</th>
                        <th>Fecha</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(f'<tr><td>#{v["id"]}</td><td>{v["cliente"]}</td><td>S/ {v["monto_total"]:.2f}</td><td class="estado-{v["estado"]}">{v["estado"].upper()}</td><td>{v["fecha_compra"]}</td></tr>' for v in ventas_recientes)}
                    {'' if ventas_recientes else '<tr><td colspan="5" style="text-align: center; color: var(--text-secondary); padding: 30px;">📝 No hay ventas registradas</td></tr>'}
                </tbody>
            </table>
        </div>
        
        <div class="navigation">
            <a href="/admin/inventario" class="admin-btn">📦 Gestionar Inventario</a>
            <a href="/admin/ventas" class="admin-btn">🛒 Ver Todas las Ventas</a>
            <a href="/admin/productos/nuevo" class="admin-btn secondary">➕ Agregar Producto</a>
        </div>
        '''
        
        return render_template_string(BASE_TEMPLATE, 
            title="Dashboard Admin - Autopartes Verese Sac",
            header_title="📊 Dashboard Administrativo",
            content=dashboard_content
        )
    except Exception as e:
        error_content = f'''
        <div class="admin-section">
            <div class="section-header">
                <h2>❌ Error del Sistema</h2>
            </div>
            <div style="text-align: center; padding: 40px;">
                <div style="font-size: 4rem; margin-bottom: 20px;">😵</div>
                <h3 style="margin-bottom: 15px; color: var(--danger);">Error al cargar el dashboard</h3>
                <p style="color: var(--text-secondary); margin-bottom: 25px;">
                    No se pudo conectar a la base de datos. Asegúrate de que el proyecto principal esté ejecutándose.
                </p>
                <p style="color: var(--text-secondary); font-size: 0.9rem;">
                    Error: {str(e)}
                </p>
                <div style="margin-top: 30px;">
                    <a href="http://127.0.0.1:5000" class="admin-btn" target="_blank">🚀 Ejecutar Proyecto Principal</a>
                </div>
            </div>
        </div>
        '''
        return render_template_string(BASE_TEMPLATE, 
            title="Error - Autopartes Verese Sac",
            header_title="❌ Error del Sistema",
            content=error_content
        )

@admin_bp.route('/inventario')
@login_required
def admin_inventario():
    """Página de administración del inventario"""
    try:
        productos = obtener_productos()
        
        productos_html = ""
        for producto in productos:
            stock_class = "stock-bajo" if producto['stock'] <= 5 else ""
            productos_html += f'''
            <tr>
                <td>{producto['codigo']}</td>
                <td>{producto['nombre']}</td>
                <td>{producto['marca']}</td>
                <td>{producto['categoria']}</td>
                <td class="{stock_class}">{producto['stock']}</td>
                <td>S/ {producto['precio']:.2f}</td>
                <td>{producto['numero_serie']}</td>
                <td>
                    <a href="/admin/productos/editar/{producto['id']}" class="admin-btn secondary" style="padding: 6px 12px; font-size: 0.8rem;">✏️ Editar</a>
                    <a href="/admin/productos/eliminar/{producto['id']}" class="admin-btn logout" style="padding: 6px 12px; font-size: 0.8rem;" onclick="return confirm('¿Estás seguro de eliminar este producto?')">🗑️ Eliminar</a>
                </td>
            </tr>
            '''
        
        inventario_content = f'''
        <div class="admin-section">
            <div class="section-header">
                <h2>📋 Inventario Completo</h2>
                <a href="/admin/productos/nuevo" class="admin-btn">➕ Agregar Producto</a>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Código</th>
                        <th>Nombre</th>
                        <th>Marca</th>
                        <th>Categoría</th>
                        <th>Stock</th>
                        <th>Precio</th>
                        <th>N° Serie</th>
                        <th>Acciones</th>
                    </tr>
                </thead>
                <tbody>
                    {productos_html if productos else '<tr><td colspan="8" style="text-align: center; color: var(--text-secondary); padding: 30px;">📝 No hay productos en el inventario</td></tr>'}
                </tbody>
            </table>
        </div>
        
        <div class="navigation">
            <a href="/admin" class="admin-btn">← Volver al Dashboard</a>
            <a href="/admin/productos/nuevo" class="admin-btn secondary">➕ Agregar Nuevo Producto</a>
        </div>
        '''
        
        return render_template_string(BASE_TEMPLATE, 
            title="Inventario - Autopartes Verese Sac",
            header_title="📦 Gestión de Inventario",
            content=inventario_content
        )
    except Exception as e:
        error_content = f'''
        <div class="admin-section">
            <div class="section-header">
                <h2>❌ Error del Sistema</h2>
            </div>
            <div style="text-align: center; padding: 40px;">
                <div style="font-size: 4rem; margin-bottom: 20px;">😵</div>
                <h3 style="margin-bottom: 15px; color: var(--danger);">Error al cargar el inventario</h3>
                <p style="color: var(--text-secondary); margin-bottom: 25px;">
                    No se pudo conectar a la base de datos.
                </p>
                <p style="color: var(--text-secondary); font-size: 0.9rem;">
                    Error: {str(e)}
                </p>
            </div>
        </div>
        '''
        return render_template_string(BASE_TEMPLATE, 
            title="Error - Autopartes Verese Sac",
            header_title="❌ Error del Sistema",
            content=error_content
        )
        
@admin_bp.route('/ventas')
@login_required
def admin_ventas():
    """Página de administración de ventas"""
    try:
        ventas = obtener_ventas_por_periodo()
        
        ventas_html = ""
        for venta in ventas:
            estado_color = {
                'pendiente': 'estado-pendiente',
                'proceso': 'estado-proceso', 
                'completado': 'estado-completado',
                'cancelado': 'estado-cancelado'
            }.get(venta['estado'], '')
            
            ventas_html += f'''
            <tr>
                <td>#{venta['id']}</td>
                <td>{venta['cliente']}</td>
                <td>S/ {venta['monto_total']:.2f}</td>
                <td>{venta['cantidad_total']}</td>
                <td class="{estado_color}">{venta['estado'].upper()}</td>
                <td>{venta['metodo_pago']}</td>
                <td>{venta['fecha_compra']}</td>
            </tr>
            '''
        
        ventas_content = f'''
        <div class="admin-section">
            <div class="section-header">
                <h2>📋 Historial de Ventas</h2>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Cliente</th>
                        <th>Monto</th>
                        <th>Cantidad</th>
                        <th>Estado</th>
                        <th>Método Pago</th>
                        <th>Fecha</th>
                    </tr>
                </thead>
                <tbody>
                    {ventas_html if ventas else '<tr><td colspan="7" style="text-align: center; color: var(--text-secondary); padding: 30px;">📝 No hay ventas registradas</td></tr>'}
                </tbody>
            </table>
        </div>
        
        <div class="navigation">
            <a href="/admin" class="admin-btn">← Volver al Dashboard</a>
            <a href="/admin/inventario" class="admin-btn secondary">📦 Gestionar Inventario</a>
        </div>
        '''
        
        return render_template_string(BASE_TEMPLATE, 
            title="Ventas - Autopartes Verese Sac",
            header_title="🛒 Gestión de Ventas",
            content=ventas_content
        )
    except Exception as e:
        error_content = f'''
        <div class="admin-section">
            <div class="section-header">
                <h2>❌ Error del Sistema</h2>
            </div>
            <div style="text-align: center; padding: 40px;">
                <div style="font-size: 4rem; margin-bottom: 20px;">😵</div>
                <h3 style="margin-bottom: 15px; color: var(--danger);">Error al cargar las ventas</h3>
                <p style="color: var(--text-secondary); margin-bottom: 25px;">
                    No se pudo conectar a la base de datos.
                </p>
                <p style="color: var(--text-secondary); font-size: 0.9rem;">
                    Error: {str(e)}
                </p>
            </div>
        </div>
        '''
        return render_template_string(BASE_TEMPLATE, 
            title="Error - Autopartes Verese Sac",
            header_title="❌ Error del Sistema",
            content=error_content
        )

# Rutas para crear, editar y eliminar productos (se mantienen igual que antes)
@admin_bp.route('/producto/nuevo', methods=['GET', 'POST'])
@login_required
def admin_nuevo_producto():
    """Formulario para crear nuevo producto"""
    if request.method == 'POST':
        codigo = request.form.get('codigo')
        nombre = request.form.get('nombre')
        marca = request.form.get('marca')
        modelo = request.form.get('modelo')
        precio = float(request.form.get('precio'))
        stock = int(request.form.get('stock'))
        descripcion = request.form.get('descripcion')
        garantia = request.form.get('garantia')
        categoria = request.form.get('categoria')
        numero_serie = request.form.get('numero_serie')
        
        if crear_producto(codigo, nombre, marca, modelo, precio, stock, descripcion, garantia, categoria, numero_serie):
            mensaje = '<div class="alert alert-success">✅ Producto creado exitosamente</div>'
        else:
            mensaje = '<div class="alert alert-error">❌ Error al crear el producto (posible código o número de serie duplicado)</div>'
    else:
        mensaje = ''
    
    form_content = f'''
    <div class="admin-section">
        <div class="section-header">
            <h2>➕ Agregar Nuevo Producto</h2>
        </div>
        {mensaje}
        <form method="POST">
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Código *</label>
                    <input type="text" name="codigo" class="form-input" placeholder="FR-001" required>
                </div>
                <div class="form-group">
                    <label class="form-label">N° Serie *</label>
                    <input type="text" name="numero_serie" class="form-input" placeholder="BOS-0987-FR" required>
                </div>
            </div>
            <div class="form-group">
                <label class="form-label">Nombre *</label>
                <input type="text" name="nombre" class="form-input" placeholder="Pastillas de Freno" required>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Marca *</label>
                    <input type="text" name="marca" class="form-input" placeholder="Bosch" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Categoría *</label>
                    <select name="categoria" class="form-select" required>
                        <option value="Frenos">Frenos</option>
                        <option value="Motor">Motor</option>
                        <option value="Suspension">Suspensión</option>
                        <option value="Electrico">Eléctrico</option>
                        <option value="Lubricantes">Lubricantes</option>
                    </select>
                </div>
            </div>
            <div class="form-group">
                <label class="form-label">Modelos Compatibles</label>
                <input type="text" name="modelo" class="form-input" placeholder="Toyota Corolla 2015-2020">
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Precio (S/) *</label>
                    <input type="number" step="0.01" name="precio" class="form-input" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Stock *</label>
                    <input type="number" name="stock" class="form-input" required>
                </div>
            </div>
            <div class="form-group">
                <label class="form-label">Garantía</label>
                <input type="text" name="garantia" class="form-input" placeholder="12 meses">
            </div>
            <div class="form-group">
                <label class="form-label">Descripción</label>
                <textarea name="descripcion" class="form-textarea"></textarea>
            </div>
            <div style="display: flex; gap: 15px;">
                <a href="/admin/inventario" class="admin-btn secondary" style="flex: 1;">Cancelar</a>
                <button type="submit" class="admin-btn" style="flex: 2;">Guardar Producto</button>
            </div>
        </form>
    </div>
    '''
    
    return render_template_string(BASE_TEMPLATE, 
        title="Nuevo Producto - Autopartes Verese Sac",
        header_title="➕ Agregar Nuevo Producto",
        content=form_content
    )

@admin_bp.route('/producto/editar/<int:producto_id>', methods=['GET', 'POST'])
@login_required
def admin_editar_producto(producto_id):
    """Formulario para editar producto"""
    producto = obtener_producto_por_id(producto_id)
    if not producto:
        return "Producto no encontrado", 404
    
    if request.method == 'POST':
        codigo = request.form.get('codigo')
        nombre = request.form.get('nombre')
        marca = request.form.get('marca')
        modelo = request.form.get('modelo')
        precio = float(request.form.get('precio'))
        stock = int(request.form.get('stock'))
        descripcion = request.form.get('descripcion')
        garantia = request.form.get('garantia')
        categoria = request.form.get('categoria')
        numero_serie = request.form.get('numero_serie')
        
        if actualizar_producto(producto_id, codigo, nombre, marca, modelo, precio, stock, descripcion, garantia, categoria, numero_serie):
            mensaje = '<div class="alert alert-success">✅ Producto actualizado</div>'
            producto = obtener_producto_por_id(producto_id)
        else:
            mensaje = '<div class="alert alert-error">❌ Error al actualizar</div>'
    else:
        mensaje = ''
    
    form_content = f'''
    <div class="admin-section">
        <div class="section-header">
            <h2>✏️ Editar Producto</h2>
        </div>
        {mensaje}
        <form method="POST">
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Código *</label>
                    <input type="text" name="codigo" value="{producto['codigo']}" class="form-input" required>
                </div>
                <div class="form-group">
                    <label class="form-label">N° Serie *</label>
                    <input type="text" name="numero_serie" value="{producto['numero_serie']}" class="form-input" required>
                </div>
            </div>
            <div class="form-group">
                <label class="form-label">Nombre *</label>
                <input type="text" name="nombre" value="{producto['nombre']}" class="form-input" required>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Marca *</label>
                    <input type="text" name="marca" value="{producto['marca']}" class="form-input" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Categoría *</label>
                    <select name="categoria" class="form-select" required>
                        <option value="Frenos" {"selected" if producto['categoria']=='Frenos' else ""}>Frenos</option>
                        <option value="Motor" {"selected" if producto['categoria']=='Motor' else ""}>Motor</option>
                        <option value="Suspension" {"selected" if producto['categoria']=='Suspension' else ""}>Suspensión</option>
                        <option value="Electrico" {"selected" if producto['categoria']=='Electrico' else ""}>Eléctrico</option>
                        <option value="Lubricantes" {"selected" if producto['categoria']=='Lubricantes' else ""}>Lubricantes</option>
                    </select>
                </div>
            </div>
            <div class="form-group">
                <label class="form-label">Modelos Compatibles</label>
                <input type="text" name="modelo" value="{producto['modelo'] or ''}" class="form-input">
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Precio (S/) *</label>
                    <input type="number" step="0.01" name="precio" value="{producto['precio']}" class="form-input" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Stock *</label>
                    <input type="number" name="stock" value="{producto['stock']}" class="form-input" required>
                </div>
            </div>
            <div class="form-group">
                <label class="form-label">Garantía</label>
                <input type="text" name="garantia" value="{producto['garantia'] or ''}" class="form-input">
            </div>
            <div class="form-group">
                <label class="form-label">Descripción</label>
                <textarea name="descripcion" class="form-textarea">{producto['descripcion'] or ''}</textarea>
            </div>
            <div style="display: flex; gap: 15px;">
                <a href="/admin/inventario" class="admin-btn secondary" style="flex: 1;">Cancelar</a>
                <button type="submit" class="admin-btn" style="flex: 2;">Actualizar Producto</button>
            </div>
        </form>
    </div>
    '''
    
    return render_template_string(BASE_TEMPLATE, 
        title=f"Editar {producto['nombre']}",
        header_title=f"✏️ Editar {producto['nombre']}",
        content=form_content
    )

@admin_bp.route('/producto/eliminar/<int:producto_id>')
@login_required
def admin_eliminar_producto(producto_id):
    """Eliminar producto"""
    if eliminar_producto(producto_id):
        return redirect(url_for('admin_inventario'))
    else:
        return "Error al eliminar", 500

def abrir_navegador():
    """Abre el navegador automáticamente"""
    time.sleep(2)
    webbrowser.open('http://127.0.0.1:5001/admin/login')


