import cravat
from cravat import util

output_dir = '/home/kyle/a/jobs/lihc-maf'
run_name = 'LIHC_maf_hg38_1000.txt'

module = cravat.admin_util.get_local_module_info('cohortcompare')

cmd = [module.script_path, "-d", output_dir, "-n", run_name]

status_path = '/tmp/ocstatus.json'
with open(status_path,'w') as f:
	f.write('{}')
status_writer = cravat.StatusWriter('/tmp/ocstatus.json')

post_agg_cls = util.load_class(module.script_path, "CravatPostAggregator")
post_agg = post_agg_cls(cmd, status_writer)
post_agg.run()