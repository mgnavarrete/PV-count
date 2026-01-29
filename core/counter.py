"""
Lógica principal del contador.
"""


class Counter:
    """
    Clase principal para manejar el contador.
    """
    
    def __init__(self, initial_value=0):
        """
        Inicializa el contador.
        
        Args:
            initial_value (int): Valor inicial del contador
        """
        self.value = initial_value
    
    def increment(self, step=1):
        """
        Incrementa el contador.
        
        Args:
            step (int): Cantidad a incrementar
        """
        self.value += step
    
    def decrement(self, step=1):
        """
        Decrementa el contador.
        
        Args:
            step (int): Cantidad a decrementar
        """
        self.value -= step
    
    def reset(self):
        """Reinicia el contador a cero."""
        self.value = 0
    
    def get_value(self):
        """
        Obtiene el valor actual del contador.
        
        Returns:
            int: Valor actual
        """
        return self.value

