import core
from nmrguf.constants import ACTION_GENERATE_METADATA, ACTION_SEND_METADATA, ACTION_PRINT_PROJECT
from nmrguf.actions import generate_metadata, send_metadata, print_project


class Plugin(core.Plugin):

    @classmethod
    def define_args(cls):
        cls.define_arg(ACTION_GENERATE_METADATA, {
            'help': {'usage': '--logs-dataset-id DATASET_ID',
                     'epilog': '--logs-dataset-id 225957'},
            'args': {
                'logs-dataset-id': {'help': 'id of the LOGS dataset',
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
        cls.define_method(ACTION_GENERATE_METADATA, generate_metadata.perform_action)
        cls.define_method(ACTION_SEND_METADATA, send_metadata.perform_action)
        cls.define_method(ACTION_PRINT_PROJECT, print_project.perform_action)