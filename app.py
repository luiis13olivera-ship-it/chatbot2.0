from flask import Flask, request, jsonify, g, session, redirect, url_for
import webbrowser
import threading
import random
import time
from datetime import datetime
import sqlite3
import json
import os
import hashlib
from admin_system import admin_bp

app = Flask(__name__)
app.secret_key = 'autopartes_verese_secret_key_2024'

app.register_blueprint(admin_bp, url_prefix='/admin')

# Configuración de la base de datos
DATABASE = 'autopartes.db'

# Credenciales de administradores

def get_db():
    """Obtiene la conexión a la base de datos"""
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
    """Inicializa la base de datos con las tablas necesarias"""
    db = get_db()
    
    # Tabla de productos (inventario)
    db.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            marca TEXT NOT NULL,
            modelo TEXT,
            precio REAL NOT NULL,
            stock INTEGER NOT NULL,
            descripcion TEXT,
            garantia TEXT,
            categoria TEXT NOT NULL,
            numero_serie TEXT UNIQUE,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            activo BOOLEAN DEFAULT 1
        )
    ''')
    
    # Tabla de usuarios
    db.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            correo_electronico TEXT UNIQUE NOT NULL,
            telefono TEXT,
            direccion TEXT,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabla de compras
    db.execute('''
        CREATE TABLE IF NOT EXISTS compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            fecha_compra TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cantidad_total INTEGER NOT NULL,
            monto_total REAL NOT NULL,
            monto_igv REAL NOT NULL,
            monto_subtotal REAL NOT NULL,
            estado TEXT NOT NULL CHECK(estado IN ('pendiente', 'proceso', 'completado', 'cancelado')),
            metodo_pago TEXT NOT NULL,
            codigo_seguimiento TEXT,
            direccion_entrega TEXT,
            telefono_contacto TEXT,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    # Tabla de detalles de compra (productos en cada compra)
    db.execute('''
        CREATE TABLE IF NOT EXISTS detalle_compra (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            compra_id INTEGER NOT NULL,
            producto_id INTEGER NOT NULL,
            cantidad INTEGER NOT NULL,
            precio_unitario REAL NOT NULL,
            subtotal REAL NOT NULL,
            FOREIGN KEY (compra_id) REFERENCES compras (id),
            FOREIGN KEY (producto_id) REFERENCES productos (id)
        )
    ''')
    
    # Tabla de pagos
    db.execute('''
        CREATE TABLE IF NOT EXISTS pagos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            compra_id INTEGER NOT NULL,
            metodo_pago TEXT NOT NULL,
            monto REAL NOT NULL,
            estado TEXT NOT NULL CHECK(estado IN ('pendiente', 'completado', 'fallido', 'reembolsado')),
            fecha_pago TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            codigo_transaccion TEXT,
            datos_pago TEXT,
            FOREIGN KEY (compra_id) REFERENCES compras (id)
        )
    ''')
    
    db.commit()
    insert_datos_iniciales(db)

def insert_datos_iniciales(db):
    """Inserta datos iniciales en la base de datos"""
    
    # Verificar si ya existen productos
    productos_existentes = db.execute('SELECT COUNT(*) as count FROM productos').fetchone()
    if productos_existentes['count'] > 0:
        return
    
    # Productos de ejemplo
    productos = [
        # Frenos
        ('FR-001', 'Pastillas de Freno Delanteras Cerámicas', 'Bosch', 
         'Toyota Corolla 2015-2020,Honda Civic 2016-2021', 180.00, 15,
         'Pastillas de freno cerámicas de alto rendimiento, baja emisión de polvo y mayor durabilidad',
         '12 meses', 'Frenos', 'BOS-0987-FR'),
        
        ('FR-002', 'Disco de Freno Delantero Ventilado', 'Brembo',
         'Nissan Sentra 2014-2019,Hyundai Elantra 2015-2020', 320.00, 8,
         'Disco de freno ventilado para mejor disipación de calor, performance deportivo',
         '18 meses', 'Frenos', 'BRE-1234-FD'),
        
        ('FR-003', 'Kit de Pastillas Traseras', 'ACDelco',
         'Chevrolet Aveo 2012-2018,Suzuki Swift 2010-2017', 150.00, 12,
         'Kit completo pastillas traseras, incluye sensores de desgaste',
         '12 meses', 'Frenos', 'ACD-5678-RT'),
        
        # Motor
        ('MO-001', 'Filtro de Aceite Sintético', 'Mann-Filter',
         'VW Golf 2015-2020,Audi A3 2014-2019', 45.00, 25,
         'Filtro de aceite de alta eficiencia para aceites sintéticos',
         '6 meses', 'Motor', 'MAN-9012-OF'),
        
        ('MO-002', 'Kit de Correa de Distribución', 'Gates',
         'Toyota Hilux 2015-2021,Ford Ranger 2016-2022', 420.00, 6,
         'Kit completo: correa, tensores y poleas. Calidad premium',
         '24 meses', 'Motor', 'GAT-3456-TK'),
        
        ('MO-003', 'Bujías de Iridio', 'NGK',
         'BMW Serie 3 2012-2019,Mercedes-Benz Clase C 2013-2018', 280.00, 18,
         'Bujías de iridio para mejor combustión y ahorro de combustible',
         '12 meses', 'Motor', 'NGK-7890-SP'),
        
        # Suspensión
        ('SU-001', 'Amortiguador Delantero Gas', 'KYB',
         'Kia Rio 2011-2017,Hyundai Accent 2010-2017', 380.00, 10,
         'Amortiguador a gas, comfort superior y durabilidad extendida',
         '18 meses', 'Suspension', 'KYB-1122-SF'),
        
        ('SU-002', 'Kit de Rotulas y Terminales', 'TRW',
         'Nissan Tiida 2007-2014,Renault Logan 2009-2015', 220.00, 14,
         'Kit completo dirección, incluye rotulas y terminales',
         '12 meses', 'Suspension', 'TRW-3344-ST'),
        
        # Eléctrico
        ('EL-001', 'Batería 12V 60Ah', 'ACDelco',
         'Toyota Yaris 2014-2020,Honda Fit 2013-2020', 480.00, 9,
         'Batería libre de mantenimiento, alta capacidad de arranque',
         '24 meses', 'Electrico', 'ACD-5566-BT'),
        
        ('EL-002', 'Alternador 12V 90A', 'Denso',
         'Mitsubishi L200 2015-2021,Nissan NP300 2014-2020', 850.00, 4,
         'Alternador reconstruido con garantía, incluye instalación',
         '12 meses', 'Electrico', 'DEN-7788-AL'),
        
        # Aceites
        ('AC-001', 'Aceite Sintético 5W-30', 'Mobil',
         'Vehículos a gasolina 2010-2023', 180.00, 30,
         'Aceite sintético full, protección superior del motor',
         'N/A', 'Lubricantes', 'MOB-9900-SY'),
        
        ('AC-002', 'Aceite Mineral 20W-50', 'Repsol',
         'Vehículos antiguos y motos', 95.00, 22,
         'Aceite mineral para motores de alto kilometraje',
         'N/A', 'Lubricantes', 'REP-8811-MN')
    ]
    
    for producto in productos:
        db.execute('''
            INSERT INTO productos (codigo, nombre, marca, modelo, precio, stock, 
                                 descripcion, garantia, categoria, numero_serie)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', producto)
    
    # Usuarios de ejemplo
    usuarios = [
    ]
    
    for usuario in usuarios:
        db.execute('''
            INSERT INTO usuarios (nombre, correo_electronico, telefono, direccion)
            VALUES (?, ?, ?, ?)
        ''', usuario)
    
    db.commit()

# Funciones para gestionar productos
def obtener_productos(categoria=None, marca=None, modelo=None):
    """Obtiene productos con filtros opcionales"""
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
    
    # Convertir a formato compatible con el código existente
    productos_formateados = []
    for producto in productos:
        producto_dict = dict(producto)
        # Convertir el campo modelo en lista para compatibilidad
        if producto_dict['modelo']:
            producto_dict['modelo_compatible'] = [m.strip() for m in producto_dict['modelo'].split(',')]
        else:
            producto_dict['modelo_compatible'] = []
        
        # Usar código como ID para compatibilidad
        producto_dict['id'] = producto_dict['codigo']
        
        productos_formateados.append(producto_dict)
    
    return productos_formateados

def actualizar_stock(producto_id, nueva_cantidad):
    """Actualiza el stock de un producto"""
    db = get_db()
    db.execute(
        'UPDATE productos SET stock = ? WHERE codigo = ?',
        (nueva_cantidad, producto_id)
    )
    db.commit()

# Funciones para gestionar usuarios
def crear_usuario(nombre, correo, telefono=None, direccion=None):
    """Crea un nuevo usuario"""
    db = get_db()
    try:
        cursor = db.execute(
            'INSERT INTO usuarios (nombre, correo_electronico, telefono, direccion) VALUES (?, ?, ?, ?)',
            (nombre, correo, telefono, direccion)
        )
        db.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        # Si el correo ya existe, retornar el ID existente
        usuario = db.execute(
            'SELECT id FROM usuarios WHERE correo_electronico = ?',
            (correo,)
        ).fetchone()
        return usuario['id'] if usuario else None

# Funciones para gestionar compras
def crear_compra(usuario_id, productos, metodo_pago, direccion_entrega, telefono_contacto):
    """Crea una nueva compra"""
    db = get_db()
    
    # Calcular totales
    cantidad_total = sum(item['cantidad'] for item in productos)
    monto_subtotal = sum(item['cantidad'] * item['precio'] for item in productos)
    monto_igv = monto_subtotal * 0.18  # 18% IGV
    monto_total = monto_subtotal + monto_igv
    
    # Crear la compra
    cursor = db.execute(
        '''INSERT INTO compras (usuario_id, cantidad_total, monto_total, monto_igv, monto_subtotal, 
                              estado, metodo_pago, direccion_entrega, telefono_contacto) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (usuario_id, cantidad_total, monto_total, monto_igv, monto_subtotal, 
         'pendiente', metodo_pago, direccion_entrega, telefono_contacto)
    )
    compra_id = cursor.lastrowid
    
    # Agregar detalles de compra
    for producto in productos:
        # Obtener el ID real del producto basado en el código
        producto_db = db.execute(
            'SELECT id, precio FROM productos WHERE codigo = ?', (producto['id'],)
        ).fetchone()
        
        if producto_db:
            db.execute(
                'INSERT INTO detalle_compra (compra_id, producto_id, cantidad, precio_unitario, subtotal) VALUES (?, ?, ?, ?, ?)',
                (compra_id, producto_db['id'], producto['cantidad'], producto_db['precio'], producto['cantidad'] * producto_db['precio'])
            )
            
            # Actualizar stock
            producto_actual = db.execute(
                'SELECT stock FROM productos WHERE id = ?', (producto_db['id'],)
            ).fetchone()
            
            nuevo_stock = producto_actual['stock'] - producto['cantidad']
            db.execute(
                'UPDATE productos SET stock = ? WHERE id = ?',
                (nuevo_stock, producto_db['id'])
            )
    
    db.commit()
    return compra_id

