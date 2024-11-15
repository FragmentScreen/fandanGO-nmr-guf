import configparser
import os
from nmrguf.db.sqlite_db import update_project
import json
import pandas as pd

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config.yaml'))
metadata_output_path = config['METADATA'].get('OUTPUT_PATH')


def generate_library_metadata(project_name, input_file):
    """
    Function that generates metadata for a FandanGO project based on the Excel file with the analyzed data (with fragment library, binding/non-binding summary, protein sequences and cocktails information)

    Args:
        project_name (str): FandanGO project name
        input_file (str): path of the Excel file
    Returns:
        success (bool): if everything went ok or not
        info (dict): info metadata path
    """

    print(f'FandanGO will create library metadata for FandanGO project {project_name} based on the Excel file placed at {input_file}...')
    success = False
    info = None

    try:
        fragment_library = pd.read_excel(input_file, sheet_name='Fragment Library')
        summary = pd.read_excel(input_file, sheet_name='Summary')
        protein_sequence = pd.read_excel(input_file, sheet_name='Protein Sequence')
        cocktails = pd.read_excel(input_file, sheet_name='cocktails')

        mixtures = {}
        for index, row in cocktails.iterrows():
            mix_name = row['mix']
            compounds = []
            for i in range(1, 13):
                compound = row[f'compound {i}']
                if pd.isnull(compound):
                    break
                compounds.append(compound)
            mixtures[mix_name] = compounds

        def find_compounds_by_mix(mix_name):
            return mixtures[mix_name]

        def find_SMILES_Formula_by_compound(compound_name):
            row = fragment_library[fragment_library['Spectrum'] == compound_name]
            if row.empty:
                return None
            return row['SMILES Formula'].values[0]

        def find_summary_info_from_compound(compound_name):
            row = summary[summary['Spectrum'] == compound_name]
            if row.empty:
                return None
            bindingstate = row['Bindingstate'].values[0]
            waterlogsy = row['Waterlogsy'].values[0]
            T2 = row['T2'].values[0]
            CSP = row['CSP'].values[0]
            STD = row['STD'].values[0]
            return_info = {
                'bindingstate': bindingstate,
                'waterlogsy': waterlogsy,
                'T2': T2,
                'CSP': CSP,
                'STD': STD
            }
            return return_info

        def package_info(mix_name):
            compounds = find_compounds_by_mix(mix_name)
            mix = {}
            mix['compounds'] = {}
            for compound in compounds:
                compound_info = {}
                compound_info['smiles_formula'] = find_SMILES_Formula_by_compound(compound)
                compound_info['summary_info'] = find_summary_info_from_compound(compound)
                mix['compounds'][compound] = compound_info
            return mix

        def convert_mix_to_json(mix):
            mix = {
                mix_name: {
                    'compounds': {
                        compound: {
                            'smiles_formula': info['smiles_formula'],
                            'summary_info': info['summary_info']
                        }
                        for compound, info in mix['compounds'].items()
                    }
                }
            }
            return str(mix).replace("'", '"')

        all_mixes = []
        for mix_name in mixtures:
            mix = package_info(mix_name)
            all_mixes.append(convert_mix_to_json(mix))

        all_mixes = '[' + ','.join(all_mixes) + ']'

        library_metadata_path = os.path.join(metadata_output_path, f'{project_name}_analyzed_metadata.json')

        with open(library_metadata_path, 'w') as metadata_file:
            json.dump(json.loads(all_mixes), metadata_file, indent=2)
        success = True
        update_project(project_name, 'library_metadata_path', library_metadata_path)
        info = {'library_metadata_path': library_metadata_path}

    except ValueError:
        info = (f'... there was a problem reading the file. Make sure it is an Excel file (.xlsx)')
        success = False

    except Exception as e:
        info = (f'... Something went wrong: {e}')
        success = False

    return success, info


def perform_action(args):
    success, info = generate_library_metadata(args['name'], args['input'])
    results = {'success': success, 'info': info}
    return results
