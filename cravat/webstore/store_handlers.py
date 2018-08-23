import cravat.admin_util as au
import markdown

def get_remote_manifest(handler):
    manifest = handler.get_remote_manifest()
    return manifest

def get_module_readme(request):
    module_name = request.match_info['module']
    version = request.match_info['version']
    if version == 'latest': version=None
    readme_md = au.get_readme(module_name, version=version)
    if readme_md is None:
        response = web.Response()
        response.status = 404
    else:
        readme_html = markdown.markdown(readme_md)
        response = web.Response(body=readme_html,
                                content_type='text/html')
    return response

def get_local_manifest():
    au.refresh_cache()
    module_names = au.list_local()
    out = {}
    for module_name in module_names:
        local_info = au.get_local_module_info(module_name)
        out[module_name] = {
                            'version':local_info.version,
                            'type':local_info.type,
                            'title':local_info.title,
                            'description':local_info.description,
                            'developer':local_info.developer
                           }
    return web.json_response(out)

def install_module(request):
    module = request.json()
    module_name = module['name']
    version = module['version']
    au.install_module(module_name,version=version,verbose=False)
    return web.Response()

def uninstall_module(request):
    module = request.json()
    print('Uninstall requested for %s' %str(module))
    module_name = module['name']
    au.uninstall_module(module_name)
    return web.Response()
