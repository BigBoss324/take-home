"""
Tests unitarios para el módulo de validación de RUT chileno (Módulo 11).
Cubre: formatos con puntos/guiones, RUTs válidos del dataset real, 
casos borde (vacío, solo letras, DV='K', DV='0'), y RUTs inválidos conocidos.
"""
import pytest
from src.validator import is_valid_rut, clean_rut


# ============================================================
# Tests para clean_rut()
# ============================================================

class TestCleanRut:
    def test_remueve_puntos_y_guiones(self):
        assert clean_rut("12.345.678-9") == "123456789"

    def test_remueve_espacios(self):
        assert clean_rut(" 12345678 9 ") == "123456789"

    def test_convierte_k_minuscula_a_mayuscula(self):
        assert clean_rut("44444441-k") == "44444441K"

    def test_ya_limpio(self):
        assert clean_rut("123456789") == "123456789"

    def test_formato_mixto_completo(self):
        assert clean_rut("  2.037.289-3  ") == "20372893"


# ============================================================
# Tests para is_valid_rut()
# ============================================================

class TestIsValidRut:
    """Valida el algoritmo Módulo 11 contra casos reales y sintéticos."""

    # --- Casos válidos del dataset de entrada real ---
    @pytest.mark.parametrize("rut", [
        "2037289-3",
        "4346663-1",
        "4286678-4",
        "4108520-7",
        "5084436-6",
        "4596828-6",
        "5781261-3",
        "6105425-1",
        "7683970-0",
        "3418354-6",
    ])
    def test_ruts_validos_del_dataset(self, rut):
        assert is_valid_rut(rut) is True, f"Se esperaba que {rut} fuera válido"

    # --- Caso borde: DV = K ---
    def test_rut_valido_con_dv_k(self):
        # 44444441-K: suma=122, 122%11=1, 11-1=10 → K
        assert is_valid_rut("44444441-K") is True

    def test_rut_valido_con_dv_k_minuscula(self):
        assert is_valid_rut("44444441-k") is True

    # --- Caso borde: DV = 0 (cuando 11-resto=11) ---
    def test_rut_valido_con_dv_cero(self):
        # 10000004-0: suma=11, 11%11=0, 11-0=11 → '0'
        assert is_valid_rut("10000004-0") is True

    # --- Formato con puntos de miles ---
    def test_rut_valido_con_puntos(self):
        assert is_valid_rut("2.037.289-3") is True

    # --- Casos inválidos del dataset de entrada real ---
    def test_rut_invalido_dv_incorrecto(self):
        # 12.345.678-9: DV correcto es 5, no 9
        assert is_valid_rut("12.345.678-9") is False

    def test_rut_invalido_segundo(self):
        # 76543210-0: DV correcto es 3, no 0
        assert is_valid_rut("76543210-0") is False

    # --- Casos borde ---
    def test_string_vacio(self):
        assert is_valid_rut("") is False

    def test_un_solo_caracter(self):
        assert is_valid_rut("5") is False

    def test_solo_letras(self):
        assert is_valid_rut("abcdefgh") is False

    def test_none_como_string(self):
        assert is_valid_rut("None") is False
