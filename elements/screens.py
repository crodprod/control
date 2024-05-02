from flet import icons, ScrollMode

screens = {
    'login': {
        'title': "Авторизация",
        'leading_icon': None,
        'scroll_mode': None
    },
    'main': {
        'title': "Control",
        'leading_icon': None,
        'scroll_mode': None
    }
}

tabs = {
    1: {
        'nick': 'projectors',
        'title': "Экраны",
        'icon': icons.CAST_CONNECTED,
        'scroll_mode': ScrollMode.HIDDEN,
        'floating_btn': {
            'view': None,
            'title': None,
            'icon': None,
            'target': None
        }
    },
    0: {
        'nick': 'fons',
        'title': "Фоны",
        'icon': icons.IMAGE,
        'scroll_mode': ScrollMode.HIDDEN,
        'floating_btn': {
            'view': None,
            'title': None,
            'icon': None,
            'target': None
        }
    },
    2: {
        'nick': 'walls',
        'title': "Стены",
        'icon': icons.VIEW_COMFORTABLE,
        'scroll_mode': ScrollMode.HIDDEN,
        'floating_btn': {
            'view': None,
            'title': None,
            'icon': None,
            'target': None
        }
    },
    3: {
        'nick': 'presets',
        'title': "Пресеты",
        'icon': icons.APPS,
        'scroll_mode': ScrollMode.HIDDEN,
        'floating_btn': {
            'view': None,
            'title': None,
            'icon': None,
            'target': None
        }
    }
}
