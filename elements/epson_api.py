from requests import get, post, put, delete
from requests.exceptions import ConnectionError

headers = {
    'Content-Type': "",
    "Access-Control-Allow-Origin": "*",
    "accept": "*/*"
}


class EpsonAPI:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def get_power_status(self, ip_address: str):
        """
        Получение информации о текущем статусе работы проектора
        :param ip_address: ip-адрес проектора
        :return:
        """
        url = f"{self.base_url.format(ip_address)}/control/escvp21"
        params = {'cmd': 'PWR'}

        try:
            response = get(url=url, params=params, timeout=(3, 3))
            return response.json()
        except ConnectionError as e:
            print("error: ", e)
            return None

    def switch_on(self, ip_address: str):
        """
        отправляет запрос на включение проекторов из списка
        :param ip_address: ip-адрес проектора
        :return:
        """
        url = f"{self.base_url.format(ip_address)}/contentmgr/remote/on"
        try:
            response = get(url=url, timeout=(3, 3))
            return response.json()
        except ConnectionError as e:
            print("error: ", e)
            return None

    def switch_off(self, ip_address: str):
        """
        отправляет запрос на выключение проекторов из списка
        :param ip_address: ip-адрес проектора
        :return:
        """
        url = f"{self.base_url.format(ip_address)}/contentmgr/remote/off"
        try:
            response = get(url=url, timeout=(3, 3))
            return response.json()
        except ConnectionError as e:
            print("error: ", e)
            return None
