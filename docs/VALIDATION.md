# Estado de validacion

- 25 pruebas locales de esquemas, permisos, calculo NDCI, filtros SQL y almacenamiento: correctas.
- Compilacion Python de los tres servicios: correcta.
- Revision de espacios y sintaxis YAML: correcta.
- El entorno Windows restringido no permite crear el socket local que usa TestClient.
- La suite completa y la migracion real se verificaran con PostgreSQL 17 en GitHub Actions.
- No se han migrado datos existentes ni se han creado recursos de Kubero.
- El conector de GitHub actual autentica a Pamtom21 y su instalacion pertenece a esa cuenta.
  Las operaciones de escritura sobre pamtom02/aqua devuelven 403.
- Actions se habilito mediante la sesion web del propietario;
  la publicacion del codigo sigue pendiente del permiso del conector.

La rama de entrega local es deploy/kubero-api. Autor y committer: Pamtom21.
