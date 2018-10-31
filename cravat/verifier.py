import os
from hashlib import md5
from cravat import CravatReader

# Base class for verifiers
class Verifier():
    def __init__(self, input_path, key_path):
        self.input_path = os.path.abspath(input_path)
        self.key_path = os.path.abspath(key_path)
        
    def compare_cksum(self):
        return self._md5sum(self.key_path) == self._md5sum(self.input_path)
    
    def _md5sum(self, fpath):
        # Not secure (uses md5) or memory efficient (reads whole file to memory) 
        # Source: https://stackoverflow.com/questions/3431825/generating-an-md5-checksum-of-a-file
        return md5(open(fpath, 'rb').read()).hexdigest()
    
    def compare_details(self):
        raise NotImplementedError
        
# Verifies tab separated files with headers and row identifiers as first col
class AnnotatorVerifier(Verifier):
    
    def compare_details(self):
        self.input_reader = CravatReader(self.input_path)
        self.key_reader = CravatReader(self.key_path)
        id_col = self.key_reader.get_col_def(0)['name']
        
        failures = []
        input_by_id = {x[id_col]: x 
                            for x in self.input_reader.get_data('dict')}
        ids_checked = []
        for key_ln, key_data in self.key_reader.loop_data('dict'):
            key_id = key_data[id_col]
            ids_checked.append(key_id)
            try:
                input_data = input_by_id[key_id]
            except KeyError:
                for col_name, expected in key_data.items():
                    fail_data = {'row_id':key_id,
                                 'column':col_name,
                                 'expected':expected,
                                 'received':'MISS_ROW'}
                    failures.append(fail_data)
                continue
            for col_name, expected in key_data.items():
                try:
                    received = input_data[col_name]
                    matches = expected == received
                except KeyError:
                    received = 'NO_COLUMN'
                    matches = False
                if not(matches):
                    fail_data = {'row_id':key_id,
                                 'column':col_name,
                                 'expected':expected,
                                 'received':received}
                    failures.append(fail_data)
        new_ids = list(set(input_by_id.keys()) - set(ids_checked))
        if new_ids:
            for input_id in new_ids:
                input_data = input_by_id[input_id]
                for col_name in input_data:
                    fail_data = {'row_id':input_id,
                                 'column':col_name,
                                 'expected':'NEW_ROW',
                                 'received':input_data[col_name]}
                    failures.append(fail_data)
        return failures