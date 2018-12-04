import os
from cravat.exceptions import BadFormatError
import json
import re
from collections import OrderedDict
import yaml

class CravatFile(object):
    valid_types = ['string','int','float']
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.columns = {}
    
    def _validate_col_type(self, col_type):
        if col_type not in self.valid_types:
            raise Exception('Invalid type: %s. Choose from %s' \
                    %(col_type, ', '.join(self.valid_types)))
    
    def get_col_def(self, col_index):
        return self.columns[col_index]
    
    def get_all_col_defs(self):
        return self.columns

class CravatWriter(CravatFile):
    def __init__(self, path, 
                 include_definition=True, 
                 include_titles=True,
                 titles_prefix='#'):
        super().__init__(path)
        self.wf = open(self.path,'w')
        self._ready_to_write = False
        self.ordered_columns = []
        self.name_to_col_index = {}
        self.title_toks = []
        self.include_definition = include_definition
        self._definition_written = False
        self.include_titles = include_titles
        self._titles_written = False
        self.titles_prefix = titles_prefix
        
    def add_column(self, col_index, title, col_name, col_type, override=False):
        if col_index == 'append':
            col_index = len(self.columns)
        else:
            col_index = int(col_index)
        title = str(title)
        self._validate_col_type(col_type)
        if not(override):
            try:
                self.columns[col_index]
                raise Exception('A column is already defined for index %d.' \
                                    %col_index + ' Choose another index,'+\
                                    ' or set override to True')
            except KeyError:
                pass
        for i in self.columns:
            if self.columns[i]['name'] == col_name:
                raise Exception('A column with name %s already exists.' %col_name)
        self.columns[col_index] = {'name':col_name,
                                   'type':col_type,
                                   'title':title}
        
    def add_columns(self, col_list, append=False):
        """
        Takes a list of tuples with title, name, and type and adds all the columns
        in the list to the writer.
        """
        for col_index, col_def in enumerate(col_list):
            if append == True:
                col_index = 'append'
            self.add_column(col_index,
                            col_def['title'],
                            col_def['name'],
                            col_def['type'])
    
    def _prep_for_write(self):
        if self._ready_to_write: return
        col_indices = sorted(self.columns.keys())
        correct_index = -1
        for col_index in col_indices:
            correct_index += 1
            if correct_index != col_index:
                raise Exception('Column %d must be defined' %correct_index)
            col_def = self.columns[col_index]
            self.ordered_columns.append(col_def)
            self.title_toks.append(col_def['title'])
            self.name_to_col_index[col_def['name']] = col_index
        self._ready_to_write = True

    def write_names (self, annotator_name, annotator_display_name):                    
        line = '#name={:}\n'.format(annotator_name)
        self.wf.write(line)
        line = '#displayname={:}\n'.format(annotator_display_name)
        self.wf.write(line)
        self.wf.flush()
        
    def add_index (self, index_columns):
        """
        On aggregation, an index will be created across the supplied columns.
        """
        self.write_meta_line('index',','.join(index_columns))
    
    def write_meta_line(self, key, value):
        line = '#{:}={:}\n'.format(key,value)
        self.wf.write(line)
        self.wf.flush()
        
    def write_definition(self, conf=None):
        self._prep_for_write()
        for col_index, col_def in enumerate(self.ordered_columns):
            col_def_line = '#column=%d,%s,%s,%s\n' %(col_index,
                                                     col_def['title'],
                                                     col_def['name'],
                                                     col_def['type'])
            self.wf.write(col_def_line)
        if conf and 'report_substitution' in conf:
            self.wf.write('#report_substitution={}\n'.format(
                json.dumps(conf['report_substitution'])))
        self._definition_written = True
        self.wf.flush()
    
    def write_report_substitution (self):
        self._prep_for_write()
    def write_titles(self):
        self._prep_for_write()
        title_line = self.titles_prefix+'\t'.join(self.title_toks) + '\n'
        self.wf.write(title_line)
        self._titles_written = True
        self.wf.flush()
    
    def write_data(self, data):
        self._prep_for_write()
        if self.include_definition and not(self._definition_written): 
            self.write_definition()
        if self.include_titles and not(self._titles_written): 
            self.write_titles()
        wtoks = [''] * len(self.name_to_col_index)
        for col_name in data:
            try:
                col_index = self.name_to_col_index[col_name]
            except KeyError:
                continue
            if data[col_name] is not None:
                wtoks[col_index] = str(data[col_name])
            else:
                wtoks[col_index] = ''
        self.wf.write('\t'.join(wtoks)+'\n')
        
    def close(self):
        self.wf.close()