def actualizar_estado_compra(compra_id, nuevo_estado):
    """Actualiza el estado de una compra"""
    db = get_db()
    db.execute(
        'UPDATE compras SET estado = ? WHERE id = ?',
        (nuevo_estado, compra_id)
    )
    db.commit()

# Funciones para gestionar pagos
def registrar_pago(compra_id, metodo_pago, monto, datos_pago=None):
    """Registra un pago"""
    db = get_db()
    
    datos_pago_json = json.dumps(datos_pago) if datos_pago else None
    
    db.execute(
        'INSERT INTO pagos (compra_id, metodo_pago, monto, estado, datos_pago) VALUES (?, ?, ?, ?, ?)',
        (compra_id, metodo_pago, monto, 'completado', datos_pago_json)
    )
    
    # Actualizar estado de la compra
    db.execute(
        'UPDATE compras SET estado = ? WHERE id = ?',
        ('proceso', compra_id)
    )
    
    db.commit()

# Funciones para reportes y consultas
def obtener_ventas_por_periodo(fecha_inicio, fecha_fin):
    """Obtiene ventas por periodo"""
    db = get_db()
    ventas = db.execute('''
        SELECT c.fecha_compra, c.monto_total, u.nombre as cliente, c.estado
        FROM compras c
        JOIN usuarios u ON c.usuario_id = u.id
        WHERE c.fecha_compra BETWEEN ? AND ?
        ORDER BY c.fecha_compra DESC
    ''', (fecha_inicio, fecha_fin)).fetchall()
    
    return [dict(venta) for venta in ventas]

def obtener_inventario_bajo(limite=5):
    """Obtiene productos con stock bajo"""
    db = get_db()
    productos = db.execute('''
        SELECT * FROM productos 
        WHERE stock <= ? AND activo = 1
        ORDER BY stock ASC
    ''', (limite,)).fetchall()
    
    return [dict(producto) for producto in productos]

# Sistema de autenticación

