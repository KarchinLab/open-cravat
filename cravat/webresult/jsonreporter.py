from cravat.cravat_report import CravatReport
import sys
import datetime

class Reporter (CravatReport):
    def setup (self):
        self.data = {}
        self.keep_json_all_mapping = True
        
    def write_preface (self, level):
        self.data[level] = []
        self.table = self.data[level]
        self.level = level
    
    def write_table_row (self, row):
        row = self.substitute_val(self.level, row)
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
    reporter = Reporter([
        '', 'd:\\git\\cravat-newarch\\tmp\\job\\in1000.sqlite'])
    data = reporter.run()
    reporter = Reporter([
        '', 'd:\\git\\cravat-newarch\\tmp\\job\\in1000.sqlite',
        '--filterstring', '{"variant": {"thousandgenomes__af": ">0.1"}}'])
    data = reporter.run()

if __name__ == '__main__':
    #main()
    test()
