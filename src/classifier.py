import pandas as pd
import logging

logger = logging.getLogger(__name__)

class RubrosClassifier:
    def __init__(self, mapa_csv_path: str):
        """Carga el DataFrame del mapa de rubros en memoria al inicio para mejor rendimiento."""
        try:
            self.df_mapa = pd.read_csv(mapa_csv_path)
            # Asegurar tipos
            self.df_mapa['codigo_giro'] = self.df_mapa['codigo_giro'].astype(int)
            self.df_mapa['prioridad'] = self.df_mapa['prioridad'].astype(int)
        except Exception as e:
            logger.error(f"Error cargando mapa de rubros {mapa_csv_path}: {e}")
            raise

    def get_tipologia(self, giros: list[str]) -> dict:
        """
        Cruza los giros obtenidos con el Dataframe en memoria.
        Regla de negocio: En caso de multi-giro, gana el que tenga menor valor en "prioridad".
        """
        giros_validos = []
        for g in giros:
            try:
                giros_validos.append(int(g))
            except ValueError:
                pass
                
        if not giros_validos:
            return {
                'familia': 'otro / sin_clasificar', 
                'motivo': 'Giros inválidos o no numéricos',
                'multi_giro': False,
                'codigo_ganador': None
            }
            
        # Filtrar mapa con los giros del RUT
        df_matches = self.df_mapa[self.df_mapa['codigo_giro'].isin(giros_validos)]
        
        if df_matches.empty:
            return {
                'familia': 'otro / sin_clasificar',
                'motivo': 'Ningún giro encontrado en el mapa',
                'multi_giro': len(giros_validos) > 1,
                'codigo_ganador': None
            }
            
        # Aplicamos regla estricta: MINIMO de prioridad
        best_match = df_matches.loc[df_matches['prioridad'].idxmin()]
        
        return {
            'familia': best_match['familia'],
            'motivo': f"Regla Prioridad ({int(best_match['prioridad'])})",
            'multi_giro': len(giros_validos) > 1,
            'codigo_ganador': int(best_match['codigo_giro'])
        }
