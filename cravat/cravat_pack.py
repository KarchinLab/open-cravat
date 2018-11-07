import sys
import os
import shutil
import zipfile
import yaml

def main ():
    dataname = 'data'
    module_dir = os.path.abspath(sys.argv[1])
    if os.path.exists(module_dir) == False:
        print(module_dir, 'does not exists')
        exit()
    module_name = os.path.basename(module_dir)
    cwd = os.getcwd()
    paths = os.listdir(module_dir)
    
    # yml file
    confpath = os.path.join(module_dir, module_name + '.yml')
    if os.path.exists(confpath) == False:
        print(confpath + ' does not exists')
        exit()
    with open(confpath) as f:
        conf = yaml.load(f)
    if 'version' not in conf:
        print('Version is not in ' + confpath)
        exit()
    code_version = conf['version']
    
    # Target module folder
    target_module_dir = os.path.join(cwd, module_name)
    if os.path.exists(target_module_dir) == False:
        os.mkdir(target_module_dir)
    
    # Version folder
    verdir = os.path.join(target_module_dir, code_version)
    if os.path.exists(verdir):
        shutil.rmtree(verdir)
    os.mkdir(verdir)
    
    # Copies yml file.
    print('Copying conf file...')
    shutil.copy(confpath, verdir)
    
    # Zips code.
    print('Making code zip file...')
    zippath = os.path.join(verdir, module_name + '.zip')
    z = zipfile.ZipFile(zippath, mode='w')
    for path in paths:
        if path == dataname:
            continue
        print('  Adding ' + path)
        z.write(os.path.join(module_dir, path), path)
    z.close()
    
    # Zips data.
    if dataname in paths:
        print('Making data zip file...')
        data_dir = os.path.join(module_dir, dataname)
        zippath = os.path.join(verdir, module_name + '.' + dataname + '.zip')
        z = zipfile.ZipFile(zippath, mode='w')
        paths = os.listdir(data_dir)
        for path in paths:
            print('  Adding ' + path)
            z.write(os.path.join(data_dir, path), os.path.join(dataname, path))
        z.close()
    
    print('Done')