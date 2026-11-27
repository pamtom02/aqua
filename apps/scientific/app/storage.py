"""Private file storage. Only authorized API endpoints can expose these files."""
import os
import tempfile
from pathlib import Path


class StorageException(Exception):
    pass


class FileStorage:
    BUCKETS = {"imports", "training_files", "model_artifacts"}

    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def from_(self, bucket: str):
        if bucket not in self.BUCKETS:
            raise StorageException("Contenedor de archivos desconocido.")
        return FileBucket(self.root / bucket)


class FileBucket:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _path(self, key: str) -> Path:
        if not key or "\\" in key or ":" in key or "\x00" in key:
            raise StorageException("Ruta de archivo no válida.")
        candidate = (self.root / key).resolve()
        if candidate == self.root or not candidate.is_relative_to(self.root):
            raise StorageException("Ruta de archivo no válida.")
        return candidate

    def upload(self, path: str, file: bytes, file_options: dict | None = None):
        target = self._path(path)
        content = bytes(file)
        if len(content) > 100 * 1024 * 1024:
            raise StorageException("El archivo supera 100 MiB.")
        target.parent.mkdir(parents=True, exist_ok=True)
        upsert = str((file_options or {}).get("upsert", "false")).lower() == "true"
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                temp_name = stream.name
                os.chmod(temp_name, 0o600)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            if upsert:
                os.replace(temp_name, target)
            else:
                # Atomic create-if-absent: never overwrite a model artifact.
                descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                try:
                    with os.fdopen(descriptor, "wb") as destination:
                        destination.write(content)
                        destination.flush()
                        os.fsync(destination.fileno())
                except BaseException:
                    target.unlink(missing_ok=True)
                    raise
                os.unlink(temp_name)
            temp_name = None
        except OSError as exc:
            raise StorageException("No se pudo guardar el archivo.") from exc
        finally:
            if temp_name and os.path.exists(temp_name):
                os.unlink(temp_name)
        return {"path": path}

    def download(self, path: str) -> bytes:
        target = self._path(path)
        try:
            return target.read_bytes()
        except OSError as exc:
            raise StorageException("Archivo no disponible.") from exc

    def remove(self, paths: list[str]):
        for path in paths:
            try:
                self._path(path).unlink(missing_ok=True)
            except OSError as exc:
                raise StorageException("No se pudo retirar el archivo.") from exc
        return [{"name": path} for path in paths]
