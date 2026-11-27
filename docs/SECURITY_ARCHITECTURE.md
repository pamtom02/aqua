# Seguridad y arquitectura de AquaBloom

Actualizado: 27 de noviembre de 2026. Este registro distingue código probado de
infraestructura desplegada; no contiene credenciales ni evidencia de usuarios reales.

## Límites y dependencias

- `domain/` conserva reglas independientes para geometrías, estados y procesamiento.
- `application/` coordina casos de uso; los adaptadores HTTP y PostgreSQL siguen en
  `app/` e `infrastructure/`. La adaptación se mantiene gradual: algunos módulos
  heredados todavía mezclan coordinación y consultas; no se ha reescrito el producto.
- PostgreSQL estándar, consultas parametrizadas e identificadores SQL validados.
  Geometrías GeoJSON JSONB validadas por Shapely; no se requiere PostGIS.
- Migraciones inmutables con checksum y bloqueo transaccional. La migración 004
  invalida las sesiones anteriores para introducir MFA sin privilegios heredados.
- Archivos en un volumen privado `/app/data`; UID/GID 10001 y una réplica inicial.
  No se copian `.env`, bases de datos ni respaldos dentro de las imágenes.
- Los servicios de procesamiento usan un token interno independiente. Los stubs y
  simulaciones científicos siguen documentados; alojamiento no equivale a completarlos.

## Identidad y sesiones

- Registro deshabilitado por defecto y roles otorgados exclusivamente en servidor.
- Contraseñas nuevas de 15 a 256 caracteres, rechazo básico de patrones comunes y
  repetitivos. No se consultan servicios externos con contraseñas. La lista básica
  no equivale a un corpus completo de contraseñas comprometidas; ampliarla offline
  antes de habilitar registro masivo. Los hashes anteriores siguen verificándose.
- scrypt versionado, sal aleatoria, N=131072/r=8/p=1; una operación de hash por proceso
  mediante semáforo. Los endpoints síncronos de FastAPI ejecutan el trabajo en su pool
  y no en el bucle HTTP. Límites persistentes por cuenta y peer antes de scrypt.
- JWT con algoritmo, emisor, audiencia y caducidad explícitos, comprobado contra una
  sesión revocable. Solo se guarda el hash del refresh token; se rota con bloqueo.
- Administradores en producción: MFA obligatorio, ocho horas absolutas y veinte
  minutos de inactividad. Las consultas GET y refresh no prolongan el plazo.
  Las escrituras requieren login de los últimos cinco minutos.
- TOTP mediante PyOTP; semillas cifradas con Fernet y clave independiente de JWT y
  PostgreSQL. Contador aceptado bloqueado en la base para impedir replay entre procesos.
  Diez códigos de recuperación aleatorios de 192 bits, almacenados mediante SHA-256,
  de un solo uso. La recuperación revoca sesiones anteriores.
- El login inicial sin MFA solo habilita una vinculación limitada a cinco minutos;
  el propietario debe confirmar su autenticador. No existe un bypass público.
- No se autentica con cookies: Authorization explícito y tokens fuera de localStorage.
  Un futuro adaptador web de cookies necesita Secure/HttpOnly/SameSite y CSRF propio.

## Frontera HTTP y construcción

- CORS por orígenes exactos y rechazo de orígenes ajenos en escrituras. Los clientes
  nativos pueden usar Bearer sin Origin. No se confía en X-Forwarded-For: el límite
  por peer puede agrupar usuarios detrás del ingress; evaluar proxies de confianza
  solo con la topología y rangos reales del clúster.
- Solicitudes comprimidas rechazadas; límite total JSON de 2 MiB y multipart de
  101 MiB, comprobado incluso sin Content-Length. Lecturas del cuerpo con timeout
  de 30 segundos por tramo. Límites más específicos de archivos en sus endpoints.
  En producción, la autenticación de cargas precede al procesamiento de multipart.
- Concurrencia HTTP 32, backlog 64 y keep-alive cinco segundos. Ajustar límites,
  almacenamiento, cuota y réplicas según memoria y métricas reales de UCT.
- nosniff, frame DENY, referencia mínima, permisos de navegador restringidos y CSP
  para respuestas de datos. Swagger/ReDoc conservan sus recursos propios; aún se
  debe verificar su presentación real tras el ingress. HSTS solo para este host,
  sin includeSubDomains sobre dominios universitarios ajenos.
- Python 3.12; lockfiles con versiones y hashes por servicio. Pruebas de los tres
  servicios y migraciones con PostgreSQL 17.6 desechable en Actions. Auditoría de
  los paquetes instalados dentro de las imágenes antes de enviarlas a GHCR.
  El health check comunica el SHA incorporado en la imagen; el autodeploy comprueba
  que coincide con el build que lo disparó, además de exigir PostgreSQL disponible.
- `python-multipart` se actualizó de 0.0.20 a 0.0.34 por avisos que incluyen consumo
  excesivo de CPU al procesar multipart. Los avisos de escritura por nombres de
  archivo no requerían la configuración utilizada aquí; no se ocultaron por ello.

## Recuperación e infraestructura pendiente

Antes de activar producción: verificar la revisión 17.x efectiva y su soporte en
UCT, volumen y permisos, ingress HTTPS y límites de cuerpo/tiempo, aislamiento de
PostgreSQL y servicios internos, origen del cliente y métricas de memoria. El
complemento visto usaba 17.6; no confundirlo con la revisión de seguridad actual.

Respaldos propuestos: diarios, cifrados, retención de 7 diarios y 4 semanales, copia
externa independiente y claves bajo custodia separada. Objetivos iniciales a acordar:
RPO de 24 horas y RTO de cuatro horas. No se han contratado servicios, programado
copias ni probado una restauración real. Detener escrituras o obtener un snapshot
consistente de PostgreSQL y archivos para preservar sus referencias.

Para volver atrás, conservar el SHA/digest de cada imagen antes del cambio y
seleccionarlo explícitamente en Kubero. No eliminar volúmenes ni aplicar SQL inverso
improvisado. Un rollback de código debe ser compatible con las migraciones aplicadas;
de lo contrario, restaurar ambos conjuntos desde una copia comprobada. En una base
restaurada eliminar `auth_sessions` antes de abrir tráfico. No imprimir hashes,
semillas, tokens o archivos de respaldo al diagnosticar problemas.

Pendiente de infraestructura: confirmar usuarios individuales y MFA en Kubero,
GitHub, hosting/dominio/correo por separado; establecer retención restringida de
eventos administrativos, depuración de datos y destinatarios de alertas antes de
activar envíos. El proyecto heredado conserva auditoría parcial; no se declara un
sistema completo de monitoreo ni una política de borrado ya operativa.

No se importaron cuentas, datos ni archivos de Supabase. Requeriría un procedimiento
de exportación, revisión y migración independiente.

## Referencias revisadas

- [OWASP: almacenamiento de contraseñas](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).
- [PyOTP: secretos y prevención de replay](https://pyauth.github.io/pyotp/).
- [Fernet: cifrado autenticado](https://cryptography.io/en/stable/fernet/).
- [Avisos oficiales de python-multipart](https://github.com/Kludex/python-multipart/security/advisories).
- [Versiones soportadas de PostgreSQL](https://www.postgresql.org/support/versioning/).