class CrxMapping(object):
    
    def __init__(self):
        self.protein = None
        self.achange = None
        self.transcript = None
        self.tchange = None
        self.so = None
        self.gene = None
        self.tref = None
        self.tpos_start = None
        self.talt = None
        self.aref = None
        self.apos_start = None
        self.aalt = None
        self.tchange_re = re.compile(r'([AaTtCcGgUuNn_-]+)(\d+)([AaTtCcGgUuNn_-]+)')
        self.achange_re = re.compile(r'([a-zA-Z_\*]+)(\d+)([AaTtCcGgUuNn_\*]+)')
        
    def load_tchange(self, tchange):
        self.tchange = tchange
        if tchange is not None:
            self.parse_tchange()
    
    def parse_tchange(self):
        tchange_match = self.tchange_re.match(self.tchange)
        if tchange_match:
            self.tref = tchange_match.group(1)
            self.tpos_start = int(tchange_match.group(2))
            self.talt = tchange_match.group(3)
            
    def load_achange(self, achange):
        self.achange = achange
        if self.achange is not None:
            self.parse_achange()
    
    def parse_achange(self):
        achange_match = self.achange_re.match(self.achange)
        if achange_match:
            self.aref = achange_match.group(1)
            self.apos_start = int(achange_match.group(2))
            self.aalt = achange_match.group(3)
            
class AllMappingsParser (object):

    def __init__(self, s):
        self._d = json.loads(s,object_pairs_hook=OrderedDict)
        self._protein_index = 0
        self._achange_index = 1
        self._so_index = 2
        self._transc_index = 3
        self._tchange_index = 4
        self.mappings = self.get_all_mappings()
    
    def get_genes(self):
        """
        Get list of all genes present
        """
        return list(self._d.keys())
    
    def get_uniq_sos (self):
        sos = {}
        for mapping in self.mappings:
            sos[mapping.so] = True
        sos = list(sos.keys())
        return sos
    
    def get_uniq_sos_for_gene (self, genes=[]):
        sos = {}
        for mapping in self.mappings:
            if mapping.gene in genes:
                sos[mapping.so] = True
        sos = list(sos.keys())
        return sos
    
    def none_to_empty (self, s):
        if s == None:
            return ''
        else:
            return s
    
    def get_mapping (self, t):
        mapping = CrxMapping()
        mapping.transcript = self.none_to_empty(t[self._transc_index])
        mapping.so = self.none_to_empty(t[self._so_index])
        mapping.load_tchange(self.none_to_empty(t[self._tchange_index]))
        mapping.load_achange(self.none_to_empty(t[self._achange_index]))
        mapping.protein = self.none_to_empty(t[self._protein_index])
        return mapping
    
    def get_all_mappings (self):
        mappings = []
        for gene, ts in self._d.items():
            for t in ts:
                mapping = self.get_mapping(t)
                mapping.gene = gene
                mappings.append(mapping)
        return mappings
                
    def get_transcript_mapping (self, transcript):
        for mapping in self.mappings:
            if mapping.transcript == transcript:
                return mapping
        return None

    def get_mapping_str (self, mapping):
        tr = mapping.transcript
        protein = mapping.protein
        achange = mapping.achange
        so = mapping.so
        tchange = mapping.tchange
        gene = mapping.gene
        s = protein + ':' + achange + ':' + tr + ':' + tchange + ':' + \
            so + ':' + gene
        return s
        
