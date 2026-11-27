"""Convierte el catastro público DGA a GeoJSON, sin alterar costas ni islas.

Herramientas de conversión: pyshp==3.1.9, pyproj==3.7.2 y Shapely del proyecto.
No son dependencias nuevas del proceso HTTP. El ZIP nunca se extrae al disco.
"""
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

import shapefile
from pyproj import CRS, Transformer
from shapely import transform
from shapely.geometry import mapping, shape
from shapely.geometry.polygon import orient

CATALOG = Path(__file__).resolve().parents[1] / "local_backend" / "catalog"
SOURCE = CATALOG / "Lagos_DGA_source.zip"
NAMES = {
    "LAGO CABURGA": "Caburga",
    "LAGO VILLARRICA": "Villarrica",
    "LAGO PANGUIPULLI": "Panguipulli",
    "LAGO RANCO": "Ranco",
}
PROVIDER = "Dirección General de Aguas (DGA), Ministerio de Obras Públicas de Chile"
METADATA_URL = "https://geoportal.cl/geoportal/catalog/35252/Catastro%20de%20Lagos"
DOWNLOAD_URL = "https://dga.mop.gob.cl/uploads/sites/13/2024/07/Lagos.zip"


def rounded(value):
    if isinstance(value, (tuple, list)):
        return [rounded(item) for item in value]
    return round(value, 7) if isinstance(value, float) else value


def main():
    with ZipFile(SOURCE) as archive:
        if len(archive.infolist()) > 20 or sum(info.file_size for info in archive.infolist()) > 20_000_000:
            raise ValueError("El archivo supera los límites de conversión.")
        source_crs = CRS.from_wkt(archive.read("Inventario_Lagos.prj").decode("utf-8"))
        if source_crs.to_epsg() != 32719:
            raise ValueError("Proyección de origen inesperada; revisar antes de convertir.")
        project = Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)
        reader = shapefile.Reader(
            shp=io.BytesIO(archive.read("Inventario_Lagos.shp")),
            shx=io.BytesIO(archive.read("Inventario_Lagos.shx")),
            dbf=io.BytesIO(archive.read("Inventario_Lagos.dbf")), encoding="utf-8")
        features = []
        for record in reader.iterShapeRecords():
            attributes = record.record.as_dict()
            source_name = attributes["NOMBRE"]
            if source_name not in NAMES:
                continue
            original = shape(record.shape.__geo_interface__)
            if original.geom_type != "Polygon" or not original.is_valid:
                raise ValueError(f"Geometría fuente inválida: {source_name}")
            projected = transform(original, project.transform, interleaved=False)
            geometry = mapping(orient(projected, sign=1.0))
            geometry["coordinates"] = rounded(geometry["coordinates"])
            checked = shape(geometry)
            if not checked.is_valid or checked.is_empty:
                raise ValueError(f"Conversión inválida: {source_name}")
            if len(checked.interiors) != len(original.interiors):
                raise ValueError("La conversión debe conservar las islas.")
            features.append({
                "type": "Feature",
                "properties": {
                    "catalog_name": NAMES[source_name], "source_name": source_name,
                    "source_id": int(attributes["NUM"]), "source_bna_code": attributes["CODBNA"],
                    "source_area_km2": attributes["AREA_KM2"], "source": "DGA/MOP · Catastro de Lagos",
                    "metadata_url": METADATA_URL,
                }, "geometry": geometry,
            })
        if {item["properties"]["catalog_name"] for item in features} != set(NAMES.values()) or len(features) != 4:
            raise ValueError("El catastro debe aportar exactamente los cuatro lagos esperados.")

    features.sort(key=lambda item: item["properties"]["catalog_name"])
    output = CATALOG / "lake_shorelines.geojson"
    output.write_text(json.dumps({"type": "FeatureCollection", "features": features},
                                 ensure_ascii=False, separators=(",", ":"))+"\n", encoding="utf-8")
    manifest = {
        "provider": PROVIDER, "metadata_url": METADATA_URL, "download_url": DOWNLOAD_URL,
        "resource_publication_date": "2020-09-01", "retrieved_client_date": "2026-11-25",
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "geojson_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "source_crs": "EPSG:32719", "output_crs": "EPSG:4326",
        "coordinate_order": "longitude, latitude", "decimal_places": 7,
        "simplification": "none", "islands": "all source interior rings retained",
        "attribution": PROVIDER+" · Catastro de Lagos; vía IDE Chile.",
        "tools": {"pyshp": "3.1.9", "pyproj": "3.7.2"},
    }
    (CATALOG / "shoreline_source.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    for item in features:
        geometry = item["geometry"]
        print(item["properties"]["catalog_name"],
              sum(len(ring) for ring in geometry["coordinates"]), "vertices;",
              len(geometry["coordinates"])-1, "islas")


if __name__ == "__main__":
    main()
