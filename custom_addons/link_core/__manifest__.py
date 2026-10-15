{
    'name': 'LINK Core - Conversational Commerce Engine',
    'version': '20.0.1.0.0',
    'category': 'Sales/Services',
    'summary': 'Headless Multi-Tenant Engine for Conversational AI & WhatsApp Commerce',
    'description': """
LINK Core Engine
================
Backend headless operating engine for LINK Conversational Commerce Platform:
- Multi-Tenant isolation (saas.tenant)
- Dynamic Service Catalog & Attributes
- Pricing & Availability Rules
- Requirements & Document Collection Workflow
- Customer Request Lifecycle (Draft -> Info -> Docs -> Pending Review -> Confirmed)
- Atomic JSON RPC endpoints for AI Middleware & WhatsApp Integration
    """,
    'author': 'LINK Platform Team',
    'website': 'https://link.local',
    'license': 'LGPL-3',
    'depends': [
        'mail',
    ],
    'data': [
        'security/link_security.xml',
        'security/ir.access.csv',
        'data/sequence_data.xml',
        'views/link_tenant_views.xml',
        'views/link_service_catalog_views.xml',
        'views/link_service_request_views.xml',
        'views/link_menus.xml',
    ],
    'application': True,
    'installable': True,
}
