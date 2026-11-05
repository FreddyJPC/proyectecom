"""
Habla con la base real (la de prueba local): el repositorio es SQL crudo y
no hay forma útil de probar el upsert sin Postgres detrás. Solo toca la fila
id=1 de `latido`, que existe únicamente para esto, y la deja funcional.
"""
from src.config.database import get_connection
from src.jobs.latido.repository import LatidoRepository


def _leer_fila():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select ultimo_latido, contador from latido where id = 1")
            return cur.fetchone()


class TestLatidoRepository:
    def test_cada_latido_sube_el_contador_y_actualiza_la_fecha(self):
        _, contador_antes = LatidoRepository.registrar_latido()

        momento, contador = LatidoRepository.registrar_latido()

        assert contador == contador_antes + 1
        assert _leer_fila() == (momento, contador)

    def test_si_la_fila_no_existe_la_recrea(self):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("delete from latido where id = 1")

        _, contador = LatidoRepository.registrar_latido()

        assert contador == 0
        assert _leer_fila() is not None

    def test_sigue_siendo_una_sola_fila(self):
        LatidoRepository.registrar_latido()
        LatidoRepository.registrar_latido()

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select count(*) from latido")
                assert cur.fetchone()[0] == 1
