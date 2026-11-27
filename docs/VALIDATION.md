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

- Integrado por fast-forward en `main`: release `a7e17c598ef465ecea06450e66a3eea6208bcd3d`,
  conservando autoría e historial. El último commit de documentación/configuración
  puede ser posterior al SHA de la imagen; no debe confundirse con una nueva release.
- [Build y publicación en main](https://github.com/pamtom02/aqua/actions/runs/45954233390):
  154 pruebas de API, 23 satelitales y 25 científicas correctas: 202 en total.
  Las tres imágenes se construyeron, auditaron y publicaron con `latest` y SHA.
- Se verificó acceso anónimo HTTP 200 a los tres manifiestos de GHCR. Digest API:
  `sha256:7ca71bcbec965dd838b98a7e71d3c50c7029744662473301fe3aa97c64d90c6d`.
- Variables guardadas y verificadas en GitHub: `KUBERO_PIPELINE=facu`, `KUBERO_APPS=api`
  y `API_BASE_URL=https://api-aquabloom.inf.uct.cl`.
- [Primer autodeploy](https://github.com/pamtom02/aqua/actions/runs/45954445421):
  falló explícitamente por ausencia de `KUBERO_TOKEN`; no se envió un restart a UCT.

- Sesión de Kubero autenticada por el propietario. `facu/production` seguía sin apps.
- Formulario de nueva app `api` preparado, todavía sin guardar ni desplegar: imagen
  pública, puerto 8000, SSL, dominio validado como disponible por Kubero, UID/GID 10001,
  raíz de solo lectura, sin escalada, una réplica web y cero workers, perfil Small,
  health `/health/live` con startup 120 s y timeout 5 s, volumen `/app/data` de 8Gi
  con `csi-cephfs-sc` y `ReadWriteOnce`, variables públicas completas y campos privados
  vacíos. No se afirma todavía disponibilidad DNS, certificado válido ni permisos del PVC.
- Complemento PostgreSQL preparado en el mismo formulario: instancia `postgres`,
  base/usuario `aquabloom`, host mostrado por Kubero `api-postgres`, tag 17.12,
  recursos 50m/500m y 128Mi/512Mi, almacenamiento 8Gi CephFS RWO. Se verificó HTTP 200
  al manifiesto oficial `postgres:17.12`; no se han creado aún estos recursos.
- Falta que el propietario complete contraseñas y secretos directamente en Kubero,
  guarde el complemento y cree la app. `KUBERO_TOKEN` sigue pendiente en GitHub.
- El SHA incorporado en cada imagen permite distinguir una API antigua de la revisión
  esperada. Un restart aceptado o una construcción correcta no prueban el despliegue.
- MFA está implementado y probado con cuentas sintéticas; el propietario debe vincular
  y confirmar su autenticador real y custodiar sus códigos.
- No se han importado datos, cuentas ni archivos de Supabase.

La construcción valida el rechazo temprano de cargas anónimas. La comprobación de
revisión tras el despliegue sigue pendiente de una API real. En un disparo manual,
indicar el SHA completo de la release publicada, no el de un commit posterior que
solo modifique documentación. El workflow verifica SHA y disponibilidad de PostgreSQL.
