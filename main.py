"""
Punto de entrada principal de la aplicación CounterV01.
"""
from core.counter import Counter


def main():
    """Función principal de la aplicación."""
    print("CounterV01 - Aplicación iniciada")
    
    # Ejemplo de uso
    counter = Counter(initial_value=0)
    print(f"Valor inicial: {counter.get_value()}")
    
    counter.increment()
    print(f"Después de incrementar: {counter.get_value()}")
    
    counter.increment(5)
    print(f"Después de incrementar 5: {counter.get_value()}")
    
    counter.decrement(2)
    print(f"Después de decrementar 2: {counter.get_value()}")


if __name__ == "__main__":
    main()

