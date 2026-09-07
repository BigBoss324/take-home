"""
Tests unitarios para el clasificador de rubros (lógica de negocio multi-giro).
Usa un mapa de rubros mock para aislar la lógica del CSV real.
Cubre: giro único, multi-giro con prioridad, giros no mapeados,
giros inválidos, y combinaciones mixtas.
"""
import pytest
import csv
from src.classifier import RubrosClassifier


@pytest.fixture
def mapa_csv(tmp_path):
    """Crea un mapa de rubros temporal para testing (no depende del CSV real)."""
    csv_path = tmp_path / "mapa_rubros_test.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['codigo_giro', 'descripcion', 'familia', 'prioridad'])
        writer.writerow([692000, 'CONTABILIDAD', 'contador', 1])
        writer.writerow([702000, 'CONSULTORIA DE GESTION', 'contador', 1])
        writer.writerow([492300, 'TRANSPORTE DE CARGA', 'pyme', 2])
        writer.writerow([410010, 'CONSTRUCCION RESIDENCIAL', 'pyme', 2])
        writer.writerow([643000, 'FONDOS DE INVERSION', 'otro', 3])
    return str(csv_path)


@pytest.fixture
def classifier(mapa_csv):
    """Instancia del clasificador con mapa mock."""
    return RubrosClassifier(mapa_csv)


# ============================================================
# Tests de clasificación
# ============================================================

class TestGetTipologia:

    # --- Giro único ---
    def test_giro_unico_contador(self, classifier):
        result = classifier.get_tipologia(['692000'])
        assert result['familia'] == 'contador'
        assert result['multi_giro'] is False
        assert result['codigo_ganador'] == 692000

    def test_giro_unico_pyme(self, classifier):
        result = classifier.get_tipologia(['492300'])
        assert result['familia'] == 'pyme'
        assert result['multi_giro'] is False
        assert result['codigo_ganador'] == 492300

    def test_giro_unico_otro(self, classifier):
        result = classifier.get_tipologia(['643000'])
        assert result['familia'] == 'otro'
        assert result['codigo_ganador'] == 643000

    # --- Multi-giro: gana la prioridad mínima ---
    def test_multi_giro_contador_gana_sobre_pyme(self, classifier):
        """Prioridad 1 (contador) debe ganar sobre prioridad 2 (pyme)."""
        result = classifier.get_tipologia(['492300', '692000'])
        assert result['familia'] == 'contador'
        assert result['multi_giro'] is True
        assert result['codigo_ganador'] == 692000

    def test_multi_giro_pyme_gana_sobre_otro(self, classifier):
        """Prioridad 2 (pyme) debe ganar sobre prioridad 3 (otro)."""
        result = classifier.get_tipologia(['643000', '410010'])
        assert result['familia'] == 'pyme'
        assert result['multi_giro'] is True
        assert result['codigo_ganador'] == 410010

    def test_multi_giro_tres_familias(self, classifier):
        """Con giros de las 3 familias, gana contador (prioridad 1)."""
        result = classifier.get_tipologia(['643000', '492300', '692000'])
        assert result['familia'] == 'contador'
        assert result['multi_giro'] is True

    def test_multi_giro_misma_familia(self, classifier):
        """Dos giros de la misma familia, sigue siendo multi_giro."""
        result = classifier.get_tipologia(['692000', '702000'])
        assert result['familia'] == 'contador'
        assert result['multi_giro'] is True

    # --- Sin giros / giros vacíos ---
    def test_lista_vacia_retorna_sin_clasificar(self, classifier):
        result = classifier.get_tipologia([])
        assert result['familia'] == 'otro / sin_clasificar'
        assert result['codigo_ganador'] is None
        assert result['multi_giro'] is False

    # --- Giros no mapeados ---
    def test_giros_no_mapeados(self, classifier):
        """Giros que no existen en el mapa → sin_clasificar."""
        result = classifier.get_tipologia(['999999', '888888'])
        assert result['familia'] == 'otro / sin_clasificar'
        assert result['multi_giro'] is True
        assert result['codigo_ganador'] is None

    def test_giro_unico_no_mapeado(self, classifier):
        result = classifier.get_tipologia(['111111'])
        assert result['familia'] == 'otro / sin_clasificar'
        assert result['multi_giro'] is False

    # --- Giros inválidos (no numéricos) ---
    def test_giros_no_numericos(self, classifier):
        result = classifier.get_tipologia(['abc', 'xyz', '!!!'])
        assert result['familia'] == 'otro / sin_clasificar'
        assert result['motivo'] == 'Giros inválidos o no numéricos'

    # --- Combinaciones mixtas ---
    def test_mezcla_valido_e_invalido(self, classifier):
        """Un giro válido + basura → clasifica con el válido."""
        result = classifier.get_tipologia(['abc', '692000', 'xyz'])
        assert result['familia'] == 'contador'
        assert result['multi_giro'] is False  # Solo 1 giro parseable

    def test_mezcla_mapeado_y_no_mapeado(self, classifier):
        """Un giro mapeado + uno no mapeado → clasifica con el mapeado."""
        result = classifier.get_tipologia(['692000', '999999'])
        assert result['familia'] == 'contador'
        assert result['multi_giro'] is True  # 2 giros válidos numéricamente


# ============================================================
# Tests de inicialización
# ============================================================

class TestRubrosClassifierInit:

    def test_carga_csv_correctamente(self, classifier):
        assert len(classifier.df_mapa) == 5

    def test_tipos_correctos(self, classifier):
        assert classifier.df_mapa['codigo_giro'].dtype == int
        assert classifier.df_mapa['prioridad'].dtype == int

    def test_csv_inexistente_lanza_excepcion(self):
        with pytest.raises(Exception):
            RubrosClassifier("/ruta/inexistente/mapa.csv")