class ChatBotAutopartes:
    def __init__(self):
        self.respuestas = {
            'horario': {
                'titulo': 'Horario de Atención',
                'contenido': '**Lunes a Viernes:** 8:00 a.m. - 18:00 p.m.\n**Sábados:** 9:00 a.m. - 14:00 p.m.\n**Domingos:** Cerrado',
                'icono': '🕒',
                'color': '#F59E0B'
            },
            'ubicacion': {
                'titulo': 'Ubicación y Sucursales',
                'contenido': '''**📍 Sucursal Principal:**
Av. Las Autopartes 123
San Juan de Lurigancho, Lima, Perú

**📍 Sucursal Centro:**
Jr. Repuestos 456, Cercado de Lima

**Horario de atención en ambas sucursales:**
Lunes a Viernes: 8:00 am - 6:00 pm
Sábados: 9:00 am - 2:00 pm''',
                'icono': '📍',
                'color': '#EF4444',
                'mapa': True
            },
            'productos': {
                'titulo': 'Catálogo de Autopartes',
                'contenido': '''**🔧 MOTOR Y TRANSMISIÓN**
• Motores completos reconstruidos
• Transmisiones automáticas y manuales
• Culatas, bloques y kits de reparación
• Embragues y componentes

**🛑 SISTEMA DE FRENOS**
• Pastillas de freno (cerámica, semi-metálica)
• Discos y tambores
• Líquido de frenos DOT 3, DOT 4
• Calipers y cilindros de rueda

**⚡ SISTEMA ELÉCTRICO**
• Baterías (12V, 24V)
• Alternadores y motor de arranque
• Sensores y módulos de control
• Cableados y fusibles

**🔄 SUSPENSIÓN Y DIRECCIÓN**
• Amortiguadores (hidráulicos, gas)
• Rotulas, terminales y bujes
• Barras estabilizadoras
• Caja de dirección

**🛢️ LUBRICANTES Y FLUIDOS**
• Aceites sintéticos y minerales
• Refrigerante y anticongelante
• Liquido de dirección hidráulica
• Grasas multiusos y especializadas''',
                'icono': '🚗',
                'color': '#10B981'
            },
            'marcas': {
                'titulo': 'Marcas y Proveedores',
                'contenido': '''**🏆 Marcas Premium:**
• Toyota • Nissan • Honda
• Hyundai • Kia • Chevrolet
• Ford • Volkswagen • BMW

**🇪🇺 Marcas Europeas:**
• Mercedes-Benz • Audi • Volvo
• Renault • Peugeot • Fiat

**🇺🇸 Marcas Americanas:**
• Dodge • Chrysler • Jeep • GMC

**🔩 Proveedores Oficiales:**
• Bosch • Denso • ACDelco
• Monroe • KYB • Gates

**Trabajamos con las mejores marcas del mercado**''',
                'icono': '🏷️',
                'color': '#8B5CF6'
            },
            'cotizacion': {
                'titulo': 'Cotizaciones y Precios',
                'contenido': '''**📋 Para una cotización precisa necesitamos:**

1. **Marca y modelo** del vehículo
2. **Año** de fabricación
3. **Autoparte específica** requerida
4. **Número de VIN** (opcional)

**💳 Métodos de pago aceptados:**
• Efectivo • Tarjetas crédito/débito
• Transferencia bancaria • Yape/Plin

**🚚 Opciones de entrega:**
• Recojo en tienda • Delivery express
• Envío a provincia''',
                'icono': '💰',
                'color': '#F59E0B'
            },
            'garantia': {
                'titulo': 'Garantías y Políticas',
                'contenido': '''**✅ Nuestro Compromiso de Calidad:**

**🛡️ Garantía en Autopartes:**
• 6 meses a 1 año según el producto
• Cobertura total por defectos de fabricación
• Reemplazo inmediato en caso de fallas

**📝 Política de Devoluciones:**
• 30 días para devoluciones
• Producto en perfecto estado
• Embalaje original completo

**🔧 Servicio de Instalación:**
• Taller propio especializado
• Técnicos certificados
• Garantía en mano de obra''',
                'icono': '🔧',
                'color': '#06B6D4'
            },
            'contacto': {
                'titulo': 'Contacto y Comunicación',
                'contenido': '''**📞 Atención Telefónica:**
• Central: (01) 456-7890
• Ventas: (01) 6200 158
• Soporte Técnico: (01) 456-7892

**📱 WhatsApp Business:**
• +51 987 654 321 (Ventas)
• +51 987 654 322 (Soporte)

**✉️ Correos Electrónicos:**
• General: info@autopartesvirtual.com
• Ventas: ventas@autopartesvirtual.com
• Soporte: soporte@autopartesvirtual.com

**🌐 Redes Sociales:**
• Facebook: /AutopartesVirtual
• Instagram: @AutopartesVirtual
• TikTok: @AutopartesVirtual''',
                'icono': '📞',
                'color': '#EC4899'
            },
            'servicios': {
                'titulo': 'Servicios Adicionales',
                'contenido': '''**🔧 SERVICIOS PROFESIONALES:**

**🛠️ Instalación y Montaje:**
• Instalación de autopartes
• Diagnóstico computarizado
• Mantenimiento preventivo

**🚗 Asesoría Técnica:**
• Asesoramiento especializado
• Recomendaciones técnicas
• Solución de problemas

**📦 Logística y Entrega:**
• Delivery express (2-4 horas)
• Envíos a nivel nacional
• Instalación a domicilio

**🔄 Plan de Mantenimiento:**
• Programas de mantenimiento
• Recordatorios automáticos
• Descuentos por fidelidad''',
                'icono': '⚙️',
                'color': '#84CC16'
            }
        }
        
        self.saludos = [
            "¡Hola! Soy tu asistente virtual de Autopartes - Verese Sac. ¿En qué puedo ayudarte hoy?",
            "¡Buen día! Estoy aquí para ayudarte a encontrar las autopartes que necesitas. ¿Qué estás buscando?",
            "¡Hola! Bienvenido a Autopartes - Verese Sac. Cuéntame, ¿qué autoparte necesitas para tu vehículo?",
            "¡Hola! 👋 ¿Buscas autopartes? Estoy aquí para asesorarte y ayudarte a encontrar lo que necesitas."
        ]
        
        self.despedidas = [
            "¡Gracias por contactarnos! Espero haberte ayudado. No dudes en volver si necesitas más autopartes.",
            "¡Hasta pronto! Recuerda que tenemos las mejores autopartes con garantía y calidad certificada.",
            "¡Que tengas un excelente día! Si necesitas algo más, aquí estaré para ayudarte.",
            "¡Fue un gusto atenderte! No olvides que tenemos promociones especiales cada semana."
        ]

    def buscar_productos(self, categoria=None, marca=None, modelo=None):
        """Busca productos en la base de datos según los criterios"""
        return obtener_productos(categoria, marca, modelo)

    def formatear_catalogo_tabla(self, productos):
        """Formatea los productos en una tabla HTML"""
        if not productos:
            return {
                'html': '''
                <div class="no-products">
                    <div class="no-products-icon">🔍</div>
                    <h3>No se encontraron productos</h3>
                    <p>Intenta con otros criterios de búsqueda o consulta nuestro catálogo completo.</p>
                </div>
                '''
            }
        
        # Crear tabla HTML
        tabla_html = f'''
        <div class="catalogo-header">
            <h3>📦 Catálogo de Autopartes</h3>
            <p>Mostrando {len(productos)} productos encontrados</p>
        </div>
        
        <div class="table-container">
            <table class="catalogo-table">
                <thead>
                    <tr>
                        <th class="col-modelo">Modelo Compatible</th>
                        <th class="col-precio">Precio</th>
                        <th class="col-tipo">Tipo de Pieza</th>
                        <th class="col-marca">Marca</th>
                        <th class="col-serie">Número de Serie</th>
                        <th class="col-stock">Stock</th>
                    </tr>
                </thead>
                <tbody>
        '''
        
        for producto in productos:
            # Determinar clase de stock
            stock_class = "stock-alto"
            if producto['stock'] <= 5:
                stock_class = "stock-bajo"
            elif producto['stock'] <= 10:
                stock_class = "stock-medio"
            
            # Formatear modelos compatibles (mostrar máximo 2)
            modelos = producto['modelo_compatible'][:2]
            if len(producto['modelo_compatible']) > 2:
                modelos.append(f"+{len(producto['modelo_compatible']) - 2} más")
            
            modelos_html = "<br>".join(modelos)
            
            tabla_html += f'''
                    <tr class="producto-row">
                        <td class="col-modelo">
                            <div class="modelo-info">
                                <strong>{producto['nombre']}</strong>
                                <div class="modelos-compatibles">{modelos_html}</div>
                            </div>
                        </td>
                        <td class="col-precio">
                            <div class="precio">S/ {producto['precio']:.2f}</div>
                        </td>
                        <td class="col-tipo">
                            <span class="badge-categoria">{producto['categoria']}</span>
                        </td>
                        <td class="col-marca">
                            <div class="marca-info">
                                <span class="marca-nombre">{producto['marca']}</span>
                            </div>
                        </td>
                        <td class="col-serie">
                            <code class="numero-serie">{producto['numero_serie']}</code>
                        </td>
                        <td class="col-stock">
                            <div class="stock-info {stock_class}">
                                {producto['stock']} unidades
                            </div>
                        </td>
                    </tr>
            '''
        
        tabla_html += '''
                </tbody>
            </table>
        </div>
        
        <div class="catalogo-footer">
            <div class="leyenda-stock">
                <div class="leyenda-item">
                    <span class="indicador-stock stock-alto"></span>
                    <span>Stock alto</span>
                </div>
                <div class="leyenda-item">
                    <span class="indicador-stock stock-medio"></span>
                    <span>Stock medio</span>
                </div>
                <div class="leyenda-item">
                    <span class="indicador-stock stock-bajo"></span>
                    <span>Stock bajo</span>
                </div>
            </div>
            <p class="nota-catalogo">💡 <em>Para más información sobre un producto específico, solicita una cotización detallada.</em></p>
        </div>
        '''
        
        return {'html': tabla_html}

    def procesar_pregunta(self, pregunta):
        pregunta = pregunta.lower().strip()
        
        # Saludo inicial
        if any(palabra in pregunta for palabra in ['hola', 'buenos días', 'buenas tardes', 'buenas', 'hi', 'hello', 'buen dia']):
            return {
                'titulo': '¡Hola!',
                'contenido': random.choice(self.saludos),
                'icono': '👋',
                'color': '#3B82F6'
            }
        
        # Métodos de pago
        elif any(palabra in pregunta for palabra in ['métodos de pago', 'metodos de pago', 'cuales son sus métodos de pago', 'tipo de pago', 'pagos', 'formas de pago', 'medios de pago']):
            return {
                'titulo': 'Métodos de Pago',
                'contenido': '''**Excelente pregunta, contamos con todo tipo de pago para BCP, BVVA e INTERBANK:**

💳 **Yape:** +51 978 462 485
📱 **Plin:** +51 978 462 485  
🏦 **Transferencia:** 1558 - 1749667 - 26560

**También aceptamos:**
• Efectivo en soles
• Tarjetas de crédito/débito (Visa, MasterCard)
• Depósitos bancarios
• Pago contra entrega''',
                'icono': '💳',
                'color': '#10B981'
            }
        
        # Catálogo y productos específicos
        elif any(palabra in pregunta for palabra in ['catalogo', 'catálogo', 'productos', 'piezas', 'repuestos', 'stock', 'disponible', 'listado', 'inventario', 'tabla', 'precios']):
            productos = self.buscar_productos()
            return {
                'titulo': 'Catálogo Completo',
                'contenido': 'Consulta nuestro catálogo completo de autopartes:',
                'icono': '📊',
                'color': '#10B981',
                'tipo': 'catalogo_tabla',
                'tabla': self.formatear_catalogo_tabla(productos[:15])
            }
        
        # Búsqueda por categoría
        elif any(palabra in pregunta for palabra in ['frenos', 'pastillas', 'discos']):
            productos = self.buscar_productos(categoria='Frenos')
            return {
                'titulo': 'Sistema de Frenos',
                'contenido': 'Productos disponibles en sistema de frenos:',
                'icono': '🛑',
                'color': '#EF4444',
                'tipo': 'catalogo_tabla',
                'tabla': self.formatear_catalogo_tabla(productos)
            }
        
        elif any(palabra in pregunta for palabra in ['motor', 'correa', 'bujías', 'filtro']):
            productos = self.buscar_productos(categoria='Motor')
            return {
                'titulo': 'Sistema del Motor',
                'contenido': 'Productos disponibles en sistema del motor:',
                'icono': '🔧',
                'color': '#F59E0B',
                'tipo': 'catalogo_tabla',
                'tabla': self.formatear_catalogo_tabla(productos)
            }
        
        elif any(palabra in pregunta for palabra in ['suspensión', 'suspension', 'amortiguador', 'rotula']):
            productos = self.buscar_productos(categoria='Suspension')
            return {
                'titulo': 'Suspensión y Dirección',
                'contenido': 'Productos disponibles en suspensión:',
                'icono': '🔄',
                'color': '#8B5CF6',
                'tipo': 'catalogo_tabla',
                'tabla': self.formatear_catalogo_tabla(productos)
            }
        
        elif any(palabra in pregunta for palabra in ['eléctrico', 'electrico', 'batería', 'bateria', 'alternador']):
            productos = self.buscar_productos(categoria='Electrico')
            return {
                'titulo': 'Sistema Eléctrico',
                'contenido': 'Productos disponibles en sistema eléctrico:',
                'icono': '⚡',
                'color': '#F59E0B',
                'tipo': 'catalogo_tabla',
                'tabla': self.formatear_catalogo_tabla(productos)
            }
        
        elif any(palabra in pregunta for palabra in ['aceite', 'lubricante', 'fluido']):
            productos = self.buscar_productos(categoria='Lubricantes')
            return {
                'titulo': 'Lubricantes y Fluidos',
                'contenido': 'Productos disponibles en lubricantes:',
                'icono': '🛢️',
                'color': '#06B6D4',
                'tipo': 'catalogo_tabla',
                'tabla': self.formatear_catalogo_tabla(productos)
            }
        
        # Búsqueda por marca
        elif any(palabra in pregunta for palabra in ['bosch', 'brembo', 'acdelco', 'denso', 'ngk', 'kyb']):
            marca = next((p for p in ['bosch', 'brembo', 'acdelco', 'denso', 'ngk', 'kyb'] if p in pregunta), None)
            if marca:
                productos = self.buscar_productos(marca=marca.capitalize())
                return {
                    'titulo': f'Productos {marca.upper()}',
                    'contenido': f'Productos disponibles de la marca {marca.upper()}:',
                    'icono': '🏷️',
                    'color': '#8B5CF6',
                    'tipo': 'catalogo_tabla',
                    'tabla': self.formatear_catalogo_tabla(productos)
                }
        
        # Horario de atención
        elif any(palabra in pregunta for palabra in ['horario', 'hora', 'atención', 'abren', 'cierra', 'atienden', 'cuándo', 'cuando', 'disponible']):
            return self.respuestas['horario']
        
        # Ubicación
        elif any(palabra in pregunta for palabra in ['ubicación', 'dirección', 'mapa', 'donde', 'lugar', 'ubicacion', 'local', 'ubican', 'encuentran', 'sucursal', 'direccion']):
            return self.respuestas['ubicacion']
        
        # Marcas
        elif any(palabra in pregunta for palabra in ['marca', 'modelo', 'toyota', 'nissan', 'honda', 'hyundai', 'chevrolet', 'ford', 'bmw', 'mercedes', 'proveedor']):
            return self.respuestas['marcas']
        
        # Cotización
        elif any(palabra in pregunta for palabra in ['costo', 'precio', 'cuánto', 'vale', 'costos', 'precios', 'cotización', 'cotizacion', 'presupuesto', 'valor']):
            return self.respuestas['cotizacion']
        
        # Garantía
        elif any(palabra in pregunta for palabra in ['garantía', 'garantia', 'calidad', 'confianza', 'seguro', 'devolución', 'devolucion', 'calidad']):
            return self.respuestas['garantia']
        
        # Contacto
        elif any(palabra in pregunta for palabra in ['contacto', 'teléfono', 'telefono', 'whatsapp', 'email', 'correo', 'llamar', 'comunico', 'comunicar', 'comunicación', 'comunicacion']):
            return self.respuestas['contacto']
        
        # Servicios
        elif any(palabra in pregunta for palabra in ['servicio', 'servicios', 'instalación', 'instalacion', 'montaje', 'asesoría', 'asesoria', 'taller', 'mantenimiento']):
            return self.respuestas['servicios']
        
        # Envíos
        elif any(palabra in pregunta for palabra in ['envío', 'envio', 'delivery', 'entrega', 'shipping', 'domicilio', 'enviar', 'recoger']):
            return {
                'titulo': 'Envíos y Logística',
                'contenido': '''**🚚 SERVICIO DE DELIVERY:**

**📦 Entrega Express:**
• Lima Metropolitana: 2-4 horas
• Provincias: 24-48 horas
• Urgente: 1 hora (costo adicional)

**💰 Costos de Envío:**
• Lima: S/ 15 - S/ 25
• Provincias: S/ 25 - S/ 50
• *Envío GRATIS en compras mayores a S/ 500*

**🏍️ Opciones de Entrega:**
• Motocourier express
• Courier especializado
• Recojo en tienda (gratis)''',
                'icono': '🚚',
                'color': '#F97316'
            }
        
        # Despedida
        elif any(palabra in pregunta for palabra in ['adiós', 'chao', 'gracias', 'bye', 'salir', 'nos vemos', 'hasta luego']):
            return {
                'titulo': '¡Hasta pronto!',
                'contenido': random.choice(self.despedidas),
                'icono': '👋',
                'color': '#3B82F6'
            }
        
        else:
            return {
                'titulo': 'No entendí tu pregunta',
                'contenido': '''Puedo ayudarte con información sobre:

• 🚗 Catálogo completo de autopartes
• 🛑 Sistema de frenos
• 🔧 Motor y transmisión
• 🔄 Suspensión y dirección
• ⚡ Sistema eléctrico
• 🛢️ Lubricantes y fluidos
• 🏷️ Marcas específicas
• 💰 Cotizaciones y precios
• 💳 Métodos de pago
• 📍 Ubicación y sucursales
• 🔧 Garantías y políticas

¿Sobre qué te gustaría consultar?''',
                'icono': '🤔',
                'color': '#6B7280'
            }

chatbot = ChatBotAutopartes()

# Inicializar base de datos al inicio
with app.app_context():
    init_db()

# Ruta de login para administración - CON DISEÑO MEJORADO


# [El resto del código permanece exactamente igual...]
# Solo he modificado la parte de autenticación y login para agregar el diseño
# El resto del código del chatbot se mantiene intacto

