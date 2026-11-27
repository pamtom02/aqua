# Estado de validación

Actualizado el 27 de noviembre de 2026.

## Publicación y autoría comprobadas

- Rama de entrega: `deploy/kubero-api`, publicada por Git sin force push.
- Commit preparado original: `5853957`; historial conservado.
- Autor y committer: `Pamtom21`, usando la configuración Git existente.
- La credencial Git autentica como `Pamtom21`; GitHub devuelve `push=true` y
  `admin=false`. El 403 anterior del conector no probaba falta de colaboración.
  El push de terminal ahora funciona.

## Evidencia de GitHub Actions

- [Ejecución inicial](https://github.com/pamtom02/aqua/actions/runs/45952157365):
  139 pruebas correctas y tres fallos. Se corrigieron dos fixtures sin base simulada
  y una aserción que confundía «incorrectos» con una contraseña filtrada.
- [Validación de los tres servicios](https://github.com/pamtom02/aqua/actions/runs/45952382707):
  pruebas e imágenes correctas antes de los cambios adicionales de seguridad.
- [Seguridad y dependencias fijadas](https://github.com/pamtom02/aqua/actions/runs/45953463391),
  commit `d6370dd`: 153 pruebas de API, 23 satelitales y 25 científicas correctas;
  tres imágenes construidas y sus dependencias instaladas auditadas correctamente.
- La integración ejecutó migraciones dos veces sobre PostgreSQL 17.6 real y comprobó
  roles, aislamiento, GeoJSON, rotación y revocación de sesiones. Verificó MFA en modo
  production, almacenamiento cifrado, exclusión de TOTP concurrentes, recuperación
  de un solo uso, inactividad, plazo absoluto y reautenticación reciente.

## Comprobaciones locales

- TestClient ya funciona en Windows; no persiste el bloqueo de sockets.
- Última suite de API: 153 correctas y una omitida por ausencia de PostgreSQL local.
  La integración real se ejecuta en Actions; no se presenta la omisión como éxito.
- 23 pruebas satelitales y 25 científicas correctas localmente.
- Auditoría del entorno Python actualizado: sin vulnerabilidades conocidas ni
  conflictos. La evidencia de imágenes Linux está en Actions.
- YAML, espacios y búsqueda de patrones de secretos en archivos controlados por Git
  correctos. Esta búsqueda no prueba ausencia absoluta de secretos.

## Estado externo pendiente

- Kubero abre `/login`. No se han creado aplicaciones, complementos ni volúmenes
  durante esta continuación.
- Falta autenticar al propietario en Kubero, configurar los secretos de infraestructura
  y `KUBERO_TOKEN` directamente en sus destinos y verificar el dominio real.
- El SHA incorporado en cada imagen permite distinguir una API antigua de la revisión
  esperada. Un restart aceptado o una construcción correcta no prueban el despliegue.
- MFA está implementado y probado con cuentas sintéticas; el propietario debe vincular
  y confirmar su autenticador real y custodiar sus códigos.
- No se han importado datos, cuentas ni archivos de Supabase.

La siguiente revisión de Actions debe verificar los últimos cambios de documentación,
el rechazo temprano de cargas anónimas y la comprobación de revisión tras el despliegue.
Registrar el resultado real después de integrar y publicar en GHCR/Kubero.
