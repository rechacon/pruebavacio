# -*- coding: utf-8 -*-

{
    'name': 'Conexión GP',
    'version': '1.0',
    'author': 'Franyer Hidalgo - VE',
    'website': '',
    'images': [],
    'category': 'Uncategorized',
    'license': 'AGPL-3',
    'summary': 'Módulo GP',
    'depends': ['base',
                'account',
                'contacts',
                'l10n_ve_dpt',
                'base_vat',
                ],
    'data': [
            'security/ir.model.access.csv',
            'data/gp_data.xml',
            'views/gp_views.xml',
            'views/account_move_views.xml',
            'views/partner_views.xml',
    ],
    'external_dependencies': {
        'python': ['pymssql'],
    },
    'demo': [],
    'css': [],
    'qweb': [],
    'installable': True,
    'auto_install': False,
    'application': False
}
