import random
import time


def retry_decorator(attempts, exceptions, delay=0):
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    print(f"Попытка {attempt} не удалась: {repr(e)}. Повтор...")
                    last_exception = e
                    time.sleep(delay)  # Имитация задержки перед новой попыткой
            raise last_exception  # Если исчерпаны все попытки, выбрасываем последнее исключение
        return wrapper
    return decorator


def test_always_error(first, second):
    @retry_decorator(attempts=5, exceptions=(ValueError, KeyError), delay=1)
    def retry_test():
        if random.random() < 0.8:  # Ошибка с вероятностью 80%
            raise random.choice([ValueError("Ошибка значения"), KeyError("Ошибка ключа")])
        return first + second
    return retry_test()
