import json
import os
import subprocess

import automatic_code_review_commons as commons
import gspread


def review(config):
    path_source = config['path_source']
    project_name = config['merge']['project_name']

    comments = []
    enums = get_enums(path_source)
    enums_mapped = config['enums']
    enums_to_search = []

    for enum in enums:
        enum["nameToSearch"] = project_name + "/" + enum['name']

        if enum['nameToSearch'] in enums_mapped:
            enums_to_search.append(enum['nameToSearch'])

    mappeds = get_data_by_google_sheets(config['data'], enums_to_search)

    for mapped in mappeds:
        enum_obj = None
        mapped_csv = mappeds[mapped]

        for enum in enums:
            if enum['nameToSearch'] == mapped:
                enum_obj = enum
                break

        for enum_value in enum_obj['values']:
            found = False

            for row in mapped_csv:
                if enum_value['name'] == row['name'] and enum_value['value'] == row['value']:
                    found = True
                    break

            if not found:
                comment_line = enum_value['line']
                comment_path = enum_obj['path'].replace(path_source, "")[1:]

                comment_description = config['message']
                comment_description = comment_description.replace("${ENUM_NAME}", enum_obj['name'])
                comment_description = comment_description.replace("${FILE_NAME}", comment_path)
                comment_description = comment_description.replace("${ENUM_VALUE}", enum_value['name'])

                comments.append(commons.comment_create(
                    comment_id=commons.comment_generate_id(comment_description),
                    comment_path=comment_path,
                    comment_description=comment_description,
                    comment_snipset=False,
                    comment_end_line=comment_line,
                    comment_start_line=comment_line,
                ))

    return comments


def get_enums(path_source):
    enums = []

    for root, dirs, files in os.walk(path_source):
        for file in files:
            path = os.path.join(root, file)

            if not path.endswith(".h") and not path.endswith(".cpp"):
                continue

            objs = get_infos(path)

            if len(objs) >= 1:
                enum_name = objs[0]['scope']
                enum_values = []

                for obj in objs:
                    value_name = obj['name']
                    real_value = get_enum_value(obj['pattern'], value_name)

                    enum_values.append({
                        "name": value_name,
                        "line": obj["line"],
                        "value": real_value
                    })

                enums.append({
                    "name": enum_name,
                    "path": path,
                    "values": enum_values
                })

    return enums


def get_enum_value(pattern, value_name):
    pattern = pattern.replace("/^", "")
    pattern = pattern.replace(value_name, "")
    pattern = pattern.replace("=", "")
    pattern = pattern.replace("'", "")
    pattern = pattern.replace(",", "")
    pattern = pattern.replace("$/", "")

    if "\\/" in pattern:
        comment_index_of = pattern.index("\\/")
        if comment_index_of >= 0:
            pattern = pattern[0:comment_index_of]

    pattern = pattern.strip()
    pattern = pattern.split(' ')
    pattern = pattern[len(pattern) - 1]

    return pattern


def get_infos(file_path):
    data = subprocess.run(
        'ctags --output-format=json -R --languages=c++ --c++-kinds=+p --fields=+iaSn --extras=+q ' + file_path,  # TODO USAR EXTENSAO DO CTAG
        shell=True,
        capture_output=True,
        text=True,
    ).stdout

    objs = []

    for data_obj in data.split('\n'):
        if data_obj == '':
            continue

        data_obj = json.loads(data_obj)

        if data_obj['kind'] != 'enumerator' or '::' in data_obj['name']:
            continue

        objs.append(data_obj)

    objs = sorted(objs, key=lambda x: x['line'])

    return objs


def get_data_by_google_sheets(config, worksheets):
    if len(worksheets) <= 0:
        return {}

    client, _ = gspread.oauth_from_dict(credentials=config["credentials"], authorized_user_info=config["authorizedUserInfo"])
    sh = client.open(config["sheet"])

    __COLUMN_NAME = 1
    __COLUMN_VALUE = 2
    __INDEX_START_ROW = 1

    worksheet_by_name = {}

    for worksheet in worksheets:
        worksheet_obj = sh.worksheet(worksheet)
        names = worksheet_obj.col_values(__COLUMN_NAME)[__INDEX_START_ROW:]
        values = worksheet_obj.col_values(__COLUMN_VALUE)[__INDEX_START_ROW:]
        enums_from_google_sheet = []

        for index, name in enumerate(names):
            enums_from_google_sheet.append({
                "name": name,
                "value": values[index]
            })

        worksheet_by_name[worksheet] = enums_from_google_sheet

    return worksheet_by_name
