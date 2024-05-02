from requests import get, post, put, delete
from requests.exceptions import ConnectionError

headers = {
    'Content-Type': "",
    "Access-Control-Allow-Origin": "*",
    "accept": "*/*"
}


class ResolumeAPI:
    def __init__(self, base_url):
        self.base_url = base_url

    def load_element(self, layer: int, clip: int, filepath: str):
        """
        Загрузка элемента на определённый индекс слоя и индекс клипа
        :param filepath: путь к файлу
        :param layer: индекс слоя
        :param clip: индекс клипа
        :return:
        """
        url = f"{self.base_url}/layers/{layer + 1}/clips/{clip + 1}/open"
        print(url)
        print(filepath)
        header = headers
        header['Content-Type'] = 'text/plain'

        try:
            response = post(
                url=url,
                headers=headers,
                data=filepath
            )
        except ConnectionError:
            return None
        return response.status_code

    def open_selected_clip(self):
        """
        Открытие выбранного элемента после загрузки
        :return:
        """
        url = f"{self.base_url}/clips/selected/connect"
        header = headers
        header['Content-Type'] = 'application/json'
        try:
            post(
                url=url,
                headers=header
            )
        except ConnectionError:
            return None

    def get_layer_elements(self, index: int):
        """
        Получение списка элементов слоя по индексу слоя
        :param index: индекс слоя
        :return:
        """
        url = f"{self.base_url}/layers/{index + 1}"
        header = headers
        header['Content-Type'] = 'application/json'

        try:
            response = get(
                url=url,
                headers=header,
            )
        except ConnectionError:
            return None

        return response.json()

    def open_element(self, layer: int, clip: int):
        """
        Подключение к элементу по индексу слоя и индексу элемента
        :param filepath: путь к файлу
        :param layer: индекс слоя
        :param clip: индекс клипа
        :return:
        """
        url = f"{self.base_url}/layers/{layer + 1}/clips/{clip + 1}/connect"
        header = headers
        header['Content-Type'] = 'application/json'

        try:
            post(
                url=url,
                headers=headers
            )
        except ConnectionError:
            return None

    def clear_layer(self, layer: int):
        """
        Выключение элементов слоя по индексу слоя
        :param layer: индекс слоя
        :return:
        """
        url = f"{self.base_url}/layers/{layer + 1}/clear"
        header = headers
        header['Content-Type'] = 'application/json'

        try:
            post(
                url=url,
                headers=header
            )
        except ConnectionError:
            return None

    def get_layers_info(self):
        """
        Получение списка всех слоёв проекта
        :return:
        """
        header = headers
        header['Content-Type'] = 'application/json'

        try:
            response = get(
                url=self.base_url,
                headers=header
            )
        except ConnectionError:
            return None

        return response.json()

    def get_clip_info(self, clip_id: int):
        """
        Получение информации о клипе по id клипа
        :param clip_id: id клипа
        :return:
        """
        url = f"{self.base_url}/clips/by-id/{clip_id}"
        header = headers
        header['Content-Type'] = 'application/json'

        try:
            response = get(
                url=url,
                headers=header
            )
        except ConnectionError:
            return None

        return response.json()

    def update_clip_info(self, clip_id: int, data):
        """
        Обновление параметров элемента
        :return:
        """
        url = f"{self.base_url}/clips/by-id/{clip_id}"
        header = headers
        header['Content-Type'] = 'application/json'
        response = put(
            url=url,
            headers=header,
            data=data
        )
        print(data)
        print(response.status_code, response.text, response.content)