from itertools import product


with open("rus.txt", 'r', encoding='utf-8') as f:
    dictionary = {line.strip() for line in f}  # добавляем каждое слово в set


# Функция для генерации всех возможных комбинаций и проверки существования слова
def generate_real_words(required_chars=None, excluded_chars=None, required_positions=None, excluded_positions=None):
    russian_alphabet = 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'
    real_words = []

    # Устанавливаем значения по умолчанию, если не указаны
    required_chars = required_chars or ""
    excluded_chars = excluded_chars or ""
    required_positions = required_positions or {}
    excluded_positions = excluded_positions or {}

    # Генерация всех возможных комбинаций длиной 5 из русского алфавита
    for combo in product(russian_alphabet, repeat=5):
        word = ''.join(combo)

        print('\rКомбинация: ' + word, end='')

        # Проверяем наличие обязательных символов
        if all(char in word for char in required_chars) and \
                not any(char in word for char in excluded_chars):

            # Проверяем позиции для обязательных символов
            if all(word[pos-1] == char for pos, char in required_positions.items()) and \
                    all(not any(word[pos - 1] == char for char in chars) for pos, chars in excluded_positions.items()):

                # Проверяем, является ли комбинация реальным словом
                if word in dictionary:

                    real_words.append(word)

    return real_words


# Запуск функции и вывод найденных слов
required = "ре"  # Обязательный символ
excluded = "хокспитлавк"  # Символ, которого не должно быть
required_positions = {3: 'р'}  #
excluded_positions = {4: 'е'}  # 1: 'н', 2: 'ае', 3: 'н', 4: 'ает', 5: 'а' нумерация с 1

found_words = generate_real_words(
    required_chars=required,
    excluded_chars=excluded,
    required_positions=required_positions,
    excluded_positions=excluded_positions
)
print(f"\rНайденные слова ({len(found_words)}):")
for word in found_words:
    print(word)
