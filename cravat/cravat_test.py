import argparse
import os
import subprocess
from cravat import admin_util as au
import time


# Regression test program for CRAAT modules.  By default, it will go through all modules and
# if the module has a test directory with an input and key file, it will test the module 
# and compare the results to the key to determine whether everything is running as expected.
# The command line -m can be used to specify one or more specific modules to test and the 
# -t option can be used to run tests on modules of a specific type (e.g. annotator)
#
# The test program runs input though the full cravat processing flow and collects the output
# of the 'text' reporter to compare to the key.
#
# When creating a test case for the cravat_test, just run a cravat input, collect the text
# report output, check that the results are correct, and then save the output as the key.
#
# The tester creates an output directory and then a subdirectory for each module run.
# Logs and output for each module can be found in the associated subdirectory.

class Tester():
    def __init__(self, module, rundir):
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        self.module = module
        if not os.path.exists(module.directory) or not module.script_exists:
            raise Exception('No runnable module installed at path %s' %module.directory)
        self.out_dir = os.path.join(rundir, module.name);
        if not os.path.exists(self.out_dir):
            os.makedirs(self.out_dir)
        self.input_path = os.path.join(module.test_dir, 'input')
        self.key_path = os.path.join(module.test_dir, 'key')
        self.log_path = os.path.join(self.out_dir,'test.log')    #put the output of this program in test.log
        self.cravat_run = os.path.join(cur_dir, 'runcravat.py')
        self.out_path = os.path.join(self.out_dir, 'input.tsv') 
        self.log = open(self.log_path,'w')
        self.start_time = None
        self.end_time = None
        self.failures = []
        self.test_passed = False
                              
    # function that tests one module                          
    def run(self):
        self._report('  Testing: ' + self.module.name);
        self.start_time = time.time()
        cmd_list = ['python', self.cravat_run, self.input_path, '-d', self.out_dir, '-t', 'text']
        if (self.module.type == 'annotator'):
            cmd_list.append('-a')
            cmd_list.append(self.module.name)
        else:
            cmd_list.append('--sa')
        print(' '.join(cmd_list))
        exit_code = subprocess.call(' '.join(cmd_list), shell=True, stdout=self.log, stderr=subprocess.STDOUT)
        if exit_code != 0:
            self._report('    CRAVAT non-zero exit code: ' + str(exit_code))
        
        return exit_code
    
    # Read the two report header columns that define the module/column
    # for each data column.  Returned as list of: module|column
    def readTextSectionHeader(self, line1, line2):
        cols = line1.split('\t')
        headers = []
        current_module = cols[0]
        for col in cols:
            if col != '':
                current_module = col
                headers.append(col + '|')
            else:
                headers.append(current_module + '|')
        cols = line2.split('\t')
        for idx, col in enumerate(cols):            
            headers[idx] = headers[idx] + col
        return headers    
    
    #get the position of a specific output column
    def getColPos(self, headers, col):
        for idx, header in enumerate(headers):
            if col in header:
                return idx
    
    #The ID of a result row is used to match key and output.  The ID
    #differs depending on which section of the output is being checked.         
    def getTextReportID(self, headers, columns, level):
        Id = ''
        if (level == 'variant'):
            Id = columns[self.getColPos(headers, 'Chrom')] + ' ' + \
                 columns[self.getColPos(headers, 'Position')] + ' ' + \
                 columns[self.getColPos(headers, 'Ref Base')] + ' ' + \
                 columns[self.getColPos(headers, 'Alt Base')] + ' ' + \
                 columns[self.getColPos(headers, 'Tags')];
        if (level == 'gene'):
            Id = columns[self.getColPos(headers, 'Hugo')];
        if (level == 'sample'):
            Id = columns[self.getColPos(headers, 'UID')] + ' ' + \
                 columns[self.getColPos(headers, 'Sample')];    
        if (level == 'mapping'):
            Id = columns[self.getColPos(headers, 'Original Line')];    
        return Id         
    
    #Read the specified level (variant, gene, etc) from text cravat report
    #Return a list of the report headers and a list of the row values
    #Rows can be returned as a list or dictionary
    def readTextReport(self, rsltFile, test_level, bDict):
        level_hdr = 'Report level:'
        level = ''
        headers = None
        if (bDict):
            rows = {}
        else:
            rows = []
        with open(rsltFile) as f:
            line = f.readline().strip('\n')
            while line:
                # skip comment lines but pull out the report level
                if line.strip().startswith('#'):    
                    if level_hdr in line:
                        level = line[line.index(level_hdr) + len(level_hdr) + 1:]
                    line = f.readline().strip('\n')
                    continue
                
                #only load the level we are testing
                if level != test_level:
                    line = f.readline().strip('\n')
                    continue
                   
                #load headers for the section
                if headers == None:
                    line2 = f.readline().strip('\n')  
                    headers = self.readTextSectionHeader(line, line2)
                    line = f.readline().strip('\n')
                    continue
                
                
                columns = line.split('\t')
                line_id = self.getTextReportID(headers, columns, level)
                if (bDict):
                    rows[line_id] = columns
                else:
                    rows.append((line_id, columns))    
                line = f.readline().strip('\n')
        return headers, rows        
    
    def verify(self):
        self.test_passed = True
        if (self.module.type == 'annotator'):
            self.verify_level(self.module.level, self.module.title)
        elif (self.module.type == 'mapper'):
            self.verify_level('variant', 'Base Information')
            self.verify_level('gene', 'Base Information')  
        elif (self.module.type == 'converter'):
            self.verify_level('variant', 'Base Information')
            self.verify_level('sample', 'Base Information')
            self.verify_level('mapping', 'Base Information')
                 
        
    #Match the key (expected values) to the text report output.  Generate errors
    #if expected results are not found and fail the test.    Test just the specified
    #level (variant, gene, etc) and specified module's columns 
    def verify_level(self, level, module_name):
        self._report('  Verifying ' + level + ' level values.')
        key_header, key_rows = self.readTextReport(self.key_path, level, False)
        result_header, result_rows = self.readTextReport(self.out_path, level, True)
        for key in key_rows:
            variant, key_row = key
            if variant not in result_rows:
                self._report('  Variant: ' + variant + ' did not appear in results');
                self.test_passed = False
                continue
            
            result = result_rows[variant]
                        
            for idx, header in enumerate(key_header):
                #just check the columns from the module we are testing
                if module_name not in header or 'UID' in header:
                    continue
                
                if header not in result_header:
                    self.test_passed = False
                    continue
                
                result_idx = result_header.index(header)
                if result[result_idx] != key_row[idx]:
                    self._report('      ' + variant + '  ' + \
                          header[header.index("|")+1:] + \
                          '  Expected: ' + key_row[idx] + \
                          '  Result: ' + result[result_idx])
                    self.test_passed = False
             
    #Write a message to the screen and to the log file.
    def _report(self, s):
        self.log.write(s + '\n')
        print(s)
    
    #Log success /failure of test.
    def write_results(self):
        self.end_time = time.time()
        elapsed_time = self.end_time - self.start_time
        self._report('  Completed in: %.2f seconds' %elapsed_time)
        if self.test_passed:
            self._report('  Test result: PASS')
        else:
            self._report('  Test result: FAIL')
 

