import logging
import math
import socket
import subprocess
import time

import flet as ft
import psutil
import requests
import os
import json
from dotenv import load_dotenv
from datetime import datetime

import functions

script_path = os.path.abspath(__file__)
script_directory = os.path.dirname(script_path)
os.chdir(script_directory)
project_folder = os.getcwd()
load_dotenv()

config = functions.load_config_file('config.json')
control_data = config['control']
paths_data = config['paths']

url_base = control_data['base_url'].format(control_data['host'], control_data['port'])


# to-do
# Страница с настройками (изменение параметров и последующая перезагрузка, кнопка для обновления)
# Работа с проекторами
# Выключение Resolume
# Оптимизация кода (?)
# Перенос текста в отдельный файл

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


def is_running(process_name: str):
    # Проверка наличия процесса в диспетчере задач

    for a in psutil.process_iter(['pid', 'name']):
        if a.name().split('.')[0] == process_name:
            return True
    return False


def make_request(request_method: str, url: str, headers, data=None, files=None, params=None):
    # Отправка HTTP запроса

    response = requests.request(
        method=request_method,
        url=url,
        headers=headers,
        data=data,
        files=files,
        params=params
    )

    return response


def send_error_message(location: str, error_text: str, extra: str = "отсутствует"):
    url = f"https://api.telegram.org/bot{os.getenv('BOT_TOKEN')}/sendMessage"
    text = f"{location}\n{error_text}\n\nДополнительное содержание: {extra}" \
        .replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("`", "\\`")
    data = {
        'chat_id': os.getenv('ID_GROUP_ERRORS'),
        'text': text,
        'parse_mode': 'Markdown'
    }
    api_response = make_request('POST', url, params=data, headers=None, files=None)
    if api_response.status_code != 200:
        logging.error(f"[{send_error_message.__name__}] Ошибка при отправке сообщения в Telegram")
        logging.error(f"[{send_error_message.__name__}] URL: {url}")
        logging.error(f"[{send_error_message.__name__}] Ошибка: {api_response.text}")


