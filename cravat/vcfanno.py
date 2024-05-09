import gzip
import logging
import multiprocessing as mp
import itertools as IT
import os
import queue
import shutil
import sys
import time
import subprocess
import pathlib
from io import StringIO
from collections import OrderedDict
import cravat
import vcf
import json
from cravat.inout import AllMappingsParser
try:
    from Bio import bgzf
except ModuleNotFoundError:
    bgzf = None
    pass

# from vcf_line_processor import VCFLineProcessor

class VCFLineProcessor(object):

    perc_encode = [
        [r'%', r'%25'],
        [r':', r'%3A'],
        [r';', r'%3B'],
        [r'=', r'%3D'],
        [r',', r'%2C'],
        [r'\n', r'%0A'],
        [r'\t', r'%09'],
        [r'\r', r'%0D'],
        [r' ', r'%20']
    ]

    so_full = {
                "PTR": "processed_transcript", "TU1": "transcribed_unprocessed_pseudogene", "UNP": "unprocessed_pseudogene",
                "MIR": "miRNA", "LNC": "lnc_RNA", "PPS": "processed_pseudogene", "SNR": "snRNA", "TPR": "transcribed_processed_pseudogene",
                "RTI": "retained_intron", "NMD": "NMD_transcript_variant", "MCR": "misc_RNA", "UNT": "unconfirmed_transcript",
                "PSE": "pseudogene", "TU2": "transcribed_unitary_pseudogene", "NSD": "NSD_transcript", "SNO": "snoRNA", "SCA": "scaRNA",
                "PRR": "pseudogene_rRNA", "UPG": "unitary_pseudogene", "PPG": "polymorphic_pseudogene", "RRN": "rRNA", "IVP": "IG_V_pseudogene",
                "RIB": "ribozyme", "SRN": "sRNA", "TVG": "TR_V_gene", "TVP": "TR_V_pseudogene", "TDG": "TR_D_gene", "TJG": "TR_J_gene",
                "TCG": "TR_C_gene", "TJP": "TR_J_pseudogene", "ICG": "IG_C_gene", "ICP": "IG_C_pseudogene", "IJG": "IG_J_gene",
                "IJP": "IG_J_pseudogene", "IDG": "IG_D_gene", "IVG": "IG_V_gene", "IGP": "IG_pseudogene", "TPP": "translated_processed_pseudogene",
                "SCR": "scRNA", "VLR": "vault_RNA", "TUP": "translated_unprocessed_pseudogene", "MTR": "Mt_tRNA", "MRR": "Mt_rRNA",
                "2KD": "2kb_downstream_variant", "2KU": "2kb_upstream_variant", "UT3": "3_prime_UTR_variant", "UT5": "5_prime_UTR_variant",
                "INT": "intron_variant", "UNK": "unknown", "SYN": "synonymous_variant", "MRT": "start_retained_variant", "STR": "stop_retained_variant",
                "MIS": "missense_variant", "CSS": "complex_substitution", "STL": "stop_lost", "SPL": "splice_site_variant", "STG": "stop_gained",
                "FSD": "frameshift_truncation", "FSI": "frameshift_elongation", "INI": "inframe_insertion", "IND": "inframe_deletion",
                "MLO": "start_lost", "EXL": "exon_loss_variant", "TAB": "transcript_ablation"
                }

    valid_bases = set('ATGC')

    skip_cnames = set(['uid','note','note_variant','note_gene','chrom','pos','ref_base','alt_base'])

    type_oc2vcf = {
        'string':'String',
        'int':'Integer',
        'float':'Float',
    }
    
    oc_base_headers = [
        '##INFO=<ID=OC_ERROR,Number=1,Type=String,Description="Error message for failed OpenCRAVAT annotation">'
    ]

    def __init__(self, annotator_names = []):
        self._buffer = StringIO()
        self._reader = None
        self.reader_ready = False
        self._mapper = cravat.get_live_mapper('hg38')
        self._annotators = OrderedDict()
        for aname in annotator_names:
            self._annotators[aname] = cravat.get_live_annotator(aname)

        self.oc_headers = []+self.oc_base_headers
        for column in cravat.constants.crx_def:
            if column['name'] in self.skip_cnames:
                continue
            self.oc_headers.append(self.get_info_line(None, column))
        for aname, annotator in self._annotators.items():
            for column in annotator.conf['output_columns']:
                self.oc_headers.append(self.get_info_line(aname, column))
        
    def initialize_reader(self, header_lines):
        for l in header_lines:
            if l.startswith('##'):
                self._buffer.write(l)
            elif l.startswith('#CHROM'):
                toks = l.strip().split('\t')
                nsl = '\t'.join(toks[:8])
                self._buffer.write(nsl+'\n')
                self._buffer.seek(0)
                self._reader = vcf.Reader(self._buffer)
                self._buffer.seek(0)
                self._buffer.truncate()
        self.reader_ready = True
    
    def annotate_line(self, input_line):
        toks = input_line.strip().split('\t')
        nsl = '\t'.join(toks[:8])
        info = toks[7]
        self._buffer.seek(0)
        self._buffer.truncate()
        self._buffer.write(nsl+'\n')
        self._buffer.seek(0)
        variant = next(self._reader)
        annots, successful = self.get_oc_info_annotations(variant)
        info = ';'.join([info]+annots)
        wtoks = toks[:7]+[info]+toks[8:]
        return '\t'.join(wtoks)+'\n', successful

    def get_oc_infoname(self, modname, colname):
        toks = ['OC']
        if modname is not None:
            toks.append(modname)
        toks.append(colname)
        return '_'.join(toks).upper()

    def get_info_line(self, modname, oc_coldef):
        info_name = self.get_oc_infoname(modname, oc_coldef['name'])
        info_type = self.type_oc2vcf[oc_coldef['type']]
        info_desc = oc_coldef.get('desc','')
        info_line = '##INFO=<ID={},Number=A,Type={},Description="{}">'.format(
            info_name,
            info_type,
            info_desc
        )
        return info_line
    
    def vcf_encode(self, orig):
        new = orig
        if type(new) == str:
            for k,v in self.perc_encode:
                new = new.replace(k,v)
        return new
    
    def make_info_entry(self, mname, cname, value):
        info_cname = self.get_oc_infoname(mname, cname)
        info_value = self.vcf_encode(value)
        info_text = f'{info_cname}={info_value}'
        return info_text
    
    def get_oc_info_annotations(self, variant):
        info_toks = []
        if not variant.CHROM.startswith('chr'):
            chrom = 'chr'+str(variant.CHROM)
        else:
            chrom = variant.CHROM
        pos = variant.POS
        ref = variant.REF
        alt = None
        try:
            alt = variant.ALT[0].sequence
        except:
            info_toks.append(f'OC_ERROR=Cannot_annotate_ALT_"{variant.ALT[0]}"')
            return info_toks, False
        if not(set(alt.upper()).issubset(self.valid_bases)):
            info_toks.append(f'OC_ERROR=Cannot_annotate_ALT_"{alt}"')
            return info_toks, False
        if not(set(ref.upper()).issubset(self.valid_bases)):
            info_toks.append(f'OC_ERROR=Cannot_annotate_REF_"{ref}"')
            return info_toks, False
        crv = {'chrom':chrom,'pos':pos,'ref_base':ref,'alt_base':alt}
        mapping = self._mapper.map(crv)
        mapping['so'] = self.so_full.get(mapping['so'], mapping['so'])
        for cname, value in mapping.items():
            if cname in self.skip_cnames:
                continue
            if value == '':
                continue
            elif value is None:
                continue
            if cname == 'all_mappings':
                if value=='{}':
                    continue
                else:
                    value = json.loads(value)
                    for gene in value:
                        for hit in value[gene]:
                            hit[2] = self.so_full.get(hit[2], hit[2])
                    value = json.dumps(value, separators=(',', ':'))
            info_entry = self.make_info_entry(None, cname, value)
            info_toks.append(info_entry)
        crx = mapping
        crx['mapping_parser'] = AllMappingsParser(crx['all_mappings'])
        annotations = {aname: annotator.annotate(crx) for aname, annotator in self._annotators.items()}
        for aname in self._annotators:
            annot_out = annotations[aname]
            if type(annot_out) != dict:
                continue
            for cname, value in annot_out.items():
                if value is None:
                    continue
                info_entry = self.make_info_entry(aname, cname, value)
                info_toks.append(info_entry)
        return info_toks, True

class VCFAnnotator(object):
    """Annotate a VCF using the VCFLineProcessor to output.

    This VCF annotator will read a VCF from `input_file` and output a VCF with annotations to `output_file. To improve
    performance, multiprocessing will be used on pieces of the input file to be annotated separately. The annotated
    output will be written to a temporary filed, numbered sequentially so that it can be combined into a single VCF
    once all the pieces are complete.

    input_path: str - The input VCF file to be annotated
    output_path: str - The path to place the VCF file. Default: {input_path}.opencravat.vcf
    temp_dir: str - A path to a directory where temporary output files will be stored. This should be an empty directory.
                    If temp_dir is not empty, the output may become corrupted.
    annotators: list[str] - The list of open cravat annotators to apply to the input
    processors: int - The number of worker processors to use. Default: multiprocessing.cpu_count()
    chunk_size: int - The number of lines of input to send to each worker process. This parameter should be chosen so that
                      the total memory will not exceed that of the machine. This annotator will read `chunk_size` * `processors`
                      lines of input at a time. Default: 10,000
    chunk_log_frequency: int - The number of chunks to process before logging status. For large input files, it may
                               be useful to limit the number of status updates logs. This parameter will limit the logs
                               to one per `chunk_log_frequency` chunks. Default: 1
    """
    def __init__(self, input_path: str, output_path: str = '', temp_dir: str = 'temp',
                 annotators: list[str] = None, processors: int = -1, chunk_size: int = 10**4,
                 chunk_log_frequency: int = 1):
        if annotators is None:
            annotators = []
        self.annotators = annotators
        self.input_path = input_path
        if output_path == '':
            output_path = f'{input_path}.opencravat.vcf'
        self.output_path = output_path
        self.temp_dir = temp_dir
        self.line_processor = VCFLineProcessor(annotators)
        self.header_lines = []
        if processors < 1:
            processors = mp.cpu_count()
        self.processors = processors
        print(__name__)
        self.logger = logging.getLogger(__name__)
        self.chunk_size = chunk_size
        self.chunk_log_frequency = chunk_log_frequency
        self.temp_file_name_gen = self._next_temp_file_name()

    def _next_temp_file_name(self):
        """Generator for a numbered sequence of filenames for temporary output"""
        c = 0
        while True:
            yield f'{c}.{self.output_path}'
            c += 1

    def process_header(self, file):
        """Read the file to find out where the data starts, return the line number of the first data"""
        header_path = pathlib.Path(self.temp_dir)
        header_file_name = header_path / next(self.temp_file_name_gen)
        header_path.mkdir(exist_ok=True)
        with bgzf.open(filename=header_file_name, mode='wt') as header_file:
            for line in file:
                if line.startswith('##'):
                    self.header_lines.append(line)
                    header_file.write(line)
                elif line.startswith('#CHROM'):
                    self.header_lines.append(line)
                    for oc_header_line in self.line_processor.oc_headers:
                        header_file.write(oc_header_line + os.linesep)
                    header_file.write(line)
                    if not self.line_processor.reader_ready:
                        self.line_processor.initialize_reader(self.header_lines)
                    return len(self.header_lines)

    def _process_chunk(self, data, identifier):
        """Annotate a chunk of lines and output to a temporary file"""
        out_path = os.path.join(self.temp_dir, identifier)
        error_count = 0
        try:
            with bgzf.open(filename=out_path, mode='wt') as out:
                for line in data:
                    try:
                        annotated, successful = self.line_processor.annotate_line(line)
                        if not successful:
                            error_count += 1
                        out.write(annotated)
                    except Exception as e:
                        out.write(line)
                        self.logger.error(f'Uncaught exception annotating line. \n  {line}\n  {e.args}')
                        import traceback
                        traceback.print_exc(e)
        except IOError:
            return False, error_count

        return True, error_count

    def _worker(self, in_queue, out_queue, file_complete):
        """Worker process function to wait for an item in the in_queue, then process it and pass it to out_queue when complete"""
        total_errors = 0
        while True:
            time.sleep(.01)
            params = None
            try:
                params = in_queue.get(block=False)
            except queue.Empty:
                pass
            if params is None and file_complete.value:
                break
            elif params is not None:
                result, error_count = self._process_chunk(**params)
                total_errors += error_count
                out_queue.put(result)
        if total_errors > 0:
            self.logger.info(f'Annotation errors: {total_errors}')
        return total_errors

    def multi_process_data(self, file):
        """Create worker processes and feed batches of data to each until the given file is read"""
        self.logger.info(f'Beginning multiprocessing; processors: {self.processors}; chunk_size: {self.chunk_size}; chunk_log_frequency: {self.chunk_log_frequency}')
        self.logger.info(f'Annotators: {self.annotators}')
        tic = time.perf_counter()

        # Queues for worker processes
        in_queue = mp.Queue()
        out_queue = mp.Queue()
        file_complete = mp.Value('B', 0)
        chunk_count = 0
        chunks_iter = iter(lambda: list(IT.islice(file, self.chunk_size)), [])  # read the file in lists of (chunk_size) lines

        # seed the input queue
        for _ in range(0, self.processors):
            in_queue.put(obj={'data': next(chunks_iter), 'identifier': next(self.temp_file_name_gen)})
            chunk_count += 1

        # start the worker processes
        workers = []
        for _ in range(0, self.processors):
            worker = mp.Process(target=self._worker,
                                kwargs={'in_queue': in_queue, 'out_queue': out_queue, 'file_complete': file_complete})
            worker.start()
            workers.append(worker)

        # continue to add data to workers until the file is fully read
        while True:
            done = out_queue.get(block=True)
            try:
                chunk = next(chunks_iter)
                work = {'data': chunk, 'identifier': next(self.temp_file_name_gen)}
                in_queue.put(work)
                chunk_count += 1
                if chunk_count % self.chunk_log_frequency == 0:
                    lap = time.perf_counter()
                    self.logger.info(f'{chunk_count:5d} chunks read. {lap-tic:0.6f}s')
            except StopIteration:
                self.logger.info('Input fully queued.')
                file_complete.value = True
                break

        # wait for all processes to end
        for w in workers:
            w.join()
        toc = time.perf_counter()
        self.logger.info(f'Results completed: {chunk_count}')
        self.logger.info(f'Process time: {toc - tic:0.4f}')
        return

    def _is_temp_output_file(self, filename):
        """Returns True if `filename` is a file in `temp_dir`, includes a '.', and starts with an int. e.g. '1.file.ext'"""
        if not os.path.isfile(os.path.join(self.temp_dir, filename)):
            return False
        dot_index = filename.find('.')
        if dot_index < 0:
            return False
        return filename[:dot_index].isdigit()

    def merge_output(self):
        """Finds all files in `temp_dir` that begin with a number and concatenates them sequentially"""
        tic = time.perf_counter()
        self.logger.info('Merging contents')
        dir_contents = os.listdir(self.temp_dir)
        files = [name for name in dir_contents if self._is_temp_output_file(name)]
        sorted_files = sorted(files, key=lambda f: int(f[:f.find('.')]))
        count = 0
        with open(self.output_path, mode='wb') as out_file:
            for f in sorted_files:
                path = os.path.join(self.temp_dir, f)
                with open(path, mode='rb') as in_file:
                    shutil.copyfileobj(in_file, out_file)
                os.remove(path)
                count += 1
                if count % self.chunk_log_frequency == 0:
                    self.logger.info(f'{count} files merged')
        toc = time.perf_counter()
        self.logger.info('Done merging contents')
        self.logger.debug(f'Time: {toc - tic:0.4f}')

    def process(self):
        """Reads the `input_path` and performs the multiprocessing annotation"""
        with gzip.open(self.input_path, mode='rt') as gzip_file:
            header_count = self.process_header(gzip_file)
            self.multi_process_data(gzip_file)

        self.merge_output()

def vcfanno(args):
    try:
        from Bio import bgzf
    except ModuleNotFoundError:
        raise ModuleNotFoundError('vcfanno requires biopython. Try running "pip install biopython".')
    input_path = pathlib.Path(args.input_path)
    if args.output_path is not None:
        output_path = args.output_path
    else:
        output_path = pathlib.Path(str(input_path)+'.oc.vcf.gz')
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    nthreads = args.threads if args.threads else mp.cpu_count()
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[handler]
    )
    anno = VCFAnnotator(
        input_path = str(input_path),
        output_path = str(output_path),
        temp_dir = args.temp_dir,
        processors = args.threads if args.threads else mp.cpu_count(),
        chunk_size= args.chunk_size,
        chunk_log_frequency = 50,
        annotators = args.annotators,
        )
    anno.process()
