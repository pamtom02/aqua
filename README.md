# AquaBloom API en Kubero UCT

Backend FastAPI de AquaBloom Sur adaptado a PostgreSQL estándar, autenticación propia y archivos privados en un volumen. No requiere Supabase ni PostGIS.

## Servicios

| App | Imagen | Puerto | Función |
| --- | --- | --- | --- |
| api | ghcr.io/pamtom02/aqua-api:latest | 8000 | API pública, identidad, catálogo, datasets, migraciones y archivos |
| satellite | ghcr.io/pamtom02/aqua-satellite:latest | 8000 | Servicio satelital y cola Redis |
| scientific | ghcr.io/pamtom02/aqua-scientific:latest | 8003 | Servicio científico |
| satellite-worker | misma imagen Satellite | sin HTTP | python -m app.worker |
| training-worker | misma imagen Scientific | sin HTTP | python -m app.training_worker |

Las carpetas `client/` y `server/` contienen la demo original de tareas y quedan como referencia. El frontend de esa demo no consume esta API. El cliente de AquaBloom debe usar los endpoints de autenticación propios descritos abajo.

## Despliegue

Sigue [docs/KUBERO.md](docs/KUBERO.md). El pipeline configurado es **facu**, fase **production**.

Al subir cambios a main, GitHub Actions:
1. Ejecuta los contratos y una prueba integral contra PostgreSQL 17.
2. Construye y publica las tres imágenes, con etiquetas latest y SHA del commit.
3. Solicita el reinicio de las apps configuradas si el build terminó correctamente.
4. Consulta el estado de PostgreSQL desde la API si está definida API_BASE_URL.

El primer despliegue requiere crear las aplicaciones, PostgreSQL, Redis y el volumen en Kubero. Los workflows no crean esa infraestructura ni trasladan datos existentes de Supabase.

## Autenticación propia

- POST /auth/login: JSON con email y password.
- POST /auth/refresh: JSON con refresh_token; rota el token de renovación.
- POST /auth/logout: revoca la sesión con Authorization: Bearer.
- GET /auth/me: perfil y membresías.
- POST /auth/register: email, password, full_name; deshabilitado por defecto.

Las contraseñas se guardan con scrypt y sal aleatoria. El token JWT vence a los 20 minutos y se comprueba contra una sesión revocable en PostgreSQL. El rol se lee del servidor; el cliente no puede asignarlo al registrarse.

En producción, los administradores deben vincular MFA antes de acceder a operaciones privadas.
La confirmación personal y los códigos de recuperación se explican en [docs/KUBERO.md](docs/KUBERO.md).
Preparar el flujo no significa que el propietario ya tenga el segundo factor activado.

Crea la primera cuenta con BOOTSTRAP_ADMIN_EMAIL y BOOTSTRAP_ADMIN_PASSWORD. Quita esas variables después del primer arranque; no son una puerta de acceso permanente ni cambian una contraseña existente.

## Persistencia

Las migraciones en apps/api/migrations se ejecutan bajo un bloqueo de PostgreSQL y registran su checksum. Las geometrías se guardan como GeoJSON JSONB y se validan con Shapely. La ubicación de estaciones sigue comprobándose contra el polígono del lago.

Los archivos se guardan bajo STORAGE_ROOT=/app/data. Hay que montar un volumen persistente allí. No se publican como archivos estáticos; las descargas siguen pasando por endpoints autorizados. Una sola réplica de API conserva la semántica de escritura del volumen.

Esta versión prepara una base nueva. Migrar cuentas, datos o archivos existentes exige una exportación y un procedimiento separado; no se accede al proyecto Supabase anterior.

## Desarrollo y pruebas

Desde apps/api:
```sh
python -m pip install --require-hashes -r requirements.lock
python -m pip install pytest==9.2.0 httpx2==2.16.2
python -m pytest -q
```

Para incluir la prueba real de base de datos, define TEST_DATABASE_URL apuntando a una base **nueva y desechable**. La prueba crea usuarios y datos de prueba. Sin esa variable, esa prueba se omite explícitamente.

Para ejecutar localmente todos los contenedores: copia .env.example a .env, configura secretos y ejecuta docker compose up --build. Los secretos no se guardan en Git.

Las imágenes y CI usan Python 3.12 y dependencias fijadas con hashes. La construcción
audita los paquetes realmente instalados dentro de cada imagen antes de publicarla.
Consulta [docs/SECURITY_ARCHITECTURE.md](docs/SECURITY_ARCHITECTURE.md) para controles,
recuperación y comprobaciones pendientes en UCT.

## Alcance heredado

Se mantienen los endpoints de negocio y los contratos del backend recibido. Algunos endpoints de candidatos/manifiestos/versiones estaban definidos como 501 y otros procesos científicos contienen simulaciones del sprint; alojar el backend no implementa esas funcionalidades pendientes.
