# Configuración de Kubero UCT

## 1. Imágenes

Espera a que **Build API images** termine correctamente. En GitHub Packages, haz públicas las imágenes aqua-api, aqua-satellite y aqua-scientific: la instalación UCT documentada descarga imágenes públicas.

No copies .env, claves, tokens ni archivos personales al repositorio. Los Dockerfile copian explícitamente el código necesario.

## 2. API principal

Dentro del pipeline **facu**, fase **production**, crea esta aplicación:

| Campo | Valor |
| --- | --- |
| Nombre | api |
| Imagen | ghcr.io/pamtom02/aqua-api |
| Tag | latest |
| Puerto | 8000 |
| Dominio propuesto | api-aquabloom.inf.uct.cl, si está disponible |
| SSL | activado |
| Réplicas | 1 web, 0 worker |
| Perfil inicial | Small; aumenta según las métricas |
| Health check | /health/live, inicio 120 s, timeout 5 s |
| Usuario/grupo | 10001 / 10001 |
| Escalada de privilegios | desactivada |

Monta un volumen en **/app/data**, por ejemplo aqua-files, 8Gi, clase **csi-cephfs-sc**, modo **ReadWriteOnce**. La aplicación necesita escribir en ese montaje como UID 10001. Comprueba permisos en el primer arranque. Si el proveedor entrega un volumen propiedad de root sin permisos para ese usuario, pide al administrador que ajuste la propiedad/grupo del volumen; no uses el filesystem efímero para guardar archivos.

## 3. PostgreSQL

Agrega el complemento **PostgreSQL** a api:

- Instance Name: postgres.
- Version/Tag: 17.6.
- Database Name: aquabloom.
- Additional Username: aquabloom.
- Contraseñas: valores propios, configurados en Kubero.
- Storage Class: csi-cephfs-sc.
- Storage Size: 8Gi.
- Access Modes: ReadWriteOnce.
- CPU request/limit: 50m / 500m.
- Memory request/limit: 128Mi / 512Mi.

Copia el host que muestre la tarjeta del complemento. Con los nombres anteriores, la documentación indica **api-postgres**, puerto **5432**.

Configura manualmente DATABASE_URL en la API:
```text
postgresql://aquabloom:CONTRASENA_CODIFICADA@api-postgres:5432/aquabloom?sslmode=disable
```

Si la contraseña contiene caracteres reservados de URL, codifícala. El complemento documentado no usa TLS; la conexión queda en la red del clúster. El HTTPS del dominio público protege otro tramo y no cambia esa conexión.

Las migraciones se aplican automáticamente al arrancar la imagen. No ejecutes las migraciones originales de Supabase sobre esta base.

## 4. Variables de la API

| Variable | Valor |
| --- | --- |
| ENVIRONMENT | production |
| DATABASE_URL | conexión del complemento |
| JWT_SECRET | secreto aleatorio de al menos 32 caracteres |
| INTERNAL_SERVICE_TOKEN | otro secreto aleatorio de al menos 32 caracteres |
| STORAGE_ROOT | /app/data |
| ALLOW_REGISTRATION | false, o true si el proyecto permite registro público |
| CORS_ORIGINS | orígenes exactos de la web, separados por comas |
| SATELLITE_SERVICE_URL | http://satellite-kuberoapp:80 |
| SCIENTIFIC_SERVICE_URL | http://scientific-kuberoapp:80 |
| BOOTSTRAP_ADMIN_EMAIL | correo de la primera cuenta, opcional |
| BOOTSTRAP_ADMIN_PASSWORD | contraseña inicial de 12 a 256 caracteres, opcional |

Tras crear la primera cuenta, retira las dos variables BOOTSTRAP. Las cuentas previas de Supabase no se importan automáticamente.

## 5. Servicios de procesamiento

Crea satellite y scientific con los puertos de la tabla del README. Usa dominios únicos si el formulario lo exige. En producción, sus rutas de procesamiento exigen X-Internal-Token. La API valida al usuario y adjunta ese token en las llamadas internas. Mantén sus health checks públicos y no publiques secretos en clientes.

En satellite:
- SATELLITE_ENVIRONMENT=production
- SATELLITE_REDIS_URL=redis://HOST_DEL_COMPLEMENTO:6379/0
- INTERNAL_SERVICE_TOKEN=el mismo de api

Añade Redis y copia su host real. No deduzcas el hostname si la tarjeta ofrece uno.

En scientific:
- ENVIRONMENT=production
- CORE_API_URL=http://api-kuberoapp:80
- INTERNAL_SERVICE_TOKEN=el mismo de api

Crea satellite-worker con la imagen Satellite y comando **python -m app.worker**, la misma URL de Redis y comprobaciones HTTP desactivadas.

Crea training-worker con la imagen Scientific y comando **python -m app.training_worker**. Configura DATABASE_URL, CORE_API_URL e INTERNAL_SERVICE_TOKEN. Desactiva las comprobaciones HTTP porque no escucha HTTP.

Los procesos worker usan una sola réplica. El despliegue de la API principal permite probar identidad, catálogo y datasets sin publicar todavía las apps de procesamiento.

## 6. Autodeploy

1. Desde tu perfil de Kubero, crea tu token de API.
2. En pamtom02/aqua, Settings → Secrets and variables → Actions, crea el secret **KUBERO_TOKEN**.
3. Configura estas Repository variables:

| Variable | Valor |
| --- | --- |
| KUBERO_PIPELINE | facu |
| KUBERO_APPS | api, o la lista con espacios api satellite scientific satellite-worker training-worker cuando todas existan |
| API_BASE_URL | https://DOMINIO_REAL_DE_LA_API, sin /api/v1 |

El workflow no usa nombres del ejemplo anterior. Si Kubero devuelve 401, 403 o 404, el despliegue falla explícitamente. Una solicitud de restart aceptada no garantiza que el proceso esté listo; la comprobación posterior consulta /api/v1/health.

## 7. Verificación

- /health/live debe responder 200.
- /api/v1/health debe responder 200 con PostgreSQL disponible; responde 503 si no está listo.
- /docs debe presentar los endpoints sobre el dominio actual.
- Prueba login, creación de organización, catálogo y descarga de archivos.
- Redespliega y comprueba que los registros y los archivos persisten.
- Respalda PostgreSQL y los archivos por separado antes de eliminar una app o volumen.

La migración de infraestructura no cambia automáticamente los clientes: la web y la app móvil deben usar /auth/login, /auth/refresh y /auth/logout de la API propia.