@app.route('/')
def home():
    # [Todo el código HTML del chatbot permanece igual...]
     return r'''
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Autopartes - Verese Sac - AI Assistant</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary: #10a37f;
                --primary-dark: #0d8c6c;
                --sidebar: #1a1b26;
                --chat-bg: #161722;
                --user-bg: #1e1f2e;
                --bot-bg: #161722;
                --text-primary: #e0e6f0;
                --text-secondary: #a0a6b8;
                --border: #2a2b3c;
                --accent: #19c37d;
                --card-bg: #1e1f2e;
                --gradient-1: #10a37f;
                --gradient-2: #1e40af;
                --success: #10B981;
                --warning: #F59E0B;
                --danger: #EF4444;
                --info: #3B82F6;
                --logo-primary: #10a37f;
                --logo-secondary: #1e40af;
                --logo-accent: #19c37d;
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
                height: 100vh;
                display: flex;
            }
            
            .app-container {
                display: flex;
                width: 100%;
                height: 100vh;
                background: rgba(22, 23, 34, 0.95);
                backdrop-filter: blur(10px);
            }
            
            .sidebar {
                width: 280px;
                background: var(--sidebar);
                display: flex;
                flex-direction: column;
                border-right: 1px solid var(--border);
                position: relative;
                z-index: 10;
            }
            
            .sidebar-header {
                padding: 24px 20px;
                border-bottom: 1px solid var(--border);
                background: linear-gradient(135deg, rgba(16, 163, 127, 0.1) 0%, rgba(30, 64, 175, 0.1) 100%);
            }
            
            .logo {
                display: flex;
                align-items: center;
                gap: 12px;
                font-size: 1.1rem;
                font-weight: 700;
            }
            
            .logo-icon {
                width: 50px;
                height: 50px;
                background: linear-gradient(135deg, var(--logo-primary), var(--logo-secondary));
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 1.6rem;
                font-weight: bold;
                color: white;
                box-shadow: 
                    0 4px 20px rgba(16, 163, 127, 0.5),
                    0 0 0 2px rgba(25, 195, 125, 0.4),
                    inset 0 2px 10px rgba(255, 255, 255, 0.3);
                position: relative;
                overflow: hidden;
                transition: all 0.3s ease;
            }
            
            .logo-icon::before {
                content: '';
                position: absolute;
                top: -50%;
                left: -50%;
                width: 200%;
                height: 200%;
                background: linear-gradient(
                    45deg,
                    transparent,
                    rgba(255, 255, 255, 0.15),
                    transparent
                );
                transform: rotate(45deg);
                animation: logoShine 3s infinite;
            }
            
            .logo-icon:hover {
                transform: scale(1.05);
                box-shadow: 
                    0 6px 25px rgba(16, 163, 127, 0.7),
                    0 0 0 3px rgba(25, 195, 125, 0.5),
                    inset 0 2px 15px rgba(255, 255, 255, 0.4);
            }
            
            @keyframes logoShine {
                0% { transform: translateX(-100%) translateY(-100%) rotate(45deg); }
                50% { transform: translateX(100%) translateY(100%) rotate(45deg); }
                100% { transform: translateX(-100%) translateY(-100%) rotate(45deg); }
            }
            
            .logo-text {
                display: flex;
                flex-direction: column;
                line-height: 1.2;
            }
            
            .logo-main {
                font-size: 1.2rem;
                font-weight: 700;
                background: linear-gradient(135deg, var(--logo-primary), var(--logo-accent));
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            
            .logo-sub {
                font-size: 0.85rem;
                font-weight: 500;
                color: var(--text-secondary);
                opacity: 0.9;
            }
            
            .new-chat-btn {
                width: 100%;
                padding: 14px;
                margin: 16px 0;
                background: linear-gradient(135deg, var(--gradient-1), var(--gradient-2));
                border: none;
                border-radius: 10px;
                color: white;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 10px;
                transition: all 0.3s ease;
                font-weight: 600;
                box-shadow: 0 4px 15px rgba(16, 163, 127, 0.3);
            }
            
            .new-chat-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(16, 163, 127, 0.4);
            }

            ##Cambiar por logos##
            
            .sidebar-footer {
                padding: 20px;
                border-top: 1px solid var(--border);
                font-size: 0.8rem;
                color: var(--text-secondary);
                background: rgba(0,0,0,0.2);
            }
            
            .status-indicator {
                display: flex;
                align-items: center;
                gap: 8px;
                margin-top: 8px;
            }
            
            .status-dot {
                width: 8px;
                height: 8px;
                background: #10B981;
                border-radius: 50%;
                animation: pulse 2s infinite;
            }
            
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
            
            .main-content {
                flex: 1;
                display: flex;
                flex-direction: column;
                background: var(--chat-bg);
                position: relative;
            }
            
            .chat-header {
                padding: 20px 30px;
                border-bottom: 1px solid var(--border);
                background: rgba(26, 27, 38, 0.8);
                backdrop-filter: blur(10px);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .header-left {
                display: flex;
                align-items: center;
                gap: 15px;
            }
            
            .header-logo {
                width: 60px;
                height: 60px;
                background: linear-gradient(135deg, var(--logo-primary), var(--logo-secondary));
                border-radius: 15px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 1.8rem;
                font-weight: bold;
                color: white;
                box-shadow: 
                    0 6px 25px rgba(16, 163, 127, 0.5),
                    0 0 0 3px rgba(25, 195, 125, 0.4),
                    inset 0 2px 15px rgba(255, 255, 255, 0.3);
                position: relative;
                overflow: hidden;
                transition: all 0.3s ease;
            }
            
            .header-logo::before {
                content: '';
                position: absolute;
                top: -50%;
                left: -50%;
                width: 200%;
                height: 200%;
                background: linear-gradient(
                    45deg,
                    transparent,
                    rgba(255, 255, 255, 0.15),
                    transparent
                );
                transform: rotate(45deg);
                animation: headerLogoShine 4s infinite;
            }
            
            .header-logo:hover {
                transform: scale(1.08);
                box-shadow: 
                    0 8px 30px rgba(16, 163, 127, 0.7),
                    0 0 0 4px rgba(25, 195, 125, 0.5),
                    inset 0 2px 20px rgba(255, 255, 255, 0.4);
            }
            
            @keyframes headerLogoShine {
                0% { transform: translateX(-150%) translateY(-150%) rotate(45deg); }
                50% { transform: translateX(150%) translateY(150%) rotate(45deg); }
                100% { transform: translateX(-150%) translateY(-150%) rotate(45deg); }
            }
            
            .header-titles h1 {
                font-size: 1.6rem;
                margin-bottom: 6px;
                background: linear-gradient(135deg, var(--text-primary), var(--logo-primary));
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                font-weight: 700;
            }
            
            .header-titles p {
                color: var(--text-secondary);
                font-size: 0.95rem;
            }
            
            .header-actions {
                display: flex;
                gap: 12px;
            }
            
            .header-btn {
                background: linear-gradient(135deg, var(--gradient-1), var(--gradient-2));
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 20px;
                font-size: 0.9rem;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 8px;
                transition: all 0.3s ease;
                font-weight: 600;
                box-shadow: 0 4px 15px rgba(16, 163, 127, 0.3);
            }
            
            .header-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(16, 163, 127, 0.4);
            }
            
            .header-btn.secondary {
                background: var(--card-bg);
                color: var(--text-primary);
                border: 1px solid var(--border);
            }
            
            .header-btn.secondary:hover {
                background: rgba(255,255,255,0.1);
            }
            
            .chat-container {
                flex: 1;
                overflow-y: auto;
                padding: 30px;
                max-width: 1200px;
                margin: 0 auto;
                width: 100%;
            }
            
            .message {
                display: flex;
                gap: 20px;
                padding: 28px 0;
                border-bottom: 1px solid var(--border);
                animation: messageSlide 0.4s ease-out;
            }
            
            @keyframes messageSlide {
                from {
                    opacity: 0;
                    transform: translateY(20px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            
            .message:last-child {
                border-bottom: none;
            }
            
            .avatar {
                width: 45px;
                height: 45px;
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 600;
                flex-shrink: 0;
                font-size: 1.3rem;
                transition: all 0.3s ease;
            }
            
            .user-avatar {
                background: linear-gradient(135deg, var(--gradient-1), var(--gradient-2));
                box-shadow: 0 4px 15px rgba(16, 163, 127, 0.3);
            }
            
            .bot-avatar {
                background: linear-gradient(135deg, var(--logo-primary), var(--logo-secondary));
                box-shadow: 
                    0 4px 20px rgba(16, 163, 127, 0.4),
                    0 0 0 2px rgba(25, 195, 125, 0.3);
                position: relative;
                overflow: hidden;
                color: white;
            }
            
            .bot-avatar::before {
                content: '';
                position: absolute;
                top: -50%;
                left: -50%;
                width: 200%;
                height: 200%;
                background: linear-gradient(
                    45deg,
                    transparent,
                    rgba(255, 255, 255, 0.1),
                    transparent
                );
                transform: rotate(45deg);
                animation: botAvatarShine 3s infinite;
            }
            
            @keyframes botAvatarShine {
                0% { transform: translateX(-100%) translateY(-100%) rotate(45deg); }
                50% { transform: translateX(100%) translateY(100%) rotate(45deg); }
                100% { transform: translateX(-100%) translateY(-100%) rotate(45deg); }
            }
            
            .message-content {
                flex: 1;
            }
            
            .message-header {
                display: flex;
                align-items: center;
                gap: 12px;
                margin-bottom: 12px;
            }
            
            .message-sender {
                font-weight: 600;
                font-size: 1rem;
            }
            
            .message-time {
                color: var(--text-secondary);
                font-size: 0.85rem;
            }
            
            .message-text {
                line-height: 1.7;
                white-space: pre-line;
                font-size: 1rem;
                margin-bottom: 15px;
            }
            
            .message-text strong {
                color: var(--text-primary);
                font-weight: 600;
            }
            
            /* Estilos para la tabla del catálogo */
            .catalogo-header {
                background: linear-gradient(135deg, rgba(16, 163, 127, 0.1), rgba(30, 64, 175, 0.1));
                padding: 20px;
                border-radius: 12px 12px 0 0;
                border: 1px solid var(--border);
                border-bottom: none;
            }
            
            .catalogo-header h3 {
                font-size: 1.3rem;
                margin-bottom: 5px;
                color: var(--text-primary);
            }
            
            .catalogo-header p {
                color: var(--text-secondary);
                font-size: 0.9rem;
            }
            
            .table-container {
                overflow-x: auto;
                border: 1px solid var(--border);
                border-radius: 0 0 12px 12px;
                background: var(--card-bg);
            }
            
            .catalogo-table {
                width: 100%;
                border-collapse: collapse;
                min-width: 800px;
            }
            
            .catalogo-table th {
                background: rgba(30, 64, 175, 0.2);
                padding: 15px 12px;
                text-align: left;
                font-weight: 600;
                font-size: 0.85rem;
                color: var(--text-primary);
                border-bottom: 2px solid var(--border);
            }
            
            .catalogo-table td {
                padding: 15px 12px;
                border-bottom: 1px solid var(--border);
                vertical-align: top;
            }
            
            .catalogo-table tr:last-child td {
                border-bottom: none;
            }
            
            .catalogo-table tr:hover {
                background: rgba(255, 255, 255, 0.03);
            }
            
            /* Columnas específicas */
            .col-modelo {
                width: 25%;
            }
            
            .col-precio {
                width: 12%;
            }
            
            .col-tipo {
                width: 15%;
            }
            
            .col-marca {
                width: 15%;
            }
            
            .col-serie {
                width: 18%;
            }
            
            .col-stock {
                width: 15%;
            }
            
            .modelo-info strong {
                display: block;
                margin-bottom: 5px;
                color: var(--text-primary);
            }
            
            .modelos-compatibles {
                font-size: 0.8rem;
                color: var(--text-secondary);
                line-height: 1.4;
            }
            
            .precio {
                font-weight: 700;
                color: var(--success);
                font-size: 1.1rem;
            }
            
            .badge-categoria {
                background: rgba(59, 130, 246, 0.2);
                color: var(--info);
                padding: 6px 12px;
                border-radius: 20px;
                font-size: 0.8rem;
                font-weight: 500;
                border: 1px solid rgba(59, 130, 246, 0.3);
            }
            
            .marca-nombre {
                font-weight: 600;
                color: var(--text-primary);
            }
            
            .numero-serie {
                background: rgba(107, 114, 128, 0.2);
                color: var(--text-secondary);
                padding: 6px 10px;
                border-radius: 6px;
                font-family: 'Courier New', monospace;
                font-size: 0.8rem;
                border: 1px solid var(--border);
            }
            
            .stock-info {
                padding: 6px 12px;
                border-radius: 20px;
                font-size: 0.8rem;
                font-weight: 600;
                text-align: center;
                display: inline-block;
            }
            
            .stock-alto {
                background: rgba(16, 185, 129, 0.2);
                color: var(--success);
                border: 1px solid rgba(16, 185, 129, 0.3);
            }
            
            .stock-medio {
                background: rgba(245, 158, 11, 0.2);
                color: var(--warning);
                border: 1px solid rgba(245, 158, 11, 0.3);
            }
            
            .stock-bajo {
                background: rgba(239, 68, 68, 0.2);
                color: var(--danger);
                border: 1px solid rgba(239, 68, 68, 0.3);
            }
            
            .catalogo-footer {
                margin-top: 20px;
                padding: 15px;
                background: rgba(255, 255, 255, 0.02);
                border-radius: 8px;
                border: 1px solid var(--border);
            }
            
            .leyenda-stock {
                display: flex;
                gap: 20px;
                margin-bottom: 10px;
                flex-wrap: wrap;
            }
            
            .leyenda-item {
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 0.8rem;
                color: var(--text-secondary);
            }
            
            .indicador-stock {
                width: 12px;
                height: 12px;
                border-radius: 50%;
                display: inline-block;
            }
            
            .nota-catalogo {
                font-size: 0.85rem;
                color: var(--text-secondary);
                margin-top: 10px;
            }
            
            .no-products {
                text-align: center;
                padding: 40px 20px;
                background: var(--card-bg);
                border-radius: 12px;
                border: 1px solid var(--border);
            }
            
            .no-products-icon {
                font-size: 3rem;
                margin-bottom: 15px;
                opacity: 0.5;
            }
            
            .no-products h3 {
                margin-bottom: 10px;
                color: var(--text-primary);
            }
            
            .no-products p {
                color: var(--text-secondary);
            }
            
            .input-container {
                padding: 25px 30px;
                border-top: 1px solid var(--border);
                max-width: 1200px;
                margin: 0 auto;
                width: 100%;
                background: rgba(26, 27, 38, 0.8);
                backdrop-filter: blur(10px);
            }
            
            .input-wrapper {
                position: relative;
                display: flex;
                align-items: flex-end;
                gap: 12px;
            }
            
            .chat-input {
                flex: 1;
                padding: 16px 20px;
                background: var(--card-bg);
                border: 1px solid var(--border);
                border-radius: 16px;
                color: var(--text-primary);
                font-size: 1rem;
                resize: none;
                max-height: 200px;
                min-height: 60px;
                line-height: 1.5;
                transition: all 0.3s ease;
            }
            
            .chat-input:focus {
                outline: none;
                border-color: var(--gradient-1);
                box-shadow: 0 0 0 3px rgba(16, 163, 127, 0.1);
            }
            
            .send-button {
                background: linear-gradient(135deg, var(--gradient-1), var(--gradient-2));
                border: none;
                border-radius: 12px;
                width: 48px;
                height: 48px;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                transition: all 0.3s ease;
                flex-shrink: 0;
                box-shadow: 0 4px 15px rgba(16, 163, 127, 0.3);
            }
            
            .send-button:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(16, 163, 127, 0.4);
            }
            
            .send-button:disabled {
                background: var(--border);
                cursor: not-allowed;
                transform: none;
                box-shadow: none;
            }
            
            .suggestions {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-top: 20px;
            }
            
            .suggestion {
                background: var(--card-bg);
                border: 1px solid var(--border);
                border-radius: 12px;
                padding: 12px 18px;
                font-size: 0.9rem;
                cursor: pointer;
                transition: all 0.3s ease;
                color: var(--text-secondary);
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            .suggestion:hover {
                background: linear-gradient(135deg, var(--gradient-1), var(--gradient-2));
                color: white;
                transform: translateY(-2px);
                box-shadow: 0 4px 15px rgba(16, 163, 127, 0.3);
            }
            
            .action-buttons {
                display: flex;
                gap: 10px;
                margin-top: 15px;
                flex-wrap: wrap;
            }
            
            .action-button {
                background: linear-gradient(135deg, var(--gradient-1), var(--gradient-2));
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px 18px;
                font-size: 0.9rem;
                cursor: pointer;
                display: inline-flex;
                align-items: center;
                gap: 8px;
                transition: all 0.3s ease;
                text-decoration: none;
            }
            
            .action-button:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 15px rgba(16, 163, 127, 0.4);
            }
            
            .action-button.secondary {
                background: var(--card-bg);
                color: var(--text-primary);
                border: 1px solid var(--border);
            }
            
            .action-button.secondary:hover {
                background: rgba(255,255,255,0.1);
            }
            
            .typing-indicator {
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 20px 0;
                color: var(--text-secondary);
                font-style: italic;
            }
            
            .typing-dot {
                width: 6px;
                height: 6px;
                background: var(--gradient-1);
                border-radius: 50%;
                animation: typing 1.4s infinite;
            }
            
            .typing-dot:nth-child(2) {
                animation-delay: 0.2s;
            }
            
            .typing-dot:nth-child(3) {
                animation-delay: 0.4s;
            }
            
            @keyframes typing {
                0%, 60%, 100% { transform: translateY(0); }
                30% { transform: translateY(-5px); }
            }
            
            /* Modal Styles */
            .modal-overlay {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.7);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 1000;
                opacity: 0;
                visibility: hidden;
                transition: all 0.3s ease;
            }
            
            .modal-overlay.active {
                opacity: 1;
                visibility: visible;
            }
            
            .modal {
                background: var(--card-bg);
                border-radius: 16px;
                border: 1px solid var(--border);
                width: 90%;
                max-width: 500px;
                max-height: 90vh;
                overflow-y: auto;
                transform: scale(0.9);
                opacity: 0;
                transition: all 0.3s ease;
            }
            
            .modal-overlay.active .modal {
                transform: scale(1);
                opacity: 1;
            }
            
            .modal-header {
                padding: 20px 24px;
                border-bottom: 1px solid var(--border);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .modal-header h2 {
                font-size: 1.3rem;
                color: var(--text-primary);
                font-weight: 600;
            }
            
            .close-modal {
                background: none;
                border: none;
                color: var(--text-secondary);
                font-size: 1.5rem;
                cursor: pointer;
                width: 32px;
                height: 32px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 6px;
                transition: all 0.3s ease;
            }
            
            .close-modal:hover {
                background: rgba(255,255,255,0.1);
                color: var(--text-primary);
            }
            
            .modal-body {
                padding: 24px;
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
            
            .form-input {
                width: 100%;
                padding: 12px 16px;
                background: var(--sidebar);
                border: 1px solid var(--border);
                border-radius: 8px;
                color: var(--text-primary);
                font-size: 0.95rem;
                transition: all 0.3s ease;
            }
            
            .form-input:focus {
                outline: none;
                border-color: var(--gradient-1);
                box-shadow: 0 0 0 3px rgba(16, 163, 127, 0.1);
            }
            
            .form-select {
                width: 100%;
                padding: 12px 16px;
                background: var(--sidebar);
                border: 1px solid var(--border);
                border-radius: 8px;
                color: var(--text-primary);
                font-size: 0.95rem;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            
            .form-select:focus {
                outline: none;
                border-color: var(--gradient-1);
                box-shadow: 0 0 0 3px rgba(16, 163, 127, 0.1);
            }
            
            .payment-info {
                background: rgba(16, 163, 127, 0.1);
                border: 1px solid rgba(16, 163, 127, 0.3);
                border-radius: 8px;
                padding: 16px;
                margin-top: 12px;
                text-align: center;
            }
            
            .payment-number {
                font-size: 1.2rem;
                font-weight: 700;
                color: var(--success);
                margin: 8px 0;
                font-family: 'Courier New', monospace;
            }
            
            .payment-instructions {
                font-size: 0.85rem;
                color: var(--text-secondary);
                margin-top: 8px;
            }
            
            .card-fields {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px;
                margin-top: 12px;
            }
            
            .submit-btn {
                width: 100%;
                padding: 14px;
                background: linear-gradient(135deg, var(--gradient-1), var(--gradient-2));
                border: none;
                border-radius: 10px;
                color: white;
                font-size: 1rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                margin-top: 10px;
                box-shadow: 0 4px 15px rgba(16, 163, 127, 0.3);
            }
            
            .submit-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(16, 163, 127, 0.4);
            }

            /* Estilos para la selección de productos */
            .productos-container {
                max-height: 400px;
                overflow-y: auto;
                margin: 20px 0;
                border: 1px solid var(--border);
                border-radius: 8px;
                padding: 15px;
                background: var(--sidebar);
            }
            
            .producto-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 12px;
                margin-bottom: 8px;
                background: var(--card-bg);
                border-radius: 6px;
                border: 1px solid var(--border);
                transition: all 0.3s ease;
            }
            
            .producto-item:hover {
                background: rgba(255,255,255,0.05);
                border-color: var(--gradient-1);
            }
            
            .producto-info {
                flex: 1;
            }
            
            .producto-nombre {
                font-weight: 600;
                margin-bottom: 4px;
            }
            
            .producto-detalles {
                font-size: 0.85rem;
                color: var(--text-secondary);
            }
            
            .producto-precio {
                font-weight: 700;
                color: var(--success);
                margin-right: 15px;
            }
            
            .agregar-producto {
                background: var(--gradient-1);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                cursor: pointer;
                font-size: 0.85rem;
                transition: all 0.3s ease;
            }
            
            .agregar-producto:hover {
                background: var(--gradient-2);
                transform: translateY(-2px);
            }
            
            .carrito-container {
                margin: 20px 0;
                border: 1px solid var(--border);
                border-radius: 8px;
                padding: 15px;
                background: var(--sidebar);
            }
            
            .carrito-header {
                font-weight: 600;
                margin-bottom: 15px;
                color: var(--text-primary);
            }
            
            .carrito-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 10px;
                margin-bottom: 8px;
                background: var(--card-bg);
                border-radius: 6px;
                border: 1px solid var(--border);
            }
            
            .carrito-info {
                flex: 1;
            }
            
            .carrito-cantidad {
                display: flex;
                align-items: center;
                gap: 10px;
                margin-right: 15px;
            }
            
            .cantidad-btn {
                background: var(--border);
                border: none;
                border-radius: 4px;
                width: 24px;
                height: 24px;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                font-size: 0.8rem;
            }
            
            .eliminar-producto {
                background: var(--danger);
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 10px;
                cursor: pointer;
                font-size: 0.8rem;
            }
            
            .resumen-pago {
                background: rgba(16, 163, 127, 0.1);
                border: 1px solid rgba(16, 163, 127, 0.3);
                border-radius: 8px;
                padding: 15px;
                margin: 20px 0;
            }
            
            .resumen-linea {
                display: flex;
                justify-content: space-between;
                margin-bottom: 8px;
            }
            
            .resumen-total {
                font-weight: 700;
                font-size: 1.1rem;
                border-top: 1px solid var(--border);
                padding-top: 8px;
                margin-top: 8px;
            }
            
            .etapa-pago {
                display: none;
            }
            
            .etapa-pago.active {
                display: block;
            }
            
            /* Scrollbar personalizado */
            .chat-container::-webkit-scrollbar {
                width: 8px;
            }
            
            .chat-container::-webkit-scrollbar-track {
                background: transparent;
            }
            
            .chat-container::-webkit-scrollbar-thumb {
                background: var(--border);
                border-radius: 4px;
            }
            
            .chat-container::-webkit-scrollbar-thumb:hover {
                background: var(--gradient-1);
            }
            
            @media (max-width: 768px) {
                .sidebar {
                    display: none;
                }
                
                .chat-container, .input-container {
                    padding: 20px;
                }
                
                .chat-header {
                    padding: 15px 20px;
                    flex-direction: column;
                    gap: 15px;
                    align-items: flex-start;
                }
                
                .header-left {
                    flex-direction: column;
                    align-items: flex-start;
                    gap: 10px;
                }
                
                .header-actions {
                    width: 100%;
                    justify-content: space-between;
                }
                
                .header-btn {
                    flex: 1;
                    justify-content: center;
                }
                
                .message {
                    padding: 20px 0;
                }
                
                .catalogo-table {
                    min-width: 600px;
                }
                
                .leyenda-stock {
                    flex-direction: column;
                    gap: 10px;
                }
                
                .modal {
                    width: 95%;
                    margin: 20px;
                }
                
                .card-fields {
                    grid-template-columns: 1fr;
                }
            }
        </style>
    </head>
    <body>
        <div class="app-container">
            <div class="sidebar">
                <div class="sidebar-header">
                    <div class="logo">
                        <div class="logo-icon">V</div>
                        <div class="logo-text">
                            <div class="logo-main">Autopartes</div>
                            <div class="logo-sub">Verese Sac</div>
                        </div>
                    </div>
                    <button class="new-chat-btn" onclick="nuevoChat()">
                        <span>+</span> Nuevo chat
                    </button>
                </div>
                
                <div class="sidebar-footer">
                    <div>Autopartes - Verese Sac AI</div>
                    <div class="status-indicator">
                        <div class="status-dot"></div>
                        <span>En línea - Listo para ayudar</span>
                    </div>
                    <div style="margin-top: 8px; font-size: 0.75rem; opacity: 0.7;">
                        Catálogo con 15+ productos en tabla
                    </div>
                </div>
            </div>
            
            <div class="main-content">
                <div class="chat-header">
                    <div class="header-left">
                        <div class="header-logo">V</div>
                        <div class="header-titles">
                            <h1>Autopartes - Verese Sac AI</h1>
                            <p>Catálogo completo en formato de tabla - Precios, modelos y disponibilidad</p>
                        </div>
                    </div>
                    <div class="header-actions">
                        <button class="header-btn secondary" onclick="mostrarModalSeparar()">
                            📦 Separar Pieza
                        </button>
                        <button class="header-btn" onclick="mostrarModalPago()">
                            💰 Realizar Pago
                        </button>
                        
                    </div>
                </div>
                
                <div class="chat-container" id="chat-container">
                    <div class="message">
                        <div class="avatar bot-avatar">V</div>
                        <div class="message-content">
                            <div class="message-header">
                                <div class="message-sender">Autopartes - Verese Sac AI</div>
                                <div class="message-time" id="current-time"></div>
                            </div>
                            <div class="message-text">
                                ¡Hola! Soy tu asistente virtual de **Autopartes - Verese Sac**. Ahora puedes consultar nuestro catálogo completo en un formato de tabla organizado con toda la información que necesitas.

**En nuestra tabla encontrarás:**
• 🚗 **Modelos compatibles** con cada autoparte
• 💰 **Precios** actualizados en soles
• 🔧 **Tipo de pieza** y categoría
• 🏷️ **Marca** del producto
• 🔢 **Número de serie** único
• 📊 **Stock disponible** con indicadores de color

**¿Qué te gustaría consultar?**
                            </div>
                            <div class="suggestions">
                                <div class="suggestion" onclick="hacerPregunta('Ver catálogo completo')">📊 Catálogo completo</div>
                                <div class="suggestion" onclick="hacerPregunta('Sistema de frenos')">🛑 Frenos en tabla</div>
                                <div class="suggestion" onclick="hacerPregunta('Motor')">🔧 Motor en tabla</div>
                                <div class="suggestion" onclick="hacerPregunta('Métodos de pago')">💳 Métodos de pago</div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="typing-indicator" id="typing-indicator" style="display: none;">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <span>Generando tabla del catálogo...</span>
                </div>
                
                <div class="input-container">
                    <div class="input-wrapper">
                        <textarea class="chat-input" id="user-input" placeholder="Ej: Mostrar tabla de productos de frenos..." rows="1"></textarea>
                        <button class="send-button" id="send-btn">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M22 2L11 13" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                                <path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                            </svg>
                        </button>
                    </div>
                    <div class="suggestions">
                        <div class="suggestion" onclick="hacerPregunta('Ver catálogo completo')">📊 Tabla completa</div>
                        <div class="suggestion" onclick="hacerPregunta('Sistema de frenos')">🛑 Tabla frenos</div>
                        <div class="suggestion" onclick="hacerPregunta('Motor')">🔧 Tabla motor</div>
                        <div class="suggestion" onclick="hacerPregunta('Métodos de pago')">💳 Métodos de pago</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Modal para Realizar Pago -->
        <div class="modal-overlay" id="pagoModal">
            <div class="modal">
                <div class="modal-header">
                    <h2>💰 Realizar Pago</h2>
                    <button class="close-modal" onclick="cerrarModalPago()">×</button>
                </div>
                <div class="modal-body">
                    <div class="etapa-pago active" id="etapaDatos">
                        <form id="pagoForm">
                            <div class="form-group">
                                <label class="form-label">Nombre Completo</label>
                                <input type="text" class="form-input" id="nombreCompleto" placeholder="Ingrese su nombre completo" required>
                            </div>
                            
                            <div class="form-group">
                                <label class="form-label">Correo Electrónico</label>
                                <input type="email" class="form-input" id="correoElectronico" placeholder="Ingrese su correo electrónico" required>
                            </div>
                            
                            <div class="form-group">
                                <label class="form-label">Teléfono de Contacto</label>
                                <input type="tel" class="form-input" id="telefonoContacto" placeholder="Ingrese su teléfono" required>
                            </div>
                            
                            <div class="form-group">
                                <label class="form-label">Dirección de Entrega</label>
                                <input type="text" class="form-input" id="direccionEntrega" placeholder="Ingrese su dirección completa" required>
                            </div>
                            
                            <div class="form-group">
                                <label class="form-label">Método de Pago</label>
                                <select class="form-select" id="metodoPago" onchange="cambiarMetodoPago()" required>
                                    <option value="">Seleccione método de pago</option>
                                    <option value="yape">Yape</option>
                                    <option value="plin">Plin</option>
                                    <option value="tarjeta">Tarjeta de Crédito/Débito</option>
                                    <option value="transferencia">Transferencia Bancaria</option>
                                </select>
                            </div>
                            
                            <div id="infoPago">
                                <!-- Aquí se mostrará la información específica del método de pago -->
                            </div>
                            
                            <button type="button" class="submit-btn" onclick="confirmarDatos()">Confirmar Datos</button>
                        </form>
                    </div>
                    
                    <div class="etapa-pago" id="etapaProductos">
                        <h3 style="margin-bottom: 20px;">🛒 Selecciona los Productos</h3>
                        
                        <div class="productos-container" id="listaProductos">
                            <!-- Los productos se cargarán aquí -->
                        </div>
                        
                        <div class="carrito-container">
                            <div class="carrito-header">📋 Productos Seleccionados</div>
                            <div id="carritoProductos">
                                <!-- Los productos seleccionados se mostrarán aquí -->
                                <div style="text-align: center; color: var(--text-secondary); padding: 20px;">
                                    No hay productos seleccionados
                                </div>
                            </div>
                        </div>
                        
                        <div class="resumen-pago" id="resumenPago">
                            <div class="resumen-linea">
                                <span>Subtotal:</span>
                                <span>S/ 0.00</span>
                            </div>
                            <div class="resumen-linea">
                                <span>IGV (18%):</span>
                                <span>S/ 0.00</span>
                            </div>
                            <div class="resumen-linea resumen-total">
                                <span>Total a Pagar:</span>
                                <span>S/ 0.00</span>
                            </div>
                        </div>
                        
                        <div style="display: flex; gap: 10px; margin-top: 20px;">
                            <button class="submit-btn" style="flex: 1; background: var(--card-bg); color: var(--text-primary);" onclick="volverADatos()">
                                ← Volver
                            </button>
                            <button class="submit-btn" style="flex: 2;" id="btnConfirmarCompra" onclick="confirmarCompra()" disabled>
                                Confirmar Compra
                            </button>
                        </div>
                    </div>
                    
                    <div class="etapa-pago" id="etapaConfirmacion">
                        <div style="text-align: center; padding: 40px 20px;">
                            <div style="font-size: 4rem; margin-bottom: 20px;">🎉</div>
                            <h3 style="margin-bottom: 15px; color: var(--success);">¡Compra Exitosa!</h3>
                            <p style="color: var(--text-secondary); margin-bottom: 25px; line-height: 1.6;">
                                Tu compra ha sido exitosa. Dentro de unos días un encargado te hará entrega de los productos.<br>
                                <strong>¡Gracias por preferirnos! ¡Hasta Luego!</strong>
                            </p>
                            <button class="submit-btn" onclick="cerrarModalPago()">
                                Cerrar
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Modal para Separar Pieza -->
        <div class="modal-overlay" id="separarModal">
            <div class="modal">
                <div class="modal-header">
                    <h2>📦 Separar Pieza</h2>
                    <button class="close-modal" onclick="cerrarModalSeparar()">×</button>
                </div>
                <div class="modal-body">
                    <p>Para separar una pieza, por favor contacta directamente con nuestro equipo de ventas:</p>
                    <div style="text-align: center; margin: 20px 0;">
                        <div style="font-size: 1.2rem; font-weight: 700; color: var(--success); margin: 10px 0;">📞 (01) 6200 158</div>
                        <div style="font-size: 1rem; color: var(--text-secondary); margin: 10px 0;">📱 +51 987 654 321</div>
                        <div style="font-size: 0.9rem; color: var(--text-secondary);">✉️ ventas@autopartesvirtual.com</div>
                    </div>
                    <p style="text-align: center; color: var(--text-secondary); font-size: 0.9rem;">
                        Nuestro equipo te ayudará a verificar disponibilidad y realizar la separación de tu pieza.
                    </p>
                </div>
            </div>
        </div>

        <script>
            const chatContainer = document.getElementById('chat-container');
            const userInput = document.getElementById('user-input');
            const sendBtn = document.getElementById('send-btn');
            const typingIndicator = document.getElementById('typing-indicator');
            const pagoModal = document.getElementById('pagoModal');
            const separarModal = document.getElementById('separarModal');
            const infoPago = document.getElementById('infoPago');
            
            // Variables para el carrito de compras
            let carrito = [];
            let datosCliente = {};
            
            // Actualizar hora actual
            function actualizarHora() {
                const now = new Date();
                document.getElementById('current-time').textContent = now.toLocaleTimeString('es-ES', { 
                    hour: '2-digit', 
                    minute: '2-digit' 
                });
            }
            setInterval(actualizarHora, 60000);
            actualizarHora();
            
            // Autoajustar altura del textarea
            userInput.addEventListener('input', function() {
                this.style.height = 'auto';
                this.style.height = Math.min(this.scrollHeight, 200) + 'px';
            });
            
            // Mostrar mensaje del usuario
            function mostrarMensajeUsuario(mensaje) {
                const messageDiv = document.createElement('div');
                messageDiv.className = 'message';
                
                messageDiv.innerHTML = `
                    <div class="avatar user-avatar">TÚ</div>
                    <div class="message-content">
                        <div class="message-header">
                            <div class="message-sender">Tú</div>
                            <div class="message-time">${new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}</div>
                        </div>
                        <div class="message-text">${mensaje}</div>
                    </div>
                `;
                
                chatContainer.appendChild(messageDiv);
                scrollToBottom();
            }
            
            // Mostrar mensaje del bot
            function mostrarMensajeBot(titulo, contenido, icono = '🤖', color = '#10a37f', tipo = 'normal', tabla = null) {
                const messageDiv = document.createElement('div');
                messageDiv.className = 'message';
                
                let contenidoFormateado = contenido.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                contenidoFormateado = contenidoFormateado.replace(/\\n/g, '<br>');
                
                messageDiv.innerHTML = `
                    <div class="avatar bot-avatar" style="background: linear-gradient(135deg, ${color}, ${color}99)">V</div>
                    <div class="message-content">
                        <div class="message-header">
                            <div class="message-sender">Autopartes - Verese Sac AI</div>
                            <div class="message-time">${new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}</div>
                        </div>
                        <div class="message-text">${contenidoFormateado}</div>
                    </div>
                `;
                
                chatContainer.appendChild(messageDiv);
                
                // Si hay tabla, agregarla al mensaje
                if (tabla && tabla.html) {
                    const tablaContainer = document.createElement('div');
                    tablaContainer.className = 'catalogo-tabla-container';
                    tablaContainer.innerHTML = tabla.html;
                    messageDiv.querySelector('.message-content').appendChild(tablaContainer);
                }
                
                // Botones de acción según el tipo de mensaje
                const actionContainer = document.createElement('div');
                actionContainer.className = 'action-buttons';
                
                if (tipo === 'catalogo_tabla') {
                    actionContainer.innerHTML = `
                        <button class="action-button" onclick="hacerPregunta('Solicitar cotización')">
                            💰 Solicitar cotización
                        </button>
                        <button class="action-button secondary" onclick="hacerPregunta('Contacto')">
                            📞 Contactar por producto
                        </button>
                        <button class="action-button secondary" onclick="hacerPregunta('Ubicación')">
                            📍 Ver sucursales
                        </button>
                    `;
                    messageDiv.querySelector('.message-content').appendChild(actionContainer);
                }
                
                if (titulo.includes('Ubicación')) {
                    actionContainer.innerHTML = `
                        <button class="action-button" onclick="window.open('https://www.google.com/maps/place/San+Juan+de+Lurigancho,+Lima+15401', '_blank')">
                            🗺️ Ver en Google Maps
                        </button>
                        <button class="action-button secondary" onclick="hacerPregunta('Horario de atención')">
                            🕒 Ver horarios
                        </button>
                    `;
                    messageDiv.querySelector('.message-content').appendChild(actionContainer);
                }
                
                if (titulo.includes('Contacto')) {
                    actionContainer.innerHTML = `
                        <button class="action-button" onclick="window.open('tel:+51014567890')">
                            📞 Llamar ahora
                        </button>
                        <button class="action-button" onclick="window.open('https://wa.me/51987654321')">
                            📱 WhatsApp
                        </button>
                        <button class="action-button secondary" onclick="window.location.href='mailto:ventas@autopartesvirtual.com'">
                            ✉️ Enviar email
                        </button>
                    `;
                    messageDiv.querySelector('.message-content').appendChild(actionContainer);
                }
                
                scrollToBottom();
            }
            
            // Funciones para modales
            function mostrarModalPago() {
                pagoModal.classList.add('active');
                document.body.style.overflow = 'hidden';
                // Resetear el modal a la primera etapa
                cambiarEtapaPago('etapaDatos');
                carrito = [];
                actualizarCarrito();
            }
            
            function cerrarModalPago() {
                pagoModal.classList.remove('active');
                document.body.style.overflow = 'auto';
            }
            
            function mostrarModalSeparar() {
                separarModal.classList.add('active');
                document.body.style.overflow = 'hidden';
            }
            
            function cerrarModalSeparar() {
                separarModal.classList.remove('active');
                document.body.style.overflow = 'auto';
            }
            
            // Cambiar entre etapas del pago
            function cambiarEtapaPago(etapa) {
                document.querySelectorAll('.etapa-pago').forEach(etapa => {
                    etapa.classList.remove('active');
                });
                document.getElementById(etapa).classList.add('active');
            }
            
            // Confirmar datos del cliente
            function confirmarDatos() {
                const nombre = document.getElementById('nombreCompleto').value;
                const correo = document.getElementById('correoElectronico').value;
                const telefono = document.getElementById('telefonoContacto').value;
                const direccion = document.getElementById('direccionEntrega').value;
                const metodoPago = document.getElementById('metodoPago').value;
                
                if (!nombre || !correo || !telefono || !direccion || !metodoPago) {
                    alert('Por favor, complete todos los campos obligatorios.');
                    return;
                }
                
                // Guardar datos del cliente
                datosCliente = {
                    nombre: nombre,
                    correo: correo,
                    telefono: telefono,
                    direccion: direccion,
                    metodoPago: metodoPago
                };
                
                // Cargar productos y pasar a la siguiente etapa
                cargarProductos();
                cambiarEtapaPago('etapaProductos');
            }
            
            function volverADatos() {
                cambiarEtapaPago('etapaDatos');
            }
            
            // Cargar productos disponibles
            function cargarProductos() {
                fetch('/api/productos')
                    .then(response => response.json())
                    .then(productos => {
                        const listaProductos = document.getElementById('listaProductos');
                        listaProductos.innerHTML = '';
                        
                        productos.forEach(producto => {
                            const productoItem = document.createElement('div');
                            productoItem.className = 'producto-item';
                            productoItem.innerHTML = `
                                <div class="producto-info">
                                    <div class="producto-nombre">${producto.nombre}</div>
                                    <div class="producto-detalles">
                                        ${producto.marca} • ${producto.categoria} • Stock: ${producto.stock}
                                    </div>
                                </div>
                                <div class="producto-precio">S/ ${producto.precio.toFixed(2)}</div>
                                <button class="agregar-producto" onclick="agregarAlCarrito('${producto.id}', '${producto.nombre}', ${producto.precio}, ${producto.stock})">
                                    Agregar
                                </button>
                            `;
                            listaProductos.appendChild(productoItem);
                        });
                    })
                    .catch(error => {
                        console.error('Error al cargar productos:', error);
                        document.getElementById('listaProductos').innerHTML = '<div style="text-align: center; color: var(--text-secondary); padding: 20px;">Error al cargar productos</div>';
                    });
            }
            
            // Funciones del carrito
            function agregarAlCarrito(id, nombre, precio, stock) {
                // Verificar si el producto ya está en el carrito
                const productoExistente = carrito.find(item => item.id === id);
                
                if (productoExistente) {
                    if (productoExistente.cantidad < stock) {
                        productoExistente.cantidad++;
                    } else {
                        alert('No hay suficiente stock disponible');
                        return;
                    }
                } else {
                    if (stock > 0) {
                        carrito.push({
                            id: id,
                            nombre: nombre,
                            precio: precio,
                            cantidad: 1,
                            stock: stock
                        });
                    } else {
                        alert('Producto sin stock disponible');
                        return;
                    }
                }
                
                actualizarCarrito();
            }
            
            function actualizarCarrito() {
                const carritoProductos = document.getElementById('carritoProductos');
                const btnConfirmarCompra = document.getElementById('btnConfirmarCompra');
                
                if (carrito.length === 0) {
                    carritoProductos.innerHTML = '<div style="text-align: center; color: var(--text-secondary); padding: 20px;">No hay productos seleccionados</div>';
                    btnConfirmarCompra.disabled = true;
                } else {
                    carritoProductos.innerHTML = '';
                    carrito.forEach((producto, index) => {
                        const carritoItem = document.createElement('div');
                        carritoItem.className = 'carrito-item';
                        carritoItem.innerHTML = `
                            <div class="carrito-info">
                                <div style="font-weight: 600;">${producto.nombre}</div>
                                <div style="font-size: 0.85rem; color: var(--text-secondary);">
                                    S/ ${producto.precio.toFixed(2)} c/u
                                </div>
                            </div>
                            <div class="carrito-cantidad">
                                <button class="cantidad-btn" onclick="cambiarCantidad(${index}, -1)">-</button>
                                <span>${producto.cantidad}</span>
                                <button class="cantidad-btn" onclick="cambiarCantidad(${index}, 1)">+</button>
                            </div>
                            <button class="eliminar-producto" onclick="eliminarDelCarrito(${index})">
                                Eliminar
                            </button>
                        `;
                        carritoProductos.appendChild(carritoItem);
                    });
                    btnConfirmarCompra.disabled = false;
                }
                
                actualizarResumenPago();
            }
            
            function cambiarCantidad(index, cambio) {
                const producto = carrito[index];
                const nuevaCantidad = producto.cantidad + cambio;
                
                if (nuevaCantidad <= 0) {
                    eliminarDelCarrito(index);
                } else if (nuevaCantidad > producto.stock) {
                    alert('No hay suficiente stock disponible');
                } else {
                    producto.cantidad = nuevaCantidad;
                    actualizarCarrito();
                }
            }
            
            function eliminarDelCarrito(index) {
                carrito.splice(index, 1);
                actualizarCarrito();
            }
            
            function actualizarResumenPago() {
                const subtotal = carrito.reduce((total, producto) => total + (producto.precio * producto.cantidad), 0);
                const igv = subtotal * 0.18;
                const total = subtotal + igv;
                
                const resumenPago = document.getElementById('resumenPago');
                resumenPago.innerHTML = `
                    <div class="resumen-linea">
                        <span>Subtotal:</span>
                        <span>S/ ${subtotal.toFixed(2)}</span>
                    </div>
                    <div class="resumen-linea">
                        <span>IGV (18%):</span>
                        <span>S/ ${igv.toFixed(2)}</span>
                    </div>
                    <div class="resumen-linea resumen-total">
                        <span>Total a Pagar:</span>
                        <span>S/ ${total.toFixed(2)}</span>
                    </div>
                `;
            }
            
            // Confirmar compra final
            function confirmarCompra() {
                if (carrito.length === 0) {
                    alert('Por favor, selecciona al menos un producto.');
                    return;
                }
                
                const compraData = {
                    usuario: {
                        nombre: datosCliente.nombre,
                        correo: datosCliente.correo,
                        telefono: datosCliente.telefono,
                        direccion: datosCliente.direccion
                    },
                    productos: carrito,
                    metodo_pago: datosCliente.metodoPago,
                    direccion_entrega: datosCliente.direccion,
                    telefono_contacto: datosCliente.telefono
                };
                
                // Enviar la compra al servidor
                fetch('/api/crear_compra', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(compraData)
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Mostrar confirmación exitosa
                        cambiarEtapaPago('etapaConfirmacion');
                    } else {
                        alert('Error al procesar la compra: ' + data.error);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Error al procesar la compra');
                });
            }
            
            // Cambiar información de pago según método seleccionado
            function cambiarMetodoPago() {
                const metodo = document.getElementById('metodoPago').value;
                let html = '';
                
                if (metodo === 'yape' || metodo === 'plin') {
                    const nombreMetodo = metodo === 'yape' ? 'Yape' : 'Plin';
                    html = `
                        <div class="payment-info">
                            <div style="font-weight: 600; color: var(--text-primary);">${nombreMetodo}</div>
                            <div class="payment-number">+51 978 462 485</div>
                            <div class="payment-instructions">
                                Realiza el pago a este número y envía el comprobante a nuestro WhatsApp
                            </div>
                        </div>
                    `;
                } else if (metodo === 'tarjeta') {
                    html = `
                        <div class="card-fields">
                            <div class="form-group">
                                <label class="form-label">Número de Tarjeta</label>
                                <input type="text" class="form-input" placeholder="1234 5678 9012 3456" required maxlength="19">
                            </div>
                            <div class="form-group">
                                <label class="form-label">CVV</label>
                                <input type="password" class="form-input" placeholder="***" required maxlength="3">
                            </div>
                            <div class="form-group">
                                <label class="form-label">Fecha de Caducidad</label>
                                <input type="text" class="form-input" placeholder="MM/AA" required maxlength="5">
                            </div>
                            <div class="form-group">
                                <label class="form-label">Nombre del Titular</label>
                                <input type="text" class="form-input" placeholder="Como aparece en la tarjeta" required>
                            </div>
                        </div>
                    `;
                } else if (metodo === 'transferencia') {
                    html = `
                        <div class="payment-info">
                            <div style="font-weight: 600; color: var(--text-primary);">Transferencia Bancaria</div>
                            <div class="payment-number">1558 - 1749667 - 26560</div>
                            <div class="payment-instructions">
                                Banco: BCP<br>
                                Titular: Autopartes Verese Sac<br>
                                Envía el comprobante a nuestro WhatsApp
                            </div>
                        </div>
                    `;
                }
                
                infoPago.innerHTML = html;
            }
            
            // Cerrar modales al hacer clic fuera
            pagoModal.addEventListener('click', function(e) {
                if (e.target === pagoModal) {
                    cerrarModalPago();
                }
            });
            
            separarModal.addEventListener('click', function(e) {
                if (e.target === separarModal) {
                    cerrarModalSeparar();
                }
            });
            
            // Hacer pregunta desde botones
            function hacerPregunta(pregunta) {
                mostrarMensajeUsuario(pregunta);
                
                // Mostrar indicador de typing
                typingIndicator.style.display = 'flex';
                scrollToBottom();
                
                // Simular delay de respuesta
                setTimeout(() => {
                    typingIndicator.style.display = 'none';
                    
                    fetch('/preguntar', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({pregunta: pregunta})
                    })
                    .then(response => {
                        if (!response.ok) {
                            throw new Error('Error en la respuesta del servidor');
                        }
                        return response.json();
                    })
                    .then(data => {
                        mostrarMensajeBot(data.titulo, data.contenido, data.icono || '🤖', data.color || '#10a37f', data.tipo || 'normal', data.tabla || null);
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        mostrarMensajeBot('Error', 'Lo siento, hubo un error procesando tu mensaje. Intenta de nuevo.', '❌', '#EF4444');
                    });
                }, 1000 + Math.random() * 1000);
            }
            
            // Nuevo chat
            function nuevoChat() {
                if (confirm('¿Comenzar un nuevo chat? Se perderá el historial actual.')) {
                    chatContainer.innerHTML = `
                        <div class="message">
                            <div class="avatar bot-avatar">V</div>
                            <div class="message-content">
                                <div class="message-header">
                                    <div class="message-sender">Autopartes - Verese Sac AI</div>
                                    <div class="message-time" id="current-time"></div>
                                </div>
                                <div class="message-text">
                                    ¡Hola! Soy tu asistente virtual de **Autopartes - Verese Sac**. ¿En qué puedo ayudarte hoy?
                                </div>
                                <div class="suggestions">
                                    <div class="suggestion" onclick="hacerPregunta('Ver catálogo completo')">📊 Tabla completa</div>
                                    <div class="suggestion" onclick="hacerPregunta('Sistema de frenos')">🛑 Tabla frenos</div>
                                    <div class="suggestion" onclick="hacerPregunta('Motor')">🔧 Tabla motor</div>
                                    <div class="suggestion" onclick="hacerPregunta('Métodos de pago')">💳 Métodos de pago</div>
                                </div>
                            </div>
                        </div>
                    `;
                    actualizarHora();
                }
            }
            
            // Enviar mensaje
            function enviarMensaje() {
                const mensaje = userInput.value.trim();
                if (!mensaje) return;
                
                mostrarMensajeUsuario(mensaje);
                userInput.value = '';
                userInput.style.height = 'auto';
                
                // Mostrar indicador de typing
                typingIndicator.style.display = 'flex';
                scrollToBottom();
                
                // Simular delay de respuesta
                setTimeout(() => {
                    typingIndicator.style.display = 'none';
                    
                    fetch('/preguntar', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({pregunta: mensaje})
                    })
                    .then(response => {
                        if (!response.ok) {
                            throw new Error('Error en la respuesta del servidor');
                        }
                        return response.json();
                    })
                    .then(data => {
                        mostrarMensajeBot(data.titulo, data.contenido, data.icono || '🤖', data.color || '#10a37f', data.tipo || 'normal', data.tabla || null);
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        mostrarMensajeBot('Error', 'Lo siento, hubo un error procesando tu mensaje. Intenta de nuevo.', '❌', '#EF4444');
                    });
                }, 1000 + Math.random() * 1000);
            }
            
            // Scroll al final del chat
            function scrollToBottom() {
                setTimeout(() => {
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                }, 100);
            }
            
            // Event listeners
            sendBtn.addEventListener('click', enviarMensaje);
            
            userInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    enviarMensaje();
                }
            });
            
            // Focus en el input al cargar
            userInput.focus();
            
            // Scroll inicial al final
            scrollToBottom();
        </script>
    </body>
    </html>
    '''

