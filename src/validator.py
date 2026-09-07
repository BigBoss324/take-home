import re

def clean_rut(rut: str) -> str:
    """Limpia el RUT removiendo puntos, guiones y espacios."""
    return re.sub(r'[^0-9kK]', '', str(rut).upper())

def is_valid_rut(rut: str) -> bool:
    """Valida el dígito verificador de un RUT chileno usando Módulo 11."""
    cleaned = clean_rut(rut)
    if len(cleaned) < 2:
        return False
    
    body = cleaned[:-1]
    dv_expected = cleaned[-1]
    
    if not body.isdigit():
        return False
        
    # Algoritmo Módulo 11
    suma = 0
    multiplo = 2
    for char in reversed(body):
        suma += int(char) * multiplo
        multiplo += 1
        if multiplo == 8:
            multiplo = 2
            
    resto = suma % 11
    dv_calculated = str(11 - resto)
    
    if dv_calculated == '11':
        dv_calculated = '0'
    elif dv_calculated == '10':
        dv_calculated = 'K'
        
    return dv_calculated == dv_expected
