from json import dump, load


def update_config_file(data, file):
    with open(file=file, mode="w", encoding="utf-8") as config_file:
        dump(data, config_file, indent=2)


def load_config_file(file):
    with open(file=file, mode="r", encoding="utf-8") as config_file:
        data = load(config_file)
    return data