@app.route('/preguntar', methods=['POST'])
def preguntar():
    try:
        data = request.get_json()
        if not data or 'pregunta' not in data:
            return jsonify({'titulo': 'Error', 'contenido': 'No se recibió ningún mensaje', 'icono': '❌', 'color': '#EF4444'})
        
        pregunta = data.get('pregunta', '')
        respuesta = chatbot.procesar_pregunta(pregunta)
        
        return jsonify(respuesta)
    except Exception as e:
        return jsonify({'titulo': 'Error', 'contenido': f'Error del servidor: {str(e)}', 'icono': '❌', 'color': '#EF4444'})

# Nuevos endpoints para la base de datos
@app.route('/api/productos')
def api_productos():
    """Endpoint para obtener productos"""
    categoria = request.args.get('categoria')
    marca = request.args.get('marca')
    modelo = request.args.get('modelo')
    
    productos = obtener_productos(categoria, marca, modelo)
    return jsonify(productos)

@app.route('/api/crear_compra', methods=['POST'])
def api_crear_compra():
    """Endpoint para crear una compra"""
    try:
        data = request.get_json()
        
        # Crear usuario si no existe
        usuario_id = crear_usuario(
            data['usuario']['nombre'],
            data['usuario']['correo'],
            data['usuario'].get('telefono'),
            data['usuario'].get('direccion')
        )
        
        if not usuario_id:
            return jsonify({
                'success': False,
                'error': 'Error al crear usuario'
            }), 400
        
        # Crear compra
        compra_id = crear_compra(
            usuario_id,
            data['productos'],
            data['metodo_pago'],
            data['direccion_entrega'],
            data['telefono_contacto']
        )
        
        return jsonify({
            'success': True,
            'compra_id': compra_id,
            'mensaje': 'Compra creada exitosamente'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/registrar_pago', methods=['POST'])
def api_registrar_pago():
    """Endpoint para registrar un pago"""
    try:
        data = request.get_json()
        
        registrar_pago(
            data['compra_id'],
            data['metodo_pago'],
            data['monto'],
            data.get('datos_pago')
        )
        
        return jsonify({
            'success': True,
            'mensaje': 'Pago registrado exitosamente'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@app.route('/abrir_mapa')
def abrir_mapa():
    webbrowser.open('https://www.google.com/maps/place/San+Juan+de+Lurigancho,+Lima+15401')
    return jsonify({'status': 'mapa_abierto'})

def abrir_navegador():
    """Abre el navegador automáticamente cuando el servidor esté listo"""
    import time
    time.sleep(2)
    webbrowser.open('http://127.0.0.1:5000')

if __name__ == '__main__':
    print("🚗 Iniciando Autopartes - Verese Sac AI...")
    print("🔐 Sistema de autenticación implementado")
    print("🛒 Carrito de compras con selección de productos")
    print("💰 Cálculo automático de IGV y totales")
    print("🗃️  Base de datos SQLite integrada y funcionando")
    print("📊 Dashboard administrativo disponible en /admin/login")
    print("🔧 Usuarios admin: Pedro_48, Abad_48, Sergio_48, Olivera_48")
    print("💬 La aplicación estará disponible en: http://127.0.0.1:5000")
    print("⏹️  Presiona Ctrl+C para detener el servidor")
    
    # Abre el navegador automáticamente
    threading.Thread(target=abrir_navegador, daemon=True).start()

    app.run(debug=True, use_reloader=False)




