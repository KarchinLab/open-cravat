import cravat.admin_util as au
from aiohttp import web
import markdown

async def get_remote_manifest(request):
    manifest = au.get_remote_manifest()
    return web.json_response(manifest)

async def get_module_readme(request):
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

async def get_local_manifest(request):
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

async def install_module(request):
    module = await request.json()
    module_name = module['name']
    version = module['version']
    au.install_module(module_name,version=version,verbose=False)
    return web.Response()

async def uninstall_module(request):
    module = await request.json()
    print('Uninstall requested for %s' %str(module))
    module_name = module['name']
    au.uninstall_module(module_name)
    return web.Response()
