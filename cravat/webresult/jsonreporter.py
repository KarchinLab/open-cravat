from cravat.cravat_report import CravatReport
import sys
import datetime
from cravat.config_loader import ConfigLoader
import cravat.constants as constants

class Reporter (CravatReport):

    def __init__ (self, cmd_args, status_writer):
        self.no_log = True
        self.no_status_update = True
        super().__init__(cmd_args, status_writer)

    def setup (self):
        self.data = {}
        self.keep_json_all_mapping = True
        self.conf = ConfigLoader()
        cravat_conf = self.conf.get_cravat_conf()
        if 'viewer_effective_digits' in cravat_conf:
            self.viewer_effective_digits = cravat_conf['viewer_effective_digits']
        else:
            self.viewer_effective_digits = constants.viewer_effective_digits
        
    def write_preface (self, level):
        self.data[level] = []
        self.table = self.data[level]
        self.level = level
    
    def write_table_row (self, row):
        row = self.substitute_val(self.level, row)
        for i in range(len(row)):
            cell = row[i]
            if type(cell) == float:
                row[i] = round(cell, self.viewer_effective_digits)
        self.table.append(list(row))
    
    def end (self):
        info = {}
        info['norows'] = len(self.data[self.level])
        self.data['info'] = info
        self.data['colinfo'] = self.colinfo
        return self.data
    
def main ():
    reporter = Reporter(sys.argv)
    reporter.run()
    
def test ():
    reporter = Reporter(['', 'd:\\git\\cravat-newarch\\tmp\\job\\in1000.sqlite'])
    data = reporter.run()
    reporter = Reporter([
        '', 'd:\\git\\cravat-newarch\\tmp\\job\\in1000.sqlite',
        '--filterstring', '{"variant": {"thousandgenomes__af": ">0.1"}}'])
    data = reporter.run()

if __name__ == '__main__':
    #main()
    test()
