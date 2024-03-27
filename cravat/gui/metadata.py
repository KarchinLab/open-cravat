from cravat import admin_util as au


def supported_report_types():
    reporter_infos = au.get_local_module_infos(types=['reporter'])
    valid_report_types = [x.name.split('reporter')[0] for x in reporter_infos]
    return [v for v in valid_report_types if not v in ['text', 'pandas', 'stdout', 'example']]