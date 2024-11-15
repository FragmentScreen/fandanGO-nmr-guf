import core
from nmrguf.constants import ACTION_GENERATE_LIBRARY_METADATA, ACTION_GENERATE_EXPERIMENT_METADATA, ACTION_SEND_METADATA, ACTION_PRINT_PROJECT
from nmrguf.actions import generate_library_metadata, generate_experiment_metadata, send_metadata, print_project


class Plugin(core.Plugin):

    @classmethod
    def define_args(cls):

        cls.define_arg(ACTION_GENERATE_LIBRARY_METADATA, {
            'help': {'usage': '--input INPUT_FILE',
                     'epilog': '--input /path/to/excel_file.xlsx'},
            'args': {
                'input': {'help': 'excel file with fragment library, binding/non-binding summary, protein sequences and cocktails information',
                          'required': True
                          }
            }
        })

        cls.define_arg(ACTION_GENERATE_EXPERIMENT_METADATA, {
            'help': {'usage': '--logs-project-id PROJECT_ID',
                     'epilog': '--logs-project-id 129'},
            'args': {
                'logs-project-id': {'help': 'id of the LOGS project',
                                    'required': True
                                    }
            }
        })

        cls.define_arg(ACTION_SEND_METADATA, {
            'help': {'usage': '--visit-id VISIT_ID',
                     'epilog': '--visit-id 2'},
            'args': {
                'visit-id': {'help': 'ARIA visit id',
                             'required': True
                             }
            }
        })

    @classmethod
    def define_methods(cls):
        cls.define_method(ACTION_GENERATE_LIBRARY_METADATA, generate_library_metadata.perform_action)
        cls.define_method(ACTION_GENERATE_EXPERIMENT_METADATA, generate_experiment_metadata.perform_action)
        cls.define_method(ACTION_SEND_METADATA, send_metadata.perform_action)
        cls.define_method(ACTION_PRINT_PROJECT, print_project.perform_action)