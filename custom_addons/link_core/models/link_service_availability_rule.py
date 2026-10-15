from odoo import fields, models


class LinkServiceAvailabilityRule(models.Model):
    _name = 'link.service.availability.rule'
    _description = 'Service Availability Rule'

    catalog_id = fields.Many2one(
        'link.service.catalog',
        string='Service',
        required=True,
        ondelete='cascade',
        index=True,
    )
    name = fields.Char(string='Rule Description', required=True)
    rule_type = fields.Selection(
        selection=[
            ('blackout_dates', 'Blackout Dates (Holidays / Maintenance / Sold Out)'),
            ('capacity_limit', 'Capacity Limit per Date'),
            ('weekday_restriction', 'Weekday Restrictions'),
        ],
        string='Rule Type',
        default='blackout_dates',
        required=True,
    )
    date_from = fields.Date(string='Date From')
    date_to = fields.Date(string='Date To')
    max_capacity = fields.Integer(string='Max Available Capacity', default=0)
    note = fields.Char(string='Availability Note / Reason')
    active = fields.Boolean(default=True)