class CravatReader (CravatFile):
    def __init__(self, path):
        super().__init__(path)
        self.annotator_name = ''
        self.annotator_displayname = ''
        self.no_aggregate_cols = []
        self.valid_modes = ['line','list','dict']
        self.default_mode = 'dict'
        self.index_columns = []
        self.report_substitution = None
        self._setup_definition()
        
    def _setup_definition (self):
        for l in self._loop_definition():
            if l.startswith('#name='):
                self.annotator_name = l.split('=')[1]
            elif l.startswith('#displayname='):
                self.annotator_displayname = l.split('=')[1]
            elif l.startswith('#no_aggregate='):
                self.no_aggregate_cols = l.split('=')[1].split(',')
            elif l.startswith('#index='):
                cols = l.split('=')[1].split(',')
                self.index_columns.append(cols)
            elif l.startswith('#column='):
                col_info = l.split('=')[1].split(',')
                col_index = int(col_info[0])
                col_title = col_info[1]
                col_name = col_info[2]
                col_type = col_info[3]
                self._validate_col_type(col_type)
                self.columns[col_index] = {'title':col_title,
                                           'name':col_name,
                                           'type':col_type}
            elif l.startswith('#report_substitution='):
                self.report_substitution = json.loads(l.split('=')[1])
            else:
                continue
        
    def get_index_columns(self):
        return self.index_columns
    
    def override_column(self, index, name, title=None, data_type=None):
        if title == None:
            title = ' '.join(x.title() for x in name.split('_'))
        if data_type == None:
            data_type = 'string'
        self.columns[index] = {'title':title,
                               'name':name,
                               'type':data_type}

    def get_column_names(self):
        sorted_order = sorted(list(self.columns.keys()))
        return [self.columns[x]['name'] for x in sorted_order]
    
    def get_annotator_name (self):
        return self.annotator_name
    
    def get_annotator_displayname (self):
        return self.annotator_displayname
    
    def get_no_aggregate_columns (self):
        return self.no_aggregate_cols
        
    def _check_mode(self, mode):
        if mode not in self.valid_modes:
            raise Exception('Invalid mode: %s. Choose from %s' \
                                %(mode, ', '.join(self.valid_modes)))
    def set_mode(self, mode):
        self._check_mode(mode)
        self.default_mode = mode

    def loop_data(self, mode=None):
        if mode:
            self._check_mode(mode)
        else:
            mode = self.default_mode
        for lnum, l in self._loop_data():
            data = None
            if mode == 'line':
                data = l
            elif mode == 'list':
                data = l.split('\t')
            elif mode == 'dict':
                data = self.line_to_data_dict(l)
            yield lnum, data
        
    def get_data(self, mode=None):
        if mode:
            self._check_mode(mode)
        else:
            mode = self.default_mode
        all_data = []
        for _, l in self._loop_data():
            if mode == 'line':
                all_data.append(l)
            elif mode == 'list':
                all_data.append(l.split('\t'))
            elif mode == 'dict':
                all_data.append(self.line_to_data_dict(l))
        return all_data
    
    def line_to_data_dict(self, l):
        toks = l.split('\t')
        return self.toks_to_data_dict(toks)
    
    def toks_to_data_dict(self, toks):
        out = {}
        if len(toks) < len(self.columns):
            err_msg = 'Too few columns. Received %s. Expected %s' \
                %(len(toks),len(self.columns))
            raise BadFormatError(err_msg)
        for col_index, col_def in self.columns.items():
            col_name = col_def['name']
            col_type = col_def['type']
            tok = toks[col_index]
            if tok == '':
                out[col_name] = None
            else:
                if col_type == 'string':
                    out[col_name] = tok
                elif col_type == 'int':
                    out[col_name] = int(tok)
                elif col_type == 'float':
                    out[col_name] = float(tok)
                else:
                    out[col_name] = tok
        return out
        
    def _loop_definition(self):
        f = open(self.path)
        for l in f:
            l = l.rstrip().lstrip()
            if l.startswith('#'):
                yield l
            else:
                break
        f.close()
            
    def _loop_data(self):
        f = open(self.path)
        lnum = 0
        for l in f:
            lnum += 1
            l = l.rstrip('\r\n')
            if l.startswith('#'):
                continue
            else:
                yield lnum, l
        f.close()
        
if __name__ == '__main__':
    import sys
    cw = CravatWriter(sys.argv[1])
    cw.add_column(3, 'col1', 'string', 'String')
    cw.add_column(2, 'col2', 'float', 'Float')
    cw.add_column(1, 'col3', 'int', 'Int')
    c1 = ''
    c2 = 0.0
    c3 = 0
    for i in range(10):
        c1 += 'k'
        c2 += 0.3
        c3 += 1
        data = {'col1':c1, 'col2':c2, 'col3':c3}
        cw.write_data(data)
    cw.close()
    
    cr = CravatReader(sys.argv[1])
    for data in cr.loop_data():
        print(data)
