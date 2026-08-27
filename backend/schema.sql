-- =============================================
-- BORRAR TODO SI EXISTE (para empezar limpio)
-- =============================================
DROP TABLE IF EXISTS sincronizacion_log CASCADE;
DROP TABLE IF EXISTS solicitudes_detalle CASCADE;
DROP TABLE IF EXISTS solicitudes_cocina CASCADE;
DROP TABLE IF EXISTS movimientos CASCADE;
DROP TABLE IF EXISTS unidades_conversion CASCADE;
DROP TABLE IF EXISTS productos_equivalentes CASCADE;
DROP TABLE IF EXISTS stock_almacen CASCADE;
DROP TABLE IF EXISTS productos CASCADE;
DROP TABLE IF EXISTS almacenes CASCADE;
DROP TABLE IF EXISTS usuarios CASCADE;

-- =============================================
-- 1. USUARIOS
-- =============================================
CREATE TABLE usuarios (
    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    nombre VARCHAR(100) NOT NULL,
    pin VARCHAR(6) NOT NULL,
    rol VARCHAR(30) CHECK (rol IN ('Admin', 'Gerente', 'Encargado de cocina', 'Encargado de Barra', 'Ayudante general')),
    activo BOOLEAN DEFAULT TRUE
);

-- =============================================
-- 2. ALMACENES
-- =============================================
CREATE TABLE almacenes (
    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    requiere_autorizacion BOOLEAN DEFAULT FALSE,
    activo BOOLEAN DEFAULT TRUE
);

-- =============================================
-- 3. PRODUCTOS
-- =============================================
CREATE TABLE productos (
    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    codigo_barras VARCHAR(50) UNIQUE,
    nombre VARCHAR(100) NOT NULL,
    categoria VARCHAR(50),
    unidad_medida VARCHAR(20),
    stock_minimo_general DECIMAL(10,2),
    activo BOOLEAN DEFAULT TRUE
);

-- =============================================
-- 4. STOCK POR ALMACÉN
-- =============================================
CREATE TABLE stock_almacen (
    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    producto_id INTEGER REFERENCES productos(id) ON DELETE CASCADE,
    almacen_id INTEGER REFERENCES almacenes(id) ON DELETE CASCADE,
    cantidad_actual DECIMAL(10,2) DEFAULT 0,
    stock_minimo_local DECIMAL(10,2),
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(producto_id, almacen_id)
);

-- =============================================
-- 5. PRODUCTOS EQUIVALENTES
-- =============================================
CREATE TABLE productos_equivalentes (
    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    producto_principal_id INTEGER REFERENCES productos(id) ON DELETE CASCADE,
    producto_alternativo_id INTEGER REFERENCES productos(id) ON DELETE CASCADE,
    factor_conversion DECIMAL(10,4) NOT NULL DEFAULT 1.0,
    activo BOOLEAN DEFAULT TRUE,
    UNIQUE(producto_principal_id, producto_alternativo_id)
);

-- =============================================
-- 6. UNIDADES DE CONVERSIÓN
-- =============================================
CREATE TABLE unidades_conversion (
    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    producto_base_id INTEGER REFERENCES productos(id) ON DELETE CASCADE,
    unidad_alternativa VARCHAR(20) NOT NULL,
    cantidad_por_unidad DECIMAL(10,2) NOT NULL,
    activo BOOLEAN DEFAULT TRUE
);

-- =============================================
-- 7. MOVIMIENTOS  ← AHORA CON almacen_destino_id
-- =============================================
CREATE TABLE movimientos (
    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    producto_id INTEGER REFERENCES productos(id) ON DELETE CASCADE,
    almacen_id INTEGER REFERENCES almacenes(id) ON DELETE CASCADE,
    almacen_destino_id INTEGER REFERENCES almacenes(id) ON DELETE SET NULL,
    tipo_movimiento VARCHAR(20) CHECK (tipo_movimiento IN ('compra', 'consumo_cocina', 'merma', 'ajuste')),
    cantidad DECIMAL(10,2) NOT NULL,
    usuario_solicita_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    usuario_autoriza_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    pin_solicitante VARCHAR(6),
    pin_autorizante VARCHAR(6),
    fecha_solicitud TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_autorizacion TIMESTAMP,
    sincronizado BOOLEAN DEFAULT FALSE,
    observaciones TEXT
);

