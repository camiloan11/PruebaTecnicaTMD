# Mi API en Python con Docker

API creada con **FastAPI**, que lee datos desde un archivo CSV y permite consultar usuarios.

## Endpoints

- `GET /usuarios` → Devuelve todos los usuarios.
- `GET /usuarios/{usuario_id}` → Busca un usuario por id.
- `GET /buscar?nombre=Ana&ciudad=Madrid` → Filtra usuarios por nombre y ciudad.
- Documentación automática: `http://localhost:8000/docs`

## Docker

Construir imagen:

```bash
docker build -t mi_api .
