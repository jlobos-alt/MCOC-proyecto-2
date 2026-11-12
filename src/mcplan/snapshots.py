"""Snapshots inmutables de clima: JSON crudo + CSV normalizado + hash.

Regla del curso: un forecast no se pisa. Cada descarga se guarda en su propia
carpeta con la fecha de emision en el nombre, el JSON crudo tal como llego, un
CSV normalizado y un `index.json` con los hashes SHA-256. Si el mismo snapshot
se intenta guardar dos veces con contenido distinto, el guardado falla: eso es
lo que hace trazable la cadena "que sabiamos ese dia -> que simulamos".

Estructura en disco:

    datos/forecast/
        index.json
        2026-11-11T140500Z_open-meteo-forecast/
            raw.json
            normalizado.csv
            metadata.json

`verify()` recalcula los hashes y detecta cualquier archivo alterado.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .meteo import MeteoFrame

CSV_COLUMNS = (
    "time",
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "shortwave_radiation",
    "cloud_cover",
    "precipitation",
)


@dataclass(frozen=True)
class SnapshotMeta:
    """Metadatos de un snapshot; suficiente para reproducir la corrida."""

    snapshot_id: str
    source: str
    model: str
    issued_at: str
    fetched_at: str
    endpoint: str
    latitude: float
    longitude: float
    timezone: str
    first_time: str
    last_time: str
    n_hours: int
    sha256_raw: str
    sha256_csv: str
    files: dict[str, str] = field(default_factory=dict)
    notes: str = ""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _csv_text(frame: MeteoFrame) -> str:
    from io import StringIO

    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for fila in frame.rows():
        writer.writerow([fila[c] for c in CSV_COLUMNS])
    return buffer.getvalue()


def _id_por_defecto(frame: MeteoFrame) -> str:
    try:
        sello = datetime.fromisoformat(frame.fetched_at).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    except ValueError:
        sello = frame.fetched_at.replace("-", "").replace(":", "")
    return f"{sello}_{frame.source}"


def _leer_index(root: Path) -> list[dict]:
    ruta = root / "index.json"
    if not ruta.exists():
        return []
    data = json.loads(ruta.read_text(encoding="utf-8"))
    return list(data.get("snapshots", []))


def _escribir_index(root: Path, entradas: list[dict]) -> None:
    entradas = sorted(entradas, key=lambda e: (e.get("fetched_at", ""), e.get("snapshot_id", "")))
    (root / "index.json").write_text(
        json.dumps({"snapshots": entradas}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def save_snapshot(
    frame: MeteoFrame,
    root: Path,
    snapshot_id: str | None = None,
    notes: str = "",
    overwrite_index: bool = True,
) -> SnapshotMeta:
    """Guarda un snapshot y lo registra en `index.json`.

    Si la carpeta ya existe:
    - con el mismo contenido: devuelve el snapshot existente (idempotente);
    - con contenido distinto: lanza `FileExistsError` (nunca se pisa).
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    sid = snapshot_id or _id_por_defecto(frame)
    carpeta = root / sid

    crudo = frame.raw or json.dumps(
        {"hourly": {c: [getattr(frame, c) for c in CSV_COLUMNS[1:]]}}, ensure_ascii=False
    ).encode("utf-8")
    texto_csv = _csv_text(frame)
    hash_raw = sha256_bytes(crudo)
    hash_csv = sha256_bytes(texto_csv.encode("utf-8"))

    if carpeta.exists():
        meta_existente = _leer_meta(carpeta)
        if meta_existente is None:
            raise FileExistsError(f"{carpeta} existe y no tiene metadata.json")
        if meta_existente.sha256_raw != hash_raw or meta_existente.sha256_csv != hash_csv:
            raise FileExistsError(
                f"El snapshot {sid} ya existe con otro contenido: no se sobrescribe."
            )
        return meta_existente

    carpeta.mkdir(parents=True)
    (carpeta / "raw.json").write_bytes(crudo)
    (carpeta / "normalizado.csv").write_bytes(texto_csv.encode("utf-8"))
    meta = SnapshotMeta(
        snapshot_id=sid,
        source=frame.source,
        model=frame.model,
        issued_at=frame.issued_at,
        fetched_at=frame.fetched_at,
        endpoint=frame.endpoint,
        latitude=frame.latitude,
        longitude=frame.longitude,
        timezone=frame.timezone,
        first_time=frame.times[0],
        last_time=frame.times[-1],
        n_hours=len(frame),
        sha256_raw=hash_raw,
        sha256_csv=hash_csv,
        files={"raw": "raw.json", "csv": "normalizado.csv"},
        notes=notes or frame.notes,
    )
    (carpeta / "metadata.json").write_text(
        json.dumps(asdict(meta), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if overwrite_index:
        entradas = [e for e in _leer_index(root) if e.get("snapshot_id") != sid]
        entradas.append(asdict(meta))
        _escribir_index(root, entradas)
    return meta


def _leer_meta(carpeta: Path) -> SnapshotMeta | None:
    ruta = carpeta / "metadata.json"
    if not ruta.exists():
        return None
    data = json.loads(ruta.read_text(encoding="utf-8"))
    return SnapshotMeta(**data)


def load_snapshot(root: Path, snapshot_id: str) -> tuple[MeteoFrame, SnapshotMeta]:
    """Relee un snapshot del disco y reconstruye su `MeteoFrame`."""
    carpeta = Path(root) / snapshot_id
    meta = _leer_meta(carpeta)
    if meta is None:
        raise FileNotFoundError(f"No existe el snapshot {snapshot_id} en {root}")
    with open(carpeta / "normalizado.csv", "r", encoding="utf-8", newline="") as fh:
        filas = list(csv.DictReader(fh))
    if not filas:
        raise ValueError(f"El snapshot {snapshot_id} no tiene filas.")

    def col(nombre: str) -> list[float]:
        return [float(fila[nombre]) for fila in filas]

    frame = MeteoFrame(
        source=meta.source,
        issued_at=meta.issued_at,
        fetched_at=meta.fetched_at,
        latitude=meta.latitude,
        longitude=meta.longitude,
        timezone=meta.timezone,
        model=meta.model,
        times=[fila["time"] for fila in filas],
        temperature_C=col("temperature_2m"),
        humidity_pct=col("relative_humidity_2m"),
        wind_ms=col("wind_speed_10m"),
        solar_W_m2=col("shortwave_radiation"),
        cloud_pct=col("cloud_cover"),
        precip_mm=col("precipitation"),
        endpoint=meta.endpoint,
        raw=(carpeta / meta.files.get("raw", "raw.json")).read_bytes(),
        notes=meta.notes,
    )
    return frame, meta


def latest_snapshot(root: Path, source: str | None = None) -> SnapshotMeta | None:
    """Snapshot mas reciente del indice, opcionalmente filtrado por fuente."""
    entradas = [e for e in _leer_index(Path(root)) if source is None or e.get("source") == source]
    if not entradas:
        return None
    return SnapshotMeta(**max(entradas, key=lambda e: e.get("fetched_at", "")))


def verify(root: Path) -> list[str]:
    """Verifica hashes contra el indice; devuelve la lista de snapshots OK.

    Lanza `ValueError` si un archivo falta o no coincide con su hash.
    """
    root = Path(root)
    entradas = _leer_index(root)
    problemas: list[str] = []
    ok: list[str] = []
    for entrada in entradas:
        sid = entrada["snapshot_id"]
        carpeta = root / sid
        for clave, nombre in (entrada.get("files") or {}).items():
            ruta = carpeta / nombre
            esperado = entrada.get(f"sha256_{clave}")
            if esperado is None:
                continue
            if not ruta.exists():
                problemas.append(f"{sid}: falta {nombre}")
                continue
            obtenido = sha256_file(ruta)
            if obtenido != esperado:
                problemas.append(f"{sid}: hash distinto en {nombre}")
        if not any(p.startswith(f"{sid}:") for p in problemas):
            ok.append(sid)
    if problemas:
        raise ValueError("Snapshots alterados o incompletos: " + "; ".join(problemas))
    return ok


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
