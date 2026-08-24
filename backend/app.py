import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Cargar variables del archivo .env
load_dotenv()

app = Flask(__name__)
CORS(app)  # Permite que el frontend (navegador) hable con la API

# Configuración de la base de datos desde .env
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'BM_Almacenes'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'Michellena24'),
    'port': os.getenv('DB_PORT', '5432')
}

API_PORT = int(os.getenv('API_PORT', 5001))


def get_db_connection():
    """Crea y devuelve una conexión a PostgreSQL."""
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


# Arrancar el servidor
if __name__ == '__main__':
    print(f"🚀 Servidor BM Almacenes corriendo en http://localhost:{API_PORT}")
    app.run(host='0.0.0.0', port=API_PORT, debug=True)