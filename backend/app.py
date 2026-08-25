import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Cargar variables del archivo .env
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuracion de la base de datos desde .env
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'BM_Almacenes'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', ''),
    'port': os.getenv('DB_PORT', '5432')
}

API_PORT = int(os.getenv('API_PORT', 5001))


def get_db_connection():
    """Crea y devuelve una conexion a PostgreSQL."""
    return psycopg2.connect(**DB_CONFIG)


@app.route('/')
def home():
    return jsonify({
        'mensaje': 'Bienvenido a BM Almacenes API',
        'version': '1.0'
    })


@app.route('/api/health')
def health():
    """Verifica que el servidor y la base de datos respondan."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        cursor.close()
        conn.close()
        return jsonify({
            'status': 'ok',
            'db': 'connected',
            'puerto': API_PORT
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'db': 'disconnected',
            'error': str(e)
        }), 500


@app.route('/api/stock')
def get_stock():
    """
    Devuelve el stock actual.
    Uso: /api/stock?almacen=cocina
    Si no pones ?almacen=, devuelve todo.
    """
    almacen = request.args.get('almacen')

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        if almacen:
            sql = """
                SELECT 
                    p.nombre AS producto,
                    p.unidad_medida,
                    a.nombre AS almacen,
                    sa.cantidad_actual,
                    sa.stock_minimo_local
                FROM stock_almacen sa
                JOIN productos p ON sa.producto_id = p.id
                JOIN almacenes a ON sa.almacen_id = a.id
                WHERE LOWER(a.nombre) = LOWER(%s)
                ORDER BY p.nombre;
            """
            cursor.execute(sql, (almacen,))
        else:
            sql = """
                SELECT 
                    p.nombre AS producto,
                    p.unidad_medida,
                    a.nombre AS almacen,
                    sa.cantidad_actual,
                    sa.stock_minimo_local
                FROM stock_almacen sa
                JOIN productos p ON sa.producto_id = p.id
                JOIN almacenes a ON sa.almacen_id = a.id
                ORDER BY a.nombre, p.nombre;
            """
            cursor.execute(sql)

        resultados = cursor.fetchall()
        cursor.close()
        conn.close()

        return jsonify({
            'status': 'ok',
            'cantidad': len(resultados),
            'data': resultados
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@app.route('/api/movimientos', methods=['POST'])
def crear_movimiento():
    """
    Registra un movimiento de inventario.
    Ejemplo de JSON que envias:
    {
        "producto_id": 1,
        "almacen_id": 1,
        "almacen_destino_id": 4,
        "tipo_movimiento": "consumo_cocina",
        "cantidad": 2,
        "pin_solicitante": "1111",
        "pin_autorizante": "4444",
        "observaciones": "Para salsa del dia"
    }
    """
    data = request.get_json()

    campos_requeridos = ['producto_id', 'almacen_id', 'tipo_movimiento', 'cantidad', 'pin_solicitante']
    for campo in campos_requeridos:
        if campo not in data:
            return jsonify({'status': 'error', 'error': f'Falta el campo: {campo}'}), 400

    producto_id = data['producto_id']
    almacen_origen_id = data['almacen_id']
    almacen_destino_id = data.get('almacen_destino_id')
    tipo_movimiento = data['tipo_movimiento']
    cantidad = float(data['cantidad'])
    pin_solicitante = data['pin_solicitante']
    pin_autorizante = data.get('pin_autorizante')
    observaciones = data.get('observaciones', '')

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        # CURSOR NORMAL (sin RealDictCursor)
        cursor = conn.cursor()

        # 1. Validar PIN del solicitante
        cursor.execute(
            "SELECT id, nombre FROM usuarios WHERE pin = %s AND activo = TRUE",
            (pin_solicitante,)
        )
        solicitante = cursor.fetchone()
        if not solicitante:
            return jsonify({'status': 'error', 'error': 'PIN de solicitante no valido'}), 403

        # 2. Validar PIN del autorizante (si se mando)
        autorizante = None
        if pin_autorizante:
            cursor.execute(
                "SELECT id, nombre FROM usuarios WHERE pin = %s AND activo = TRUE",
                (pin_autorizante,)
            )
            autorizante = cursor.fetchone()
            if not autorizante:
                return jsonify({'status': 'error', 'error': 'PIN de autorizante no valido'}), 403

        # 3. Validar que el producto existe
        cursor.execute(
            "SELECT id, nombre FROM productos WHERE id = %s AND activo = TRUE",
            (producto_id,)
        )
        producto = cursor.fetchone()
        if not producto:
            return jsonify({'status': 'error', 'error': 'Producto no encontrado'}), 404

        # 4. Validar almacen origen
        cursor.execute(
            "SELECT id, nombre, requiere_autorizacion FROM almacenes WHERE id = %s AND activo = TRUE",
            (almacen_origen_id,)
        )
        almacen_origen = cursor.fetchone()
        if not almacen_origen:
            return jsonify({'status': 'error', 'error': 'Almacen origen no encontrado'}), 404

        # 5. Si el almacen requiere autorizacion, DEBE haber segundo PIN
        if almacen_origen[2] and not autorizante:
            return jsonify({
                'status': 'error',
                'error': f"El almacen '{almacen_origen[1]}' requiere autorizacion con PIN de un segundo usuario"
            }), 403

        # 6. Validar stock suficiente (solo para movimientos que restan)
        if tipo_movimiento in ['consumo_cocina', 'merma', 'ajuste']:
            cursor.execute(
                "SELECT cantidad_actual FROM stock_almacen WHERE producto_id = %s AND almacen_id = %s",
                (producto_id, almacen_origen_id)
            )
            stock = cursor.fetchone()
            stock_actual = stock[0] if stock else 0

            if stock_actual < cantidad:
                return jsonify({
                    'status': 'error',
                    'error': f'Stock insuficiente en {almacen_origen[1]}. Disponible: {stock_actual}, Solicitado: {cantidad}'
                }), 400

        # 7. LIMPIAR cualquier transaccion previa y empezar la transaccion real
        conn.rollback()

        # 8. Insertar el movimiento
        cursor.execute("""
            INSERT INTO movimientos 
            (producto_id, almacen_id, almacen_destino_id, tipo_movimiento, cantidad,
             usuario_solicita_id, usuario_autoriza_id, pin_solicitante, pin_autorizante,
             observaciones, sincronizado)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            producto_id, almacen_origen_id, almacen_destino_id, tipo_movimiento, cantidad,
            solicitante[0],
            autorizante[0] if autorizante else None,
            pin_solicitante,
            pin_autorizante,
            observaciones,
            True
        ))
        movimiento_id = cursor.fetchone()[0]

        # 9. Actualizar stock origen (RESTAR)
        if tipo_movimiento in ['consumo_cocina', 'merma', 'ajuste']:
            cursor.execute("""
                UPDATE stock_almacen 
                SET cantidad_actual = cantidad_actual - %s,
                    fecha_actualizacion = CURRENT_TIMESTAMP
                WHERE producto_id = %s AND almacen_id = %s
            """, (cantidad, producto_id, almacen_origen_id))

            # 10. Si hay destino, SUMAR al destino
            if almacen_destino_id:
                cursor.execute("""
                    INSERT INTO stock_almacen (producto_id, almacen_id, cantidad_actual, stock_minimo_local, fecha_actualizacion)
                    VALUES (%s, %s, %s, 0, CURRENT_TIMESTAMP)
                    ON CONFLICT (producto_id, almacen_id) 
                    DO UPDATE SET 
                        cantidad_actual = stock_almacen.cantidad_actual + EXCLUDED.cantidad_actual,
                        fecha_actualizacion = CURRENT_TIMESTAMP
                """, (producto_id, almacen_destino_id, cantidad))

        elif tipo_movimiento == 'compra':
            # Compra: SUMAR al almacen origen
            cursor.execute("""
                INSERT INTO stock_almacen (producto_id, almacen_id, cantidad_actual, stock_minimo_local, fecha_actualizacion)
                VALUES (%s, %s, %s, 0, CURRENT_TIMESTAMP)
                ON CONFLICT (producto_id, almacen_id) 
                DO UPDATE SET 
                    cantidad_actual = stock_almacen.cantidad_actual + EXCLUDED.cantidad_actual,
                    fecha_actualizacion = CURRENT_TIMESTAMP
            """, (producto_id, almacen_origen_id, cantidad))

        # 11. Confirmar todo
        conn.commit()

        return jsonify({
            'status': 'ok',
            'mensaje': 'Movimiento registrado correctamente',
            'movimiento_id': movimiento_id,
            'producto': producto[1],
            'solicitante': solicitante[1],
            'autorizante': autorizante[1] if autorizante else None
        }), 201

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'status': 'error', 'error': str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == '__main__':
    print(f"Servidor BM Almacenes corriendo en http://localhost:{API_PORT}")
    app.run(host='0.0.0.0', port=API_PORT, debug=True)