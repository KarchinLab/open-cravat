import json
import time

import requests
from flask import abort, jsonify

from cravat import admin_util as au
from cravat import InvalidData, get_module
from cravat.gui.api.live_module_cache import LiveModuleCache

from . import routes

def initialize(application):
    routes.load(application)

sysconf = au.get_system_conf()
count_single_api_access = 0
time_of_log_single_api_access = time.time()
interval_log_single_api_access = 60

def format_hgvs_string(hgvs_input):
    hgvs_parts = hgvs_input.upper().split(':')
    if len(hgvs_parts) != 2:
        raise InvalidData('HGVS input invalid.')
    prefix = hgvs_parts[1][0].lower()
    # TODO: if HGVS API is upgraded to support p., change this here to allow it on single variant page
    if prefix not in ('g', 'c'):
        raise InvalidData('HGVS input invalid. Only g. and c. prefixes are supported.')
    end = hgvs_parts[1][1:]
    return f'{hgvs_parts[0]}:{prefix}{end}'

def get_coordinates_from_hgvs_api(queries):
    if 'hgvs_api_url' not in sysconf:
        raise abort(500, description='"hgvs_api_url" not found in open cravat configuration.')
    hgvs_input = format_hgvs_string(queries.get('hgvs'))
    data = {'hgvs': hgvs_input}
    headers = {'Content-Type': 'application/json'}
    resp = requests.post(sysconf['hgvs_api_url'], data=json.dumps(data), headers=headers, timeout=20)
    try:
        resp.raise_for_status()
    except Exception as e:
        raise InvalidData(f"Error retrieving data from HGVS API. {hgvs_input} {e}")
    tokens = resp.json()
    return {
        'chrom': tokens['chrom'],
        'pos': tokens['pos'],
        'ref_base': tokens['ref'],
        'alt_base': tokens['alt'],
        'assembly': tokens['assembly']
    }

def format_allele(base):
    base_string = str(base)
    if not base_string or base_string == '':
        base_string = '-'
    return base_string

def coordinates_from_clingen_json(ca_id, data):
    genomic_alleles = data.get('genomicAlleles')
    for ga in genomic_alleles:
        if ga.get('referenceGenome') == 'GRCh38':
            coords = ga.get('coordinates')[0]
            return {
                'chrom': f'chr{ga.get("chromosome")}',
                'pos': int(coords.get('start')) + 1,
                'ref_base': format_allele(coords.get('referenceAllele')),
                'alt_base': format_allele(coords.get('allele')),
                'assembly': 'hg38'
            }
    raise abort(400, description=f'Could not find hg38 coordinates for clingen allele id {ca_id}.')


def get_coordinates_from_clingen_id(queries):
    if 'clingen_api_url' not in sysconf:
        raise abort(500, description='"clingen_api_url" not found in open cravat configuration.')
    ca_id = queries['clingen'].strip().upper()
    headers = {'Content-Type': 'application/json'}
    request_url = f"{sysconf['clingen_api_url']}/{ca_id}"
    resp = requests.get(request_url, headers=headers, timeout=20)
    try:
        resp.raise_for_status()
    except Exception as e:
        raise InvalidData(f"Error retrieving data from Clingen Allele registry. Clingen Allele Registry Id should be formatted like 'CA12345'. {e}")
    data = resp.json()
    return coordinates_from_clingen_json(ca_id, data)


def get_coordinates_from_dbsnp(queries):
    converter_module = get_module('dbsnp-converter')
    converter = converter_module()

    dbsnp = queries.get('dbsnp').strip().lower()
    try:
        all_params = converter.convert_line(dbsnp)
    except Exception as e:
        raise InvalidData(f"Could not parse DBSNP '{dbsnp}'. Should be formatted like 'rs12345'.")
    params = all_params[0]
    params['assembly'] = 'hg38'
    alternates = None
    if len(all_params) > 1:
        alternates = all_params[1:]
    return params, alternates


def get_coordinates_from_request_params(queries):
    parameters = {}
    original_input = {}
    alternate_alleles = None
    required_coordinate_params = {'chrom', 'pos', 'ref_base', 'alt_base'}
    if (required_coordinate_params <= queries.keys()
            and None not in {queries[x] for x in required_coordinate_params}):
        parameters = {
            x: queries[x] for x in required_coordinate_params
        }
        parameters['chrom'] = parameters['chrom'].lower()
        try:
            parameters['pos'] = int(parameters['pos'])
        except ValueError as e:
            raise(abort(400, description="'pos' parameter could not be parsed to int."))
        original_input = {'type': 'coordinates', 'input': f'{queries["chrom"]} {queries["pos"]} {queries["ref_base"]} {queries["alt_base"]} {queries.get('assembly')}'}
    elif 'hgvs' in queries.keys() and queries['hgvs'] and 'assembly' in queries.keys():
        # make hgvs api call
        original_input = {'type': 'hgvs', 'input': queries['hgvs']}
        parameters = get_coordinates_from_hgvs_api(queries)
    elif 'clingen' in queries.keys() and queries.get('clingen'):
        # make clingen api call
        original_input = {'type': 'clingen', 'input': queries['clingen']}
        parameters = get_coordinates_from_clingen_id(queries)
    elif 'dbsnp' in queries.keys() and queries.get('dbsnp'):
        # use dbsnp-converter
        original_input = {'type': 'dbsnp', 'input': queries['dbsnp']}
        parameters, alternate_alleles = get_coordinates_from_dbsnp(queries)
    else:
        raise abort(400, description='Required parameters missing. Need either "chrom", "pos", "ref_base", and "alt_base", or "hgvs", or "dbsnp", or "clingen". Parameter "assembly" always required.')
    parameters['uid'] = queries.get('uid', '')
    if 'annotators' in queries.keys():
        parameters['annotators'] = queries.get('annotators', '')
    return parameters, original_input, alternate_alleles


def live_annotate_worker (queries, annotators, is_multiuser):
    if is_multiuser:
        from cravat.gui.multiuser.db import AdminDb
        global count_single_api_access
        global time_of_log_single_api_access
        global interval_log_single_api_access
        count_single_api_access += 1
        admindb = AdminDb()

        t = time.time()
        dt = t - time_of_log_single_api_access
        if dt > interval_log_single_api_access:
            admindb.write_single_api_access_count_to_db(t, count_single_api_access)
            time_of_log_single_api_access = t
            count_single_api_access = 0

    try:
        coords, original_input, alternate_alleles = get_coordinates_from_request_params(queries)
    except Exception as e:
        text = str(e)
        print(text)
        q = {key: value for key, value in queries.items()}
        return jsonify(data={'error': text, 'originalInput': q})
    live_mapper = LiveModuleCache()
    assembly = queries.get('assembly', 'hg38')
    if assembly != 'hg38':
        live_mapper.load_lifter(assembly)
        coords = live_mapper.liftover(coords, assembly)
    live_mapper.load_live_mapper()
    live_mapper.load_live_annotators(annotators)
    response = live_mapper.get_live_annotation(coords, annotators)
    response['originalInput'] = original_input
    response['alternateAlleles'] = alternate_alleles
    return response