#Read command line args.   
def get_args(): 
    parser = argparse.ArgumentParser()
    parser.add_argument('-d',
                        '--rundir',
                         help='Directory for output')
    parser.add_argument('-m',
                        '--modules',
                        nargs='+',
                        help='Name of module(s) to test. (e.g. gnomad)')
    parser.add_argument('-t',
                        '--mod_types',
                        nargs='+',
                        help='Type of module(s) to test (e.g. annotators)')
    cmd_args = parser.parse_args()
    if cmd_args.rundir is None:
        cmd_args.rundir = 'cravat_test_' + str(int(round(time.time() * 1000)));
        
    return cmd_args;

#Loop through installed modules.  Test each one or the ones indicated
#by -m and -t options.
def main ():
 
    cmd_args = get_args();
    #create run output directory
    if not os.path.exists(cmd_args.rundir):
        os.makedirs(cmd_args.rundir);

    #installed module types 
    module_types = au.get_local_module_types();
    
    passed = 0
    failed = 0
    modules_failed = []
    for mod_type in module_types:
        if (cmd_args.mod_types is None or mod_type in cmd_args.mod_types):
            print ('\nRunning ' + mod_type + ' tests.');
            modules = au.get_local_module_infos_of_type(mod_type);
            for mod_name in modules: 
                if cmd_args.modules is None or mod_name in cmd_args.modules:
                    module = modules[mod_name];
                    if (module.has_test):
                        tester = Tester(module, cmd_args.rundir);
                        exit_code = tester.run();
                        if exit_code == 0:
                            tester.verify()
                        
                        tester.write_results()
                        if tester.test_passed:
                            passed += 1
                        else:
                            failed += 1
                            modules_failed.append(mod_name)
    modules_failed.sort()
    print ('\nTests complete.  Passed: ' + str(passed) + '  Failed: ' + str(failed) + ' [' + ', '.join(modules_failed) + ']')
if __name__ == '__main__':
    main();       
