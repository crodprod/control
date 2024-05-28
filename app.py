import datetime
import json
import logging
import os
import platform
import subprocess
import time

import cv2
import flet as ft
import socket

import psutil
import transliterate
from dotenv import load_dotenv

from elements import epson_api, resolume_api, functions
from elements.screens import tabs

script_path = os.path.abspath(__file__)
script_directory = os.path.dirname(script_path)
os.chdir(script_directory)
project_folder = os.getcwd()

load_dotenv()

config = functions.load_config_file('config.json')
control_data = config['control']
paths_data = config['paths']
projectors_data = config['projectors']

resolume = resolume_api.ResolumeAPI(control_data['base_url'].format(control_data['host'], control_data['port']))
epson = epson_api.EpsonAPI(projectors_data['base_url'])


def shorten_string(string, max_length=20, ending="..."):
    if len(string) <= max_length:
        return string
    else:
        return string[:max_length] + ending


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


def is_running(process_name: str):
    # Проверка наличия процесса в диспетчере задач

    for a in psutil.process_iter(['pid', 'name']):
        if a.name().split('.')[0] == process_name:
            return True
    return False


def main(page: ft.Page):
    page.title = "Control"
    page.padding = 0

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

    if platform.system() == "Windows":
        page.window_width = 377
        page.window_height = 768

    appbar = ft.AppBar(
        title=ft.Text("Control", size=20, weight=ft.FontWeight.W_400),
        actions=[
            ft.Container(
                ft.Row(
                    [
                        ft.IconButton(icon=ft.icons.CAST_CONNECTED, on_click=lambda _: open_dialog(dialog_projectors)),
                        ft.PopupMenuButton(
                            items=[
                                # ft.PopupMenuItem(text="Обновить", icon=ft.icons.RESTART_ALT_ROUNDED),
                                # ft.PopupMenuItem(),
                                # ft.Divider(),
                                ft.PopupMenuItem(text="Скрыть раздел", icon=ft.icons.LAYERS_CLEAR, on_click=lambda _: clear('sel')),
                                ft.PopupMenuItem(text="Скрыть всё", icon=ft.icons.LAYERS_CLEAR, on_click=lambda _: clear('all')),
                            ]
                        )
                    ]
                ),
                padding=ft.padding.only(right=10)
            )
        ]
    )

    def clear(type: str):
        data = {
            0: 'FONS',
            1: 'ЭКРАНЫ',
            2: 'WALLS'
        }
        current_tab_index = page.navigation_bar.selected_index
        request = resolume.get_layers_info()
        if request is not None:
            for index, layer in enumerate(request['layers']):
                if type == 'sel':
                    if data[current_tab_index] in layer['name']['value']:
                        resolume.clear_layer(index)
                elif type == 'all':
                    resolume.clear_layer(index)
        if type == 'sel':
            open_sb('Слои раздела скрыты')
        elif type == 'all':
            open_sb('Все слои скрыты')

    def open_bs(bs: ft.BottomSheet):
        page.bottom_sheet = bs
        bs.open = True
        page.update()

    def close_bs(bs: ft.BottomSheet):
        bs.open = False
        page.update()

    def open_element(e: ft.ControlEvent):
        print(e.control.data)
        data = e.control.data
        request = resolume.get_layer_elements(data[0])
        if request is not None:
            for clip_index, el in enumerate(request['clips']):
                print(clip_index, el['name']['value'])
                if el['id'] == data[1]:
                    resolume.open_element(data[0], clip_index)
                    break

        # close_bs()

    bs = ft.BottomSheet(
        # is_scroll_controlled=True,
        content=ft.Container(
            content=ft.Column(
                controls=[
                    # ft.Row(
                    #     [
                    #         ft.Container(ft.Text("Выберите элемент", size=20, weight=ft.FontWeight.W_400), expand=True),
                    #         ft.IconButton(ft.icons.CLOSE, on_click=lambda _: close_bs(bs))
                    #     ]
                    # ),
                    ft.Column()
                ],
                scroll=ft.ScrollMode.HIDDEN,
                width=600

            ),
            padding=15
        )
    )

    def pick_element_on_layer(layer_index: int, preview: bool = True):
        request = resolume.get_layer_elements(layer_index)
        bs.content.content.controls[0].controls = [ft.Column([ft.ProgressBar()], height=100, alignment=ft.MainAxisAlignment.START)]
        if request is not None:
            layer_elements = [el for el in request['clips'] if el['name']['value'] != ""]
            if len(layer_elements) > 0:
                open_bs(bs)
                bs.content.content.controls[0].controls.clear()
                for el in layer_elements:
                    if preview:
                        if not os.path.exists(f"assets/previews/{el['id']}{os.path.splitext(el['video']['fileinfo']['path'])[1]}"):
                            generate_preview(el['video']['fileinfo']['path'], f"{el['id']}.png")
                        img = ft.Image(
                            src=f"previews/{el['id']}.png",
                            error_content=ft.Row([ft.Icon(ft.icons.IMAGE)], alignment=ft.MainAxisAlignment.CENTER, width=50),
                            width=50,
                            height=30
                        )
                    else:
                        img = ft.Row([ft.Icon(ft.icons.IMAGE)], alignment=ft.MainAxisAlignment.CENTER, width=50)
                    bs.content.content.controls[0].controls.append(
                        ft.Card(
                            ft.Container(
                                content=ft.Row(
                                    [
                                        img,
                                        ft.Text(shorten_string(el['name']['value']), size=16)
                                    ]
                                ),
                                padding=10,
                                data=[layer_index, el['id']],
                                on_click=open_element
                            ),
                            elevation=5
                        )
                        # ft.Text(el['name']['value'], size=20)
                    )
                page.update()
            else:
                open_sb("Этот слой пустой")
        else:
            page.add(ft.Column([ft.Text("Ошибка подключения к Resolume", size=18, weight=ft.FontWeight.W_400)], horizontal_alignment=ft.CrossAxisAlignment.CENTER))

    def edit_clip(e: ft.ControlEvent):
        # Изменение свойств выбранного клипа

        # hf.medium_impact()()
        data = e.control.data.split("_")
        print(data)
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
        request = resolume.get_clip_info(clip_id)
        if request is not None:
            del request['video']['effects'][0]['bypassed']
            del request['video']['effects'][0]['mixer']
            del request['video']['sourceparams']
            if data[1] == "plus":
                print(request['video']['effects'][0]['params'][data[0]]['value'])
                request['video']['effects'][0]['params'][data[0]]['value'] += step
                print(request['video']['effects'][0]['params'][data[0]]['value'])
            elif data[1] == "minus":
                request['video']['effects'][0]['params'][data[0]]['value'] -= step
            elif data[1] == "center":
                request['video']['effects'][0]['params']['Position X']['value'] = 0
                request['video']['effects'][0]['params']['Position Y']['value'] = 0
            # old = {"video": old}
            print('updating ', clip_id)
            # functions.update_config_file(json.loads(request, ensure_ascii=False), 'test.json')
            old = {"video": request['video']}
            resolume.update_clip_info(clip_id, json.dumps(old))
            print('ok1')
            # requests.put(url=url, headers=get_headers('application/json'), data=json.dumps(old))

    def goto_edit_clip(layer_index):
        request = resolume.get_layer_elements(layer_index)
        if request is not None:
            clip_id = -1
            for el in request['clips']:
                if el['connected']['value'] == "Connected":
                    clip_id = el['id']
                    break
            if clip_id != -1:
                dialog_edit.content = ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row([ft.IconButton(ft.icons.ARROW_UPWARD_ROUNDED, scale=2,
                                                  on_click=edit_clip,
                                                  data=f"Position Y_minus_{clip_id}"
                                                  )
                                    ],
                                   alignment=ft.MainAxisAlignment.CENTER),
                            ft.Row(
                                [ft.IconButton(ft.icons.ARROW_BACK_ROUNDED, scale=2,
                                               on_click=edit_clip,
                                               data=f"Position X_minus_{clip_id}"
                                               ),
                                 ft.IconButton(ft.icons.FIT_SCREEN_ROUNDED, scale=2,
                                               on_click=edit_clip,
                                               data=f"center_center_{clip_id}"
                                               ),
                                 ft.IconButton(ft.icons.ARROW_FORWARD_ROUNDED, scale=2,
                                               on_click=edit_clip,
                                               data=f"Position X_plus_{clip_id}"
                                               )],
                                alignment=ft.MainAxisAlignment.CENTER,

                            ),
                            ft.Row([ft.IconButton(ft.icons.ARROW_DOWNWARD_ROUNDED, scale=2,
                                                  on_click=edit_clip,
                                                  data=f"Position Y_plus_{clip_id}"
                                                  )],
                                   alignment=ft.MainAxisAlignment.CENTER),
                            ft.Divider(thickness=1),
                            ft.Row(
                                [
                                    ft.Text("Масштаб", width=100, size=16, weight=ft.FontWeight.W_400),
                                    ft.IconButton(ft.icons.ADD_ROUNDED,
                                                  on_click=edit_clip,
                                                  data=f"Scale_plus_{clip_id}"
                                                  ),
                                    ft.IconButton(ft.icons.REMOVE_ROUNDED, on_click=edit_clip,
                                                  data=f"Scale_minus_{clip_id}"
                                                  )
                                ],
                                alignment=ft.MainAxisAlignment.CENTER
                            ),
                            ft.Row(
                                [
                                    ft.Text("Ширина", width=100, size=16, weight=ft.FontWeight.W_400),
                                    ft.IconButton(ft.icons.ADD_ROUNDED,
                                                  on_click=edit_clip,
                                                  data=f"Scale W_plus_{clip_id}"
                                                  ),
                                    ft.IconButton(ft.icons.REMOVE_ROUNDED, on_click=edit_clip,
                                                  data=f"Scale W_minus_{clip_id}"
                                                  )
                                ],
                                alignment=ft.MainAxisAlignment.CENTER
                            ),
                            ft.Row(
                                [
                                    ft.Text("Высота", width=100, size=16, weight=ft.FontWeight.W_400),
                                    ft.IconButton(ft.icons.ADD_ROUNDED,
                                                  on_click=edit_clip,
                                                  data=f"Scale H_plus_{clip_id}"
                                                  ),
                                    ft.IconButton(ft.icons.REMOVE_ROUNDED, on_click=edit_clip,
                                                  data=f"Scale H_minus_{clip_id}"
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
                pass
            else:
                open_sb("Сначала активируйте элемент")

    def get_layer_index_by_layer_id(layer_id: str):
        request = resolume.get_layers_info()
        if request is not None:
            for index, layer in enumerate(request['layers']):
                if layer['id'] == int(layer_id):
                    return index

    def layer_action(e: ft.ControlEvent):
        data = e.control.data.split("_")
        print(data)
        if data[0] == "fons" or data[0] == "walls" or (data[0] == 'screens' and data[2] in ['edit', 'clear']) or (data[0] == "presets" and data[2] == "clear"):
            action = data[2]
            if action == "pick":
                pick_element_on_layer(get_layer_index_by_layer_id(data[1]))
            elif action == "upload":
                open_element_picker(get_layer_index_by_layer_id(data[1]))
            elif action == "edit":
                goto_edit_clip(get_layer_index_by_layer_id(data[1]))
            elif action == "clear":
                resolume.clear_layer(get_layer_index_by_layer_id(data[1]))
                open_sb("Слой очищен")

        elif data[0] == "screens":
            action = data[2]
            layer_index = get_layer_index_by_layer_id(data[1])
            if action == "1":
                resolume.open_element(layer_index, 0)
            elif action == "2":
                resolume.open_element(layer_index, 1)

        elif data[0] == "presets":
            action = data[2]
            if action == "pick":
                pick_element_on_layer(get_layer_index_by_layer_id(data[1]), preview=False)



        else:
            pass

    def open_sb(text: str, bgcolor=ft.colors.WHITE):
        if bgcolor != ft.colors.WHITE:
            text_color = ft.colors.WHITE
        else:
            text_color = ft.colors.BLACK

        content = ft.Text(text, size=18, text_align=ft.TextAlign.START, weight=ft.FontWeight.W_300, color=text_color)
        page.snack_bar = ft.SnackBar(
            content=content,
            duration=1200,
            bgcolor=bgcolor
        )
        page.snack_bar.open = True
        page.update()

    def save_element(e: ft.ControlEvent):
        # Загрузка нового элемента в директорию
        layer_index = e.control.data
        upload_list = []
        if element_picker.result is not None and element_picker.result.files is not None:
            loading_text.value = "Загрузка элемента"
            open_dialog(dialog_loading)
            print('ok1')
            for f in element_picker.result.files:
                upload_list.append(
                    ft.FilePickerUploadFile(
                        f.name,
                        upload_url=page.get_upload_url(f.name, 60),
                    )
                )
            element_picker.upload(upload_list)
            print('ok3')
            time.sleep(3)
            print('ok2')

            old_filename = element_picker.result.files[-1].name
            new_filename = transliterate.translit(old_filename.replace(" ", ""), 'ru', reversed=True)
            os.rename(f"assets/uploads/{old_filename}", f"assets/uploads/{new_filename}")
            print(f"{old_filename} renamed to {new_filename}")

            request = resolume.get_layer_elements(layer_index)
            if request is not None:
                for clip_index, el in enumerate(request['clips']):
                    if el['connected']['value'] == "Empty":
                        x = project_folder.replace("\\", '/')
                        filepath = f"file:///{x}/assets/uploads/{new_filename}"
                        close_dialog(dialog_loading)
                        if resolume.load_element(layer_index, clip_index, filepath) == 204:
                            resolume.open_selected_clip()
                        else:
                            open_sb("Ошибка загрузки", ft.colors.RED)
                        break
            else:
                open_sb("Потеряно подключение к Resolume", ft.colors.RED)
        else:
            open_sb("Загрузка отменена")

    element_picker = ft.FilePicker(on_result=save_element)
    page.overlay.append(element_picker)

    def open_element_picker(layer_index):
        element_picker.data = layer_index
        element_picker.pick_files(
            allow_multiple=False,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=['jpg', 'jpeg', 'png', 'mp4', 'avi', 'mov']
        )

    def change_navbar_tab(e):
        page.controls.clear()
        page.controls.append(ft.ProgressBar())
        page.update()
        page.controls.clear()
        # time.sleep(0.5)

        if type(e) == int:
            tab_index = e
        else:
            tab_index = e.control.selected_index

        if tab_index == 0:
            layers_col = ft.Column()
            # functions.update_config_file(resolume.get_layers_info(), 'test.json')
            request = resolume.get_layers_info()

            if request is not None:
                layers = [el for el in request['layers'] if 'FONS' in el['name']['value']]
                layers.reverse()
                for layer in layers:
                    name = " ".join(layer['name']['value'].split()[1:])
                    layers_col.controls.append(
                        ft.Card(
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Text(shorten_string(name), size=20, weight=ft.FontWeight.W_400),
                                        ft.Row(
                                            [
                                                ft.IconButton(
                                                    ft.icons.VIEW_LIST, data=f"fons_{layer['id']}_pick",
                                                    on_click=layer_action
                                                ),
                                                ft.IconButton(
                                                    ft.icons.ADD_PHOTO_ALTERNATE_OUTLINED, data=f"fons_{layer['id']}_upload",
                                                    on_click=layer_action
                                                ),
                                                ft.VerticalDivider(),
                                                ft.IconButton(
                                                    ft.icons.EDIT, data=f"fons_{layer['id']}_edit",
                                                    on_click=layer_action
                                                ),
                                                ft.IconButton(
                                                    ft.icons.CLOSE, data=f"fons_{layer['id']}_clear",
                                                    on_click=layer_action
                                                ),
                                            ],
                                            alignment=ft.MainAxisAlignment.CENTER
                                        )
                                    ],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    width=600,
                                    height=80
                                ),
                                padding=15

                            ),
                            elevation=5
                        )
                    )
                page.controls.append(layers_col)

            else:
                page.add(ft.Column([ft.Text("Ошибка подключения к Resolume", size=18, weight=ft.FontWeight.W_400)], horizontal_alignment=ft.CrossAxisAlignment.CENTER))

        elif tab_index == 1:
            col = ft.Column()
            # functions.update_config_file(resolume.get_layers_info(), 'test.json')
            request = resolume.get_layers_info()

            if request is not None:
                layers = [el for el in request['layers'] if 'ЭКРАНЫ' in el['name']['value']]
                layers.reverse()
                for layer in layers:
                    name = " ".join(layer['name']['value'].split()[1:])
                    col.controls.append(
                        ft.Card(
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Text(shorten_string(name), size=20, weight=ft.FontWeight.W_400),
                                        ft.Row(
                                            [
                                                ft.IconButton(
                                                    ft.icons.FILTER_1, data=f"screens_{layer['id']}_1",
                                                    on_click=layer_action
                                                ),
                                                ft.IconButton(
                                                    ft.icons.FILTER_2, data=f"screens_{layer['id']}_2",
                                                    on_click=layer_action
                                                ),
                                                ft.VerticalDivider(),
                                                ft.IconButton(
                                                    ft.icons.EDIT, data=f"screens_{layer['id']}_edit",
                                                    on_click=layer_action
                                                ),
                                                ft.IconButton(
                                                    ft.icons.CLOSE, data=f"screens_{layer['id']}_clear",
                                                    on_click=layer_action
                                                ),
                                            ],
                                            alignment=ft.MainAxisAlignment.CENTER
                                        )
                                        # ft.Row(
                                        #     [
                                        #         ft.IconButton(
                                        #             ft.icons.VIEW_LIST, data=f"fons_{layer['id']}_pick",
                                        #             on_click=layer_action
                                        #         ),
                                        #         ft.IconButton(
                                        #             ft.icons.ADD_PHOTO_ALTERNATE_OUTLINED, data=f"fons_{layer['id']}_upload",
                                        #             on_click=layer_action
                                        #         ),
                                        #         ft.IconButton(
                                        #             ft.icons.EDIT, data=f"fons_{layer['id']}_edit",
                                        #             on_click=layer_action
                                        #         ),
                                        #         ft.IconButton(
                                        #             ft.icons.CLOSE, data=f"fons_{layer['id']}_clear",
                                        #             on_click=layer_action
                                        #         ),
                                        #     ],
                                        #     alignment=ft.MainAxisAlignment.CENTER
                                        # )
                                    ],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    width=600,
                                    # height=80
                                ),
                                padding=15

                            ),
                            elevation=5
                        )
                    )
                page.controls.append(col)

            else:
                page.add(ft.Column([ft.Text("Ошибка подключения к Resolume", size=18, weight=ft.FontWeight.W_400)], horizontal_alignment=ft.CrossAxisAlignment.CENTER))

        elif tab_index == 2:
            col = ft.Column()
            # functions.update_config_file(resolume.get_layers_info(), 'test.json')
            request = resolume.get_layers_info()

            if request is not None:
                layers = [el for el in request['layers'] if 'WALLS' in el['name']['value']]
                layers.reverse()
                for layer in layers:
                    name = " ".join(layer['name']['value'].split()[1:])
                    col.controls.append(
                        ft.Card(
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Text(shorten_string(name), size=20, weight=ft.FontWeight.W_400),
                                        ft.Row(
                                            [
                                                ft.IconButton(
                                                    ft.icons.VIEW_LIST, data=f"fons_{layer['id']}_pick",
                                                    on_click=layer_action
                                                ),
                                                ft.IconButton(
                                                    ft.icons.ADD_PHOTO_ALTERNATE_OUTLINED, data=f"fons_{layer['id']}_upload",
                                                    on_click=layer_action
                                                ),
                                                ft.VerticalDivider(),
                                                ft.IconButton(
                                                    ft.icons.EDIT, data=f"fons_{layer['id']}_edit",
                                                    on_click=layer_action
                                                ),
                                                ft.IconButton(
                                                    ft.icons.CLOSE, data=f"fons_{layer['id']}_clear",
                                                    on_click=layer_action
                                                ),
                                            ],
                                            alignment=ft.MainAxisAlignment.CENTER
                                        )
                                    ],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    width=600,
                                    # height=80
                                ),
                                padding=15

                            ),
                            elevation=5
                        )
                    )
                page.controls.append(col)

            else:
                page.add(ft.Column([ft.Text("Ошибка подключения к Resolume", size=18, weight=ft.FontWeight.W_400)], horizontal_alignment=ft.CrossAxisAlignment.CENTER))

        elif tab_index == 3:
            layers_col = ft.Column()
            # functions.update_config_file(resolume.get_layers_info(), 'test.json')
            request = resolume.get_layers_info()

            if request is not None:
                layers = [el for el in request['layers'] if 'PRESETS' in el['name']['value']]
                layers.reverse()
                for layer in layers:
                    name = " ".join(layer['name']['value'].split()[1:])
                    layers_col.controls.append(
                        ft.Card(
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Text(shorten_string(name), size=20, weight=ft.FontWeight.W_400),
                                        ft.Row(
                                            [
                                                ft.IconButton(
                                                    ft.icons.VIEW_LIST, data=f"presets_{layer['id']}_pick",
                                                    on_click=layer_action
                                                ),
                                                ft.VerticalDivider(),
                                                ft.IconButton(
                                                    ft.icons.EDIT, data=f"presets_{layer['id']}_edit",
                                                    on_click=layer_action
                                                ),
                                                ft.IconButton(
                                                    ft.icons.CLOSE, data=f"presets_{layer['id']}_clear",
                                                    on_click=layer_action
                                                ),
                                            ],
                                            alignment=ft.MainAxisAlignment.CENTER
                                        )
                                    ],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    width=600,
                                    height=80
                                ),
                                padding=15

                            ),
                            elevation=5
                        )
                    )
                page.controls.append(layers_col)

            else:
                page.add(ft.Column([ft.Text("Ошибка подключения к Resolume", size=18, weight=ft.FontWeight.W_400)], horizontal_alignment=ft.CrossAxisAlignment.CENTER))

        page.update()

    def change_screen(target: str):
        page.navigation_bar = None
        page.appbar = None

        if target == 'login':
            page.vertical_alignment = ft.MainAxisAlignment.CENTER
            page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
            page.add(login_col)

        elif target == 'main':
            page.scroll = ft.ScrollMode.HIDDEN
            page.vertical_alignment = ft.MainAxisAlignment.START
            page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
            page.navigation_bar = navbar
            page.appbar = appbar
            change_navbar_tab(0)
        page.update()

    navbar = ft.NavigationBar(
        destinations=[
            ft.NavigationDestination(
                label=tabs[0]['title'],
                icon=tabs[0]['icon']
            ),
            ft.NavigationDestination(
                label=tabs[1]['title'],
                icon=tabs[1]['icon']
            ),
            ft.NavigationDestination(
                label=tabs[2]['title'],
                icon=tabs[2]['icon']
            ),
            ft.NavigationDestination(
                label=tabs[3]['title'],
                icon=tabs[3]['icon']
            )
        ],
        on_change=change_navbar_tab
    )

    def open_dialog(dialog: ft.AlertDialog):
        page.dialog = dialog
        dialog.open = True
        page.update()

    def close_dialog(dialog: ft.AlertDialog):
        dialog.open = False
        page.update()

    dialog_edit = ft.AlertDialog(
        # Диалог редактирования свойств элемента

        title=ft.Row(
            [
                ft.Container(ft.Text("Свойства", size=20, weight=ft.FontWeight.W_400), expand=True),
                ft.IconButton(ft.icons.CLOSE_ROUNDED, on_click=lambda _: close_dialog(dialog_edit))
            ]
        ),
        modal=True

    )

    def switch_prjectors(action: str):
        close_dialog(dialog_projectors)
        open_sb("Отправляем запрос")
        if action == "off":
            for device in projectors_data['devices']:
                epson.switch_off(device['ip_address'])
        elif action == "on":
            for device in projectors_data['devices']:
                request = epson.get_power_status(device['ip_address'])
                if request['status'] != 'Active':
                    epson.switch_on(device['ip_address'])
        open_sb("Запрос отправлен", ft.colors.GREEN)

    dialog_projectors = ft.AlertDialog(
        # Диалог с кнопкой запуска Resolume

        modal=True,
        title=ft.Row(
            [
                ft.Container(ft.Text("Проекторы", size=20, weight=ft.FontWeight.W_400), expand=True),
                ft.IconButton(ft.icons.CLOSE_ROUNDED, on_click=lambda _: close_dialog(dialog_projectors))
            ]
        ),
        content=ft.Text(
            "Если один или несколько проекторов не работают, то нажмите на кнопку включения проекторов",
            size=17,
            width=600
        ),
        actions=[
            ft.Column(
                [
                    ft.ElevatedButton(
                        text="Включить",
                        on_click=lambda _: switch_prjectors('on'),
                        bgcolor=ft.colors.GREEN,
                        width=600
                    ),
                    ft.ElevatedButton(
                        text="Выключить",
                        on_click=lambda _: switch_prjectors('off'),
                        bgcolor=ft.colors.RED,
                        width=600
                    )

                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )
        ],
        actions_alignment=ft.MainAxisAlignment.END
    )

    dialog_info = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Container(ft.Text("Resolume", size=20, weight=ft.FontWeight.W_400), expand=True),
                ft.IconButton(ft.icons.CLOSE_ROUNDED, on_click=lambda _: close_dialog(dialog_info))
            ]
        )
    )

    dialog_resolume_start_menu = ft.AlertDialog(
        # Диалог с кнопкой запуска Resolume

        modal=True,
        title=ft.Row(
            [
                ft.Container(ft.Text("Resolume", size=20, weight=ft.FontWeight.W_400), expand=True),
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

    loading_text = ft.Text(size=20, weight=ft.FontWeight.W_400)
    dialog_loading = ft.AlertDialog(
        # Диалог с кольцом загрузки

        # title=ft.Text(size=20),
        modal=True,
        content=ft.Column(
            controls=[
                ft.Column([loading_text, ft.ProgressBar()], alignment=ft.MainAxisAlignment.CENTER),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            width=400,
            height=50
        )
    )

    def start_resolume():
        close_dialog(dialog_resolume_start_menu)
        # hf.medium_impact()
        time_to_open = control_data['start_time']
        percents = 100 / time_to_open
        loading_text.value = "Запуск Resolume"
        open_dialog(dialog_loading)
        logging.info(f"Запуск процесса Arena.exe")
        subprocess.Popen(rf"{paths_data['arena']}", creationflags=subprocess.CREATE_NEW_CONSOLE, shell=True)
        time.sleep(time_to_open)
        # for i in range(1, time_to_open + 1):
        #     dialog_loading.content.controls[1].value = f"{int(percents * i)}%"
        #     time.sleep(1)

        close_dialog(dialog_loading)
        # dialog_loading.content.controls[1].value = ""
        change_screen('main')

    def load_exe(exe_name: str):
        # Поиск и запуск исполняемых файлов

        logging.info(f"Поиск процесса {exe_name}.exe")
        if is_running(exe_name):
            logging.info(f"Процесс {exe_name}.exe обнаружен")
            request = resolume.get_layers_info()
            if request is not None:
                if request['name']['value'] == "CROD_NEW":
                    change_screen('main')
                else:
                    dialog_info.content = ft.Text(f"На сервере открыт другой проект Resolume ({request['name']['value']}).Закройте его вручную и откройте проект CROD_NEW", size=18)
                    open_dialog(dialog_info)
            else:
                dialog_info.content = ft.Text(f"Не удаётся подключиться к Resolume. Попробуйте ещё раз или обратитесь к администратору", size=18)
                open_dialog(dialog_info)
        else:
            logging.info(f"Процесс {exe_name}.exe не обнаружен")
            open_dialog(dialog_resolume_start_menu)

    def login():
        true_password = os.getenv('PANEL_PASSWORD')
        if login_field.value == true_password:
            open_sb("Загружаем...")
            load_exe('Arena')
        else:
            open_sb("Неверный код")
        login_field.value = ""
        page.update()

    def generate_preview(file_path: str, preview_filename: str):
        try:
            cap = cv2.VideoCapture(file_path)

            if not cap.isOpened():
                return None

            ret, frame = cap.read()

            if not ret:
                return None

            cap.release()
            cv2.imwrite(f'assets/previews/{preview_filename}', frame)
        except Exception:
            return None

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
            ft.Image(
                src='icons/loading-animation.png',
                height=200
            ),
            login_field,
            button_login
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER
    )
    os.environ["FLET_SECRET_KEY"] = os.urandom(12).hex()
    change_screen('login')

    page.update()


if __name__ == "__main__":
    if not is_port_in_use(8502):
        logging.basicConfig(level=logging.INFO,
                            filename=f"logs/{datetime.datetime.now().date()}.log",
                            filemode="w",
                            format="%(asctime)s %(levelname)s %(message)s",
                            encoding='utf-8'
                            )
        if not is_running('ngrok'):
            subprocess.Popen(
                fr"ngrok.exe http 8502 --domain={os.getenv('NGROK_DOMAIN')}",
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        ft.app(
            target=main,
            view=ft.AppView.WEB_BROWSER,
            assets_dir='assets',
            upload_dir='assets/uploads',
            port=8502,
        )