-- =============================================
-- 8. SOLICITUDES A COCINA
-- =============================================
CREATE TABLE solicitudes_cocina (
    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    almacen_origen_id INTEGER REFERENCES almacenes(id) ON DELETE CASCADE,
    usuario_solicita_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    usuario_autoriza_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    estado VARCHAR(20) CHECK (estado IN ('pendiente', 'aprobado', 'entregado', 'cancelado')),
    pin_solicitante VARCHAR(6),
    pin_autorizante VARCHAR(6),
    fecha_solicitud TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_entrega TIMESTAMP,
    sincronizado BOOLEAN DEFAULT FALSE,
    observaciones TEXT
);

-- =============================================
-- 9. DETALLE DE SOLICITUDES
-- =============================================
CREATE TABLE solicitudes_detalle (
    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    solicitud_id INTEGER REFERENCES solicitudes_cocina(id) ON DELETE CASCADE,
    producto_id INTEGER REFERENCES productos(id) ON DELETE CASCADE,
    cantidad_solicitada DECIMAL(10,2) NOT NULL,
    cantidad_entregada DECIMAL(10,2) DEFAULT 0,
    producto_equivalente_id INTEGER REFERENCES productos(id) ON DELETE SET NULL,
    cantidad_equivalente DECIMAL(10,2) DEFAULT 0
);

-- =============================================
-- 10. REGISTRO DE SINCRONIZACIÓN
-- =============================================
CREATE TABLE sincronizacion_log (
    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    tablet_id VARCHAR(50),
    fecha_sincronizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    movimientos_subidos INTEGER DEFAULT 0,
    movimientos_descargados INTEGER DEFAULT 0,
    estado VARCHAR(20) CHECK (estado IN ('exitoso', 'fallido', 'parcial'))
);

-- =============================================
-- DATOS DE PRUEBA
-- =============================================

-- Usuarios
INSERT INTO usuarios (nombre, pin, rol) VALUES 
('Admin General', '1234', 'Admin'),
('Juan Cocinero', '1111', 'Encargado de cocina'),
('Maria Barra', '2222', 'Encargado de Barra'),
('Carlos Ayudante', '3333', 'Ayudante general'),
('Ana Gerente', '4444', 'Gerente');

-- Almacenes
INSERT INTO almacenes (nombre, requiere_autorizacion) VALUES 
('Bistro', FALSE),
('Nervion', FALSE),
('Liquidos', TRUE),
('Cocina', FALSE);

-- Productos
INSERT INTO productos (nombre, categoria, unidad_medida, stock_minimo_general) VALUES 
('Tomate Redondo', 'Verduras', 'kg', 10),
('Tomate Cherry', 'Verduras', 'kg', 5),
('Pechuga de Pollo', 'Carnes', 'kg', 8),
('Cebolla', 'Verduras', 'kg', 8),
('Papa', 'Verduras', 'kg', 15),
('Aceite de Oliva', 'Despensa', 'lt', 4),
('Cerveza Ultra Botella 335ml', 'Bebidas', 'Unidad', 48),
('Cerveza Ultra Lata 335ml', 'Bebidas', 'Unidad', 36),
('Cerveza Ultra Caja 24 Botellas', 'Bebidas', 'Caja', 4),
('Leche Entera', 'Lacteos', 'lt', 10),
('Huevos', 'Despensa', 'Unidad', 100),
('Carne de Res', 'Carnes', 'kg', 10);

-- Stock inicial - BISTRO (id=1)
INSERT INTO stock_almacen (producto_id, almacen_id, cantidad_actual, stock_minimo_local) VALUES 
(1, 1, 15, 10),
(3, 1, 10, 8),
(4, 1, 12, 8),
(5, 1, 20, 15),
(6, 1, 5, 4),
(7, 1, 60, 48),
(10, 1, 12, 10),
(11, 1, 120, 100),
(12, 1, 8, 10);

-- Stock inicial - NERVION (id=2)
INSERT INTO stock_almacen (producto_id, almacen_id, cantidad_actual, stock_minimo_local) VALUES 
(7, 2, 40, 36),
(8, 2, 20, 24),
(10, 2, 8, 5);

-- Stock inicial - LIQUIDOS (id=3)
INSERT INTO stock_almacen (producto_id, almacen_id, cantidad_actual, stock_minimo_local) VALUES 
(7, 3, 120, 96),
(9, 3, 3, 5);

-- Stock inicial - COCINA (id=4)
INSERT INTO stock_almacen (producto_id, almacen_id, cantidad_actual, stock_minimo_local) VALUES 
(1, 4, 5, 3),
(3, 4, 4, 2),
(4, 4, 3, 2),
(5, 4, 6, 5),
(6, 4, 2, 2),
(11, 4, 50, 30),
(12, 4, 3, 3);