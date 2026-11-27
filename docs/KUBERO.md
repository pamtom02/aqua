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
- 17.6 es la versión observada en el complemento, no la revisión de seguridad vigente.
  Antes de activar producción, seleccionar una revisión 17.x actual compatible con UCT
  o pedir su actualización al administrador. No cambiar de versión mayor sobre un volumen existente.
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
| MFA_ENCRYPTION_KEY | clave Fernet propia de este proyecto, distinta de JWT_SECRET y custodiada fuera de PostgreSQL |
| INTERNAL_SERVICE_TOKEN | otro secreto aleatorio de al menos 32 caracteres |
| STORAGE_ROOT | /app/data |
| ALLOW_REGISTRATION | false, o true si el proyecto permite registro público |
| CORS_ORIGINS | orígenes exactos de la web, separados por comas |
| SATELLITE_SERVICE_URL | http://satellite-kuberoapp:80 |
| SCIENTIFIC_SERVICE_URL | http://scientific-kuberoapp:80 |
| BOOTSTRAP_ADMIN_EMAIL | correo de la primera cuenta, opcional |
| BOOTSTRAP_ADMIN_PASSWORD | contraseña inicial de 15 a 256 caracteres, opcional |

Tras crear la primera cuenta, retira las dos variables BOOTSTRAP. Las cuentas previas de Supabase no se importan automáticamente.

La clave MFA es una clave Fernet de 32 bytes aleatorios codificada en base64 URL-safe.
El propietario debe generarla en su gestor de secretos y configurarla directamente en Kubero;
no pegarla en el chat, en argumentos de consola ni en archivos públicos. Sin una clave válida
la API no arranca en producción. Guardar una copia separada de los respaldos de PostgreSQL.

### Vinculación personal del segundo factor

El propietario realiza estos pasos desde un cliente seguro sobre HTTPS, sin grabaciones ni capturas:

1. `POST /auth/login` con correo y contraseña. Si el administrador aún no tiene MFA,
   devuelve `mfa_required=true` y una sesión restringida de cinco minutos.
   Esa sesión solo permite vincular MFA y cerrar sesión; no habilita operaciones privadas.
2. `POST /auth/mfa/enroll` con el Bearer de esa sesión. Registrar el `provisioning_uri`
   localmente en el autenticador; nunca enviarlo a un generador de QR externo.
3. `POST /auth/mfa/confirm` con ese Bearer y JSON `code` del autenticador. Solo la
   confirmación correcta activa MFA. Devuelve una sesión nueva y diez códigos de recuperación;
   guardarlos en el gestor de secretos. Solo se muestran una vez y se almacenan mediante hash.
4. En siguientes logins enviar `second_factor` junto con correo y contraseña. Acepta
   el TOTP o un código de recuperación de un solo uso. La recuperación revoca las demás sesiones.

La semilla se cifra con Fernet. PostgreSQL serializa la aceptación de TOTP para impedir
repeticiones entre procesos. Una sesión administrativa vence tras ocho horas o veinte minutos
sin escritura explícita; GET y refresh automáticos no prolongan ese plazo. Las escrituras
administrativas requieren un login de los últimos cinco minutos. El cliente debe soportar
estos estados antes de dar acceso administrativo a una web o app móvil.

No guardar el Bearer ni el refresh token en localStorage. Para un cliente web que necesite
cookies, implementar un adaptador de sesión con HttpOnly y CSRF antes de habilitar ese flujo;
la API actual usa Authorization explícito y no autentica mediante cookies.

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

La comprobación exige `API_BASE_URL` por HTTPS y verifica también el SHA de la imagen.
Al disparar manualmente **Deploy to Kubero**, completa `revision` con el SHA completo
de la release que ya existe en GHCR y está configurada en Kubero. Esto permite
redesplegar aunque `main` tenga después cambios exclusivos de documentación.
La release verificada de esta entrega es `a7e17c598ef465ecea06450e66a3eea6208bcd3d`.

## 7. Verificación

- /health/live debe responder 200.
- /api/v1/health debe responder 200 con PostgreSQL disponible; responde 503 si no está listo.
- /docs debe presentar los endpoints sobre el dominio actual.
- Prueba login, creación de organización, catálogo y descarga de archivos.
- Redespliega y comprueba que los registros y los archivos persisten.
- Respalda PostgreSQL y los archivos por separado antes de eliminar una app o volumen.

La migración de infraestructura no cambia automáticamente los clientes: la web y la app móvil deben usar /auth/login, /auth/refresh y /auth/logout de la API propia.