def main(page: ft.Page):
    page.title = "Control"
    page.window_width = 377
    page.window_height = 768
    page.client_storage.clear()
    page.theme = ft.Theme(
        font_family="Geologica",
        color_scheme=ft.ColorScheme(
            primary=ft.colors.WHITE
        )
    )
    page.fonts = {
        "Geologica": "fonts/Geologica.ttf",
    }
    page.theme_mode = ft.ThemeMode.DARK
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.update()

    main_appbar = ft.AppBar(
        actions=[
            ft.Container(
                ft.Row(
                    [
                        ft.IconButton(ft.icons.SCREEN_SHARE_ROUNDED, on_click=lambda _: open_dialog(dialog_proj)),
                        ft.IconButton(ft.icons.RESTART_ALT_ROUNDED, on_click=lambda _: update_control()),
                        ft.IconButton(ft.icons.POWER_SETTINGS_NEW_ROUNDED,
                                      on_click=lambda _: open_dialog(dialog_power_menu))
                    ]
                ),
                margin=ft.margin.only(right=10)
            )
        ],
        leading=ft.IconButton(
            icon=ft.icons.LOGOUT_ROUNDED,
            rotate=math.pi,
            on_click=lambda _: logout(),
            tooltip="Выйти"
        )
    )

    text_params = {
        'dialog_title': {
            'size': 20,
            'weight': ft.FontWeight.W_700
        }
    }

    layers_info = {}
    layer_panel = {}
    rr = ft.ResponsiveRow()

    main_panel = ft.ExpansionPanelList()

    screen_panel = ft.ExpansionPanel(
        expanded=False,
        header=ft.ListTile(title=ft.Text(f"HDMI", weight=ft.FontWeight.W_500)),
        content=ft.Column()
    )

    walls_panel = ft.ExpansionPanel(
        expanded=False,
        header=ft.ListTile(title=ft.Text(f"Стены", weight=ft.FontWeight.W_500)),
        content=ft.Column()
    )

    fons_panel = ft.ExpansionPanel(
        expanded=False,
        header=ft.ListTile(title=ft.Text(f"Фоны", weight=ft.FontWeight.W_500)),
        content=ft.Column()
    )

    logos_panel = ft.ExpansionPanel(
        expanded=False,
        header=ft.ListTile(title=ft.Text(f"Логотипы", weight=ft.FontWeight.W_500)),
        content=ft.Column()
    )

    layer_types = {
        # Соотношение панелей и названий из Resolume

        "WALLS": walls_panel,
        "FONS": fons_panel,
        "ЭКРАНЫ": screen_panel,
        "ЛОГОТИПЫ": logos_panel

    }

    def open_sb(text: str, bgcolor=ft.colors.WHITE):
        if bgcolor != ft.colors.WHITE:
            text_color = ft.colors.WHITE
        else:
            text_color = ft.colors.BLACK

        content = ft.Text(text, size=18, text_align=ft.TextAlign.START, weight=ft.FontWeight.W_500, color=text_color)
        page.snack_bar = ft.SnackBar(
            content=content,
            duration=1200,
            bgcolor=bgcolor
        )
        page.snack_bar.open = True
        page.update()

    def open_loading_sb(text: str = "Загрузка"):
        page.snack_bar = ft.SnackBar(
            content=ft.Row(
                [
                    ft.ProgressRing(color=ft.colors.BLACK, scale=0.6),
                    ft.Text(text, size=18, weight=ft.FontWeight.W_400)
                ]
            ),
            duration=1000
        )
        page.snack_bar.open = True
        page.update()

    def load_exe(exe_name: str):
        # Поиск и запуск исполняемых файлов

        logging.info(f"Поиск процесса {exe_name}.exe")
        if is_running(exe_name):
            logging.info(f"Процесс {exe_name}.exe обнаружен")
            if exe_name == 'Arena':
                change_screen('control')
        else:
            logging.info(f"Процесс {exe_name}.exe не обнаружен")
            if exe_name == 'Arena':
                open_dialog(dialog_resolume_start_menu)

    def login():
        true_password = os.getenv('PANEL_PASSWORD')
        if login_field.value == true_password:
            open_loading_sb()
            load_exe('Arena')
        else:
            open_sb("Неверный код")
        login_field.value = ""
        page.update()

    def logout():
        login_field.value = ""
        change_screen('login')

    def change_screen(target: str):
        page.controls.clear()

        if target == "login":
            page.add(ft.Container(login_col))
            page.appbar = None
            page.scroll = None

        elif target == "control":
            page.add(control_screen)
            page.appbar = main_appbar
            page.scroll = ft.ScrollMode.ADAPTIVE
            update_control()

        page.update()

    def upload_new_element(layer_index, file):
        # Загрузка нового элемента

        logging.info(f"[{upload_new_element.__name__}] Загрузка нового элемента: {file}")
        layer_index += 1
        clips = get_layer_clips(layer_index - 1)

        for clip in range(len(clips)):
            if clips[clip]['connected']['value'] == "Empty":
                clip_index = clip + 1
                t = project_folder.replace("\\", "/")
                file_path = f"file:///{t}/assets/uploads/{file}"
                load_url = f"{url_base}/layers/{layer_index}/clips/{clip_index}/open"
                api_response = make_request('POST', load_url, get_headers('text/plain'),
                                            f"file:///{t}/assets/uploads/{file}")

                if api_response.status_code == 204:
                    logging.info(f"[{upload_new_element.__name__}] Элемент загружен в проект {file}")
                    open_clip(layer_index, clip_index, file)
                else:
                    close_dialog(dialog_loading)
                    logging.error(f"[{upload_new_element.__name__}] Элемент не загружен в проект: {file}")
                    open_sb("Элемент не загружен", ft.colors.RED_ACCENT_200)
                    send_error_message(
                        location=upload_new_element.__name__,
                        error_text=f"Элемент {file} не загружен в проект: {api_response.text}",
                        extra=f"{load_url}\n{file_path}",
                    )

                break

    def save_element(e: ft.ControlEvent):
        # Загрузка нового элемента в директорию

        logging.info(f"[{save_element.__name__}] Загрузка нового элемента в директорию")
        layer_index = e.control.data
        upload_list = []
        if element_picker.result is not None and element_picker.result.files is not None:
            open_dialog(dialog_loading)
            # open_loading_snackbar(f"Загружаем {make_text_smaller(element_picker.result.files[-1].name)}")
            for f in element_picker.result.files:
                upload_list.append(
                    ft.FilePickerUploadFile(
                        f.name,
                        upload_url=page.get_upload_url(f.name, 60),
                    )
                )
            element_picker.upload(upload_list)
            logging.info(f"[{save_element.__name__}] Загрузка нового элемента в директорию завершена")
            time.sleep(2)
            upload_new_element(layer_index, element_picker.result.files[-1].name)
        else:
            logging.info(f"[{save_element.__name__}] Загрузка нового элемента в директорию отменена")

    def on_uploading_element(e: ft.FilePickerUploadEvent):
        logging.info(f"[{save_element.__name__}] Загружено: {int(e.progress * 100)}%")
        dialog_loading.content.controls[2] = ft.Text(f"{int(e.progress * 100)}% / 100%", size=18)
        page.update()

    element_picker = ft.FilePicker(on_result=save_element, on_upload=on_uploading_element)

    def open_element_picker(e):
        # hf.medium_impact()
        layer_index = e.control.data
        page.overlay.append(element_picker)
        page.update()
        element_picker.data = layer_index
        element_picker.pick_files(
            allow_multiple=False,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=['jpg', 'jpeg', 'png', 'mp4', 'avi', 'mov']
        )

    def update_control():
        # Обновление экрана управления КЗ

        logging.info('Обновление данных Resolume')
        # hf.medium_impact()
        open_loading_sb("Обновляем проект")
        rr.controls.clear()
        walls_panel.content.controls, fons_panel.content.controls, screen_panel.content.controls, logos_panel.content.controls = [], [], [], []
        main_panel.controls = [
            screen_panel,
            fons_panel,
            walls_panel,
            logos_panel
        ]
        control_screen.controls.clear()
        control_screen.controls.append(main_panel)

        layers_list = get_layers()

        for layer_index in range(len(layers_list) - 1, -1, -1):
            layer_name = layers_list[layer_index]['name']['value']
            try:
                current_panel = layer_types[layer_name[1:layer_name.find(']')]]
            except KeyError:
                open_dialog(dialog_loading)
                time.sleep(2)
                close_dialog(dialog_loading)
                update_control()

            layer_panel[layer_index + 1] = current_panel
            clips = get_layer_clips(layer_index)
            current_panel.content.controls.append(
                ft.Card(
                    ft.Column(
                        controls=[
                            ft.Container(
                                ft.Row(
                                    controls=[
                                        ft.Text(layers_list[layer_index]['name']['value'].split("]")[-1][1:], size=19,
                                                text_align=ft.TextAlign.CENTER)
                                    ],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                ),
                                padding=20
                            ),
                            ft.Container(
                                content=ft.Row([ft.Text("---", size=16), ft.ProgressRing(visible=False, scale=0.5)],
                                               alignment=ft.MainAxisAlignment.CENTER, height=50),
                                padding=-15
                            ),
                            ft.Container(
                                ft.Row(
                                    controls=[
                                        ft.IconButton(ft.icons.ADD_ROUNDED, on_click=open_element_picker,
                                                      data=layer_index),
                                        ft.IconButton(icon=ft.icons.EDIT_ROUNDED, on_click=control_btn_pressed,
                                                      data=f"edit_{layer_index + 1}_{layers_list[layer_index]['id']}"
                                                      ),
                                        ft.IconButton(icon=ft.icons.KEYBOARD_ARROW_LEFT_OUTLINED,
                                                      on_click=control_btn_pressed,
                                                      data=f"prev_{layer_index + 1}_{layers_list[layer_index]['id']}"
                                                      ),
                                        ft.IconButton(icon=ft.icons.KEYBOARD_ARROW_RIGHT_OUTLINED,
                                                      on_click=control_btn_pressed,
                                                      data=f"next_{layer_index + 1}_{layers_list[layer_index]['id']}"
                                                      ),
                                        ft.IconButton(icon=ft.icons.VISIBILITY_OFF_OUTLINED,
                                                      on_click=control_btn_pressed,
                                                      data=f"stop_{layer_index + 1}_{layers_list[layer_index]['id']}"
                                                      ),
                                    ],
                                    alignment=ft.MainAxisAlignment.CENTER
                                ),
                                padding=10
                            )
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER
                    ),
                    data=layer_index

                )
            )

            connected_clip = find_connected(clips)
            if not connected_clip:
                layers_info[layers_list[layer_index]['id']] = -1
                current_panel.content.controls[-1].content.controls[1].content.controls[0].value = "---"
                current_panel.content.controls[-1].surface_tint_color = None
            else:
                layers_info[layers_list[layer_index]['id']] = connected_clip[1]

                current_panel.content.controls[-1].content.controls[1].content.controls[0].value = make_text_smaller(
                    connected_clip[0]['name']['value'])
                current_panel.content.controls[-1].surface_tint_color = ft.colors.GREEN
        time.sleep(2)
        page.update()
        close_dialog(dialog_loading)
        open_sb("Данные обновлены", ft.colors.GREEN)

    def open_dialog(dialog: ft.AlertDialog):
        page.dialog = dialog
        dialog.open = True
        page.update()

    def close_dialog(dialog: ft.AlertDialog):
        dialog.open = False
        page.update()

    def make_text_smaller(text):
        # Сокращение длины строки

        if len(text) > 15:
            text = text[:16] + "..."
        return text

    def get_headers(content_type: str):
        # Создание headers для HTTP запроса

        headers = control_data['request_headers']
        headers['Content-Type'] = content_type

        return headers

    def find_connected(clips: {}):
        # Поиск активного элемента среди всех элементов слоя
        # [clip, clip_index] / False

        fl = False
        for clip_index in range(len(clips)):
            # print(clips[clip_index]['connected'])
            if clips[clip_index]['connected']['value'] == "Connected":
                fl = True
                return [clips[clip_index], clip_index]
        if not fl:
            return False

    def get_layer_clips(index: int):
        # Получение списка элементов слоя по индексу слоя

        url = f"{url_base}/layers/{index + 1}"
        api_response = make_request('GET', url, get_headers("application/json"))
        data = json.loads(api_response.text)
        print("layer: ", data['name']['value'], "id:", data['id'])
        return data['clips']

    def open_clip(layer_index: int, clip_index: int, file: str):
        # Запуск нового клипа по индексу слоя и индексу клипа

        url = f"{url_base}/layers/{layer_index}/clips/{clip_index}/connect"
        logging.info(f'[{open_clip.__name__}] Запуск нового элемента {url}')
        api_response = make_request('POST', url, get_headers("application/json"))
        close_dialog(dialog_loading)
        if api_response.status_code == 204:
            logging.info(f'[{open_clip.__name__}] Новый элемент открыт: {file}')
            open_sb(f"Элемент загружен", ft.colors.GREEN)
            edit_control_card(layer_index, make_text_smaller(file), ft.colors.GREEN)
        else:
            logging.error(f'[{open_clip.__name__}] Ошибка при подключении к элементу: {api_response.text}')
            open_sb("Ошибка доступа", ft.colors.RED_ACCENT_200)
            send_error_message(
                location=open_clip.__name__,
                error_text=f"Ошибка при подключении к элементу: {api_response.text}",
                extra=url,
            )

    def power_off(e: ft.ControlEvent):
        dest = e.control.data
        if dest == 'layers_off':
            layers = get_layers()
            for index in range(len(layers)):
                url = f"{url_base}/layers/{index + 1}/clear"
                api_response = make_request('POST', url, headers=get_headers("application/json"))
                if api_response.status_code != 204:
                    close_dialog(dialog_loading)
                    open_sb("Ошибка слоя", ft.colors.RED_ACCENT_200)
                    logging.error(f"[{power_off.__name__}] Ошибка при скрытии слоя")
                    logging.error(f"[{power_off.__name__}] URL: {url}")
                    send_error_message(
                        location=power_off.__name__,
                        error_text="Ошибка при скрытии слоя",
                        extra=url
                    )
                    break
                edit_control_card(index + 1, "---")

            close_dialog(dialog_power_menu)
            logging.info(f"[{power_off.__name__}] Все слои скрыты")
            # open_sb("Все слои скрыты", ft.colors.GREEN)

    def get_layers():
        # Получение списка слоёв проекта Resolume

        logging.info(f'[{get_layers.__name__}] Запрос на получение/обновление данных')

        api_response = make_request('GET', url_base, get_headers("application/json"))
        data = json.loads(api_response.text)['layers']

        logging.info(f'[{get_layers.__name__}] Данные получены')
        return data

    def control_btn_pressed(e: ft.ControlEvent):
        # Реакция на кнопки управления элементом слоя
        # hf.medium_impact()()
        request = e.control.data.split("_")
        layer_id = int(request[2])
        cur_clip_index = layers_info[layer_id]
        layer_index = int(request[1])
        action = request[0]

        print(request[0], layer_id, cur_clip_index, layer_index, action)
        if action in ['next', 'prev']:
            show_progress_ring(layer_index, True)
            if action == 'next':
                cur_clip_index += 1
            else:
                if cur_clip_index >= 1:
                    cur_clip_index -= 1
            layers_info[layer_id] = cur_clip_index
            url = f"{url_base}/layers/{layer_index}/clips/{cur_clip_index + 1}/connect"
            api_response = make_request('POST', url, get_headers("application/json"))
            if api_response.status_code != 204:
                logging.error(f"[{control_btn_pressed.__name__}] Ошибка при переключении элементов")
                logging.error(f"[{control_btn_pressed.__name__}] URL: {url}")
                open_sb("Ошибка при переключении", ft.colors.RED_ACCENT_200)
                send_error_message(
                    location=control_btn_pressed.__name__,
                    error_text=f"Ошибка при переключении элементов",
                    extra=url,
                )
            else:
                time.sleep(2)
                clips = get_layer_clips(layer_index - 1)
                connected_clip = find_connected(clips)
                if not connected_clip:
                    pass
                    edit_control_card(layer_index, "Пустой слой")

                else:
                    connected_clip_info = connected_clip[0]
                    edit_control_card(layer_index, make_text_smaller(connected_clip_info['name']['value']),
                                      ft.colors.GREEN)
            show_progress_ring(layer_index, False)

        elif action == 'edit':
            clips = get_layer_clips(layer_index - 1)
            connected_clip = find_connected(clips)
            if not connected_clip:
                open_sb("Сначала выберите элемент")
            else:
                dialog_edit.content = ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row([ft.IconButton(ft.icons.ARROW_UPWARD_ROUNDED, scale=2,
                                                  on_click=edit_clip,
                                                  data=f"Position Y_minus_{connected_clip[0]['id']}"
                                                  )
                                    ],
                                   alignment=ft.MainAxisAlignment.CENTER),
                            ft.Row(
                                [ft.IconButton(ft.icons.ARROW_BACK_ROUNDED, scale=2,
                                               on_click=edit_clip,
                                               data=f"Position X_minus_{connected_clip[0]['id']}"
                                               ),
                                 ft.IconButton(ft.icons.FIT_SCREEN_ROUNDED, scale=2,
                                               on_click=edit_clip,
                                               data=f"center_center_{connected_clip[0]['id']}"
                                               ),
                                 ft.IconButton(ft.icons.ARROW_FORWARD_ROUNDED, scale=2,
                                               on_click=edit_clip,
                                               data=f"Position X_plus_{connected_clip[0]['id']}"
                                               )],
                                alignment=ft.MainAxisAlignment.CENTER,

                            ),
                            ft.Row([ft.IconButton(ft.icons.ARROW_DOWNWARD_ROUNDED, scale=2,
                                                  on_click=edit_clip,
                                                  data=f"Position Y_plus_{connected_clip[0]['id']}"
                                                  )],
                                   alignment=ft.MainAxisAlignment.CENTER),
                            ft.Divider(thickness=1),
                            ft.Row(
                                [
                                    ft.Text("Масштаб", width=100, size=16, weight=ft.FontWeight.W_400),
                                    ft.IconButton(ft.icons.ADD_ROUNDED,
                                                  on_click=edit_clip,
                                                  data=f"Scale_plus_{connected_clip[0]['id']}"
                                                  ),
                                    ft.IconButton(ft.icons.REMOVE_ROUNDED, on_click=edit_clip,
                                                  data=f"Scale_minus_{connected_clip[0]['id']}"
                                                  )
                                ],
                                alignment=ft.MainAxisAlignment.CENTER
                            ),
                            ft.Row(
                                [
                                    ft.Text("Ширина", width=100, size=16, weight=ft.FontWeight.W_400),
                                    ft.IconButton(ft.icons.ADD_ROUNDED,
                                                  on_click=edit_clip,
                                                  data=f"Scale W_plus_{connected_clip[0]['id']}"
                                                  ),
                                    ft.IconButton(ft.icons.REMOVE_ROUNDED, on_click=edit_clip,
                                                  data=f"Scale W_minus_{connected_clip[0]['id']}"
                                                  )
                                ],
                                alignment=ft.MainAxisAlignment.CENTER
                            ),
                            ft.Row(
                                [
                                    ft.Text("Высота", width=100, size=16, weight=ft.FontWeight.W_400),
                                    ft.IconButton(ft.icons.ADD_ROUNDED,
                                                  on_click=edit_clip,
                                                  data=f"Scale H_plus_{connected_clip[0]['id']}"
                                                  ),
                                    ft.IconButton(ft.icons.REMOVE_ROUNDED, on_click=edit_clip,
                                                  data=f"Scale H_minus_{connected_clip[0]['id']}"
                                                  )
                                ],
                                alignment=ft.MainAxisAlignment.CENTER
                            ),
                            # ft.Row([ft.Text("Наклон", width=100, size=16), ft.IconButton(ft.icons.ROTATE_LEFT_ROUNDED),
                            #         ft.IconButton(ft.icons.ROTATE_RIGHT_ROUNDED)], alignment=ft.MainAxisAlignment.CENTER)
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        scroll=ft.ScrollMode.ADAPTIVE
                    ),
                    height=400,
                )
                open_dialog(dialog_edit)
            page.update()

        elif action == 'stop':
            layers_info[layer_id] = -1
            url = f"{url_base}/layers/{layer_index}/clear"
            api_response = make_request('POST', url, get_headers("application/json"))
            if api_response.status_code == 204:
                edit_control_card(layer_index, "---")
            else:
                logging.error(f"[{control_btn_pressed.__name__}] Ошибка при отключении элемента")
                logging.error(f"[{control_btn_pressed.__name__}] URL: {url}")
                open_sb("Ошибка при отключении", ft.colors.RED_ACCENT_200)
                send_error_message(
                    location=control_btn_pressed.__name__,
                    error_text="Ошибка при отключении элемента",
                    extra=url
                )
        page.update()

    def edit_control_card(layer_index: int, text: str, color=None):
        # Изменение свойств карточки слоя

        cur_panel = layer_panel[layer_index]
        cards = cur_panel.content.controls
        for i in range(len(cards)):
            if cards[i].data == layer_index - 1:
                cur_panel.content.controls[i].content.controls[1].content.controls[0].value = text
                cur_panel.content.controls[i].surface_tint_color = color
        page.update()

    def show_progress_ring(layer_index: int, action: bool):
        # Пока кольца загрузки вместо названия элемента
        # слоя во время переключения элементов

        cur_panel = layer_panel[layer_index]
        cards = cur_panel.content.controls
        for i in range(len(cards)):
            if cards[i].data == layer_index - 1:
                cur_panel.content.controls[i].content.controls[1].content.controls[1].visible = action
                cur_panel.content.controls[i].content.controls[1].content.controls[0].visible = not action
        page.update()

    def edit_clip(e: ft.ControlEvent):
        # Изменение свойств выбранного клипа

        # hf.medium_impact()()
        data = e.control.data.split("_")
        steps = {
            "Scale": 10,
            "Scale W": 10,
            "Scale H": 10,
            "Position X": 50,
            "Position Y": 50,
        }
        if data[0] != "center":
            step = steps[data[0]]
        clip_id = data[-1]
        url = f"{url_base}/clips/by-id/{clip_id}"
        old = json.loads(requests.get(url=url, headers=get_headers('application/json')).text)
        del old['video']['effects'][0]['bypassed']
        del old['video']['effects'][0]['mixer']
        del old['video']['sourceparams']
        if data[1] == "plus":
            old['video']['effects'][0]['params'][data[0]]['value'] += step
        elif data[1] == "minus":
            old['video']['effects'][0]['params'][data[0]]['value'] -= step
        elif data[1] == "center":
            old['video']['effects'][0]['params']['Position X']['value'] = 0
            old['video']['effects'][0]['params']['Position Y']['value'] = 0
        old = {"video": old['video']}
        requests.put(url=url, headers=get_headers('application/json'), data=json.dumps(old))

    def start_resolume():
        close_dialog(dialog_resolume_start_menu)
        # hf.medium_impact()
        time_to_open = control_data['start_time']
        percents = 100 / time_to_open

        open_dialog(dialog_loading)
        logging.info(f"Запуск процесса Arena.exe")
        subprocess.Popen(rf"{paths_data['arena']}", creationflags=subprocess.CREATE_NEW_CONSOLE, shell=True)
        for i in range(1, time_to_open + 1):
            dialog_loading.content.controls[2].value = f"{int(percents * i)}%"
            page.update()
            print(i)
            time.sleep(1)

        close_dialog(dialog_loading)
        dialog_loading.content.controls[2].value = ""
        change_screen('control')

    dialog_power_menu = ft.AlertDialog(
        # Диалог с меню выключения

        title=ft.Row(
            [
                ft.Container(ft.Text("Выключение", size=text_params['dialog_title']['size'], weight=text_params['dialog_title']['weight']), expand=True),
                ft.IconButton(ft.icons.CLOSE_ROUNDED, on_click=lambda _: close_dialog(dialog_power_menu))
            ]
        ),
        modal=True,
        content=ft.Text("Выберите необходимое действие", size=17),
        actions=[
            ft.Column(
                controls=[
                    ft.ElevatedButton(
                        text="Скрыть слои",
                        width=350,
                        on_click=power_off,
                        data='layers_off'
                    ),
                    ft.ElevatedButton(
                        text="Закрыть Resolume",
                        width=350,
                        bgcolor=ft.colors.RED
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            )
        ],
        actions_alignment=ft.MainAxisAlignment.CENTER
    )

    dialog_resolume_start_menu = ft.AlertDialog(
        # Диалог с кнопкой запуска Resolume

        modal=True,
        title=ft.Row(
            [
                ft.Container(ft.Text("Resolume", size=text_params['dialog_title']['size'], weight=text_params['dialog_title']['weight']), expand=True),
                ft.IconButton(ft.icons.CLOSE_ROUNDED, on_click=lambda _: close_dialog(dialog_resolume_start_menu))
            ]
        ),
        content=ft.Text(
            "В данный момент Resolume Arena выключена",
            size=17
        ),
        actions=[
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.ElevatedButton(
                                text="Включить",
                                on_click=lambda _: start_resolume(),
                                bgcolor=ft.colors.GREEN
                            )
                        ],
                        alignment=ft.MainAxisAlignment.END
                    ),

                ],
                horizontal_alignment=ft.CrossAxisAlignment.END
            )
        ],
        actions_alignment=ft.MainAxisAlignment.END
    )

    dialog_edit = ft.AlertDialog(
        # Диалог редактирования свойств элемента

        title=ft.Row(
            [
                ft.Container(ft.Text("Свойства", size=text_params['dialog_title']['size'], weight=text_params['dialog_title']['weight']), expand=True),
                ft.IconButton(ft.icons.CLOSE_ROUNDED, on_click=lambda _: close_dialog(dialog_edit))
            ]
        ),
        modal=True

    )

    dialog_proj = ft.AlertDialog(
        # Диалог управления проекторами

        title=ft.Row(
            [
                ft.Container(ft.Text("Проекторы", size=text_params['dialog_title']['size'], weight=text_params['dialog_title']['weight']), expand=True),
                ft.IconButton(ft.icons.CLOSE_ROUNDED, on_click=lambda _: close_dialog(dialog_proj))
            ]
        ),
        modal=True,
        actions=[
            ft.Column(
                [
                    ft.ElevatedButton(
                        width=300,
                        text="Включить",
                        on_click=lambda _: close_dialog(dialog_proj),
                        bgcolor=ft.colors.GREEN

                    ),
                    ft.ElevatedButton(
                        width=300,
                        text="Выключить",
                        on_click=lambda _: close_dialog(dialog_proj)
                    )
                ],

            )
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    dialog_loading = ft.AlertDialog(
        # Диалог с кольцом загрузки

        title=ft.Text(size=20),
        modal=True,
        content=ft.Column(
            controls=[
                ft.ProgressRing(),
                ft.Text("Загружаем", size=20, weight=ft.FontWeight.W_700),
                ft.Text("", size=20, weight=ft.FontWeight.W_500)
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, height=100
        )
    )

    login_field = ft.TextField(
        label="Код доступа", text_align=ft.TextAlign.CENTER,
        width=250,
        height=70,
        on_submit=lambda _: login(),
        keyboard_type=ft.KeyboardType.NUMBER,
        password=True
    )
    button_login = ft.ElevatedButton("Войти", width=250, on_click=lambda _: login(),
                                     disabled=False, height=50,
                                     icon=ft.icons.KEYBOARD_ARROW_RIGHT_ROUNDED)
    login_col = ft.Column(
        controls=[
            ft.Text("Control", size=30, weight=ft.FontWeight.W_700),
            login_field,
            button_login
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True
    )

    control_screen = ft.Column(
        # Экран управления КЗ

        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.START
    )

    if os.getenv('FLET_SECRET_KEY') is None:
        os.environ["FLET_SECRET_KEY"] = os.urandom(12).hex()

    change_screen('login')
    page.update()


if __name__ == "__main__":
    if not is_port_in_use(8502):
        logging.basicConfig(level=logging.INFO,
                            # filename=f"logs/{datetime.now().strftime('%d-%m-%Y-%H-%M')}.log",
                            # filemode="w",
                            format="%(asctime)s %(levelname)s %(message)s",
                            encoding='utf-8'
                            )
        if not is_running('ngrok'):
            subprocess.Popen(
                fr"ngrok.exe http 8502 --domain={os.getenv('NGROK_DOMAIN')}",
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            send_error_message(location="Запуск Ngrok", error_text="Модуль запущен")
        send_error_message(location="Запуск CROD.Control", error_text="Модуль запущен")
        ft.app(
            target=main,
            view=ft.AppView.WEB_BROWSER,
            assets_dir='assets',
            upload_dir='assets/uploads',
            port=8502,
        )
