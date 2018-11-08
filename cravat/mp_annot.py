from cravat import util
import time
import traceback

def run_mp_annot(a):
    try:
        module = a[0]
        print('annotator= '+module.name)
        cmd = a[1]
        annotator_class = util.load_class("CravatAnnotator", module.script_path)
        annotator = annotator_class(cmd)
        annotator.run()
    except:
        traceback.print_exc()
        raise