from odoo import models, fields, api


_region_specific_vat_codes = {
    'xi',
}


class Partner(models.Model):
    _inherit = 'res.partner'

    state = fields.Selection([('without_suspending', 'Sin suspender'), ('suspending', 'Supendida')])
    count_proforma = fields.Integer(string='N° Proforma', compute='_compute_proforma')
    gp = fields.Boolean(string='GP', help='Contacto que viene de GP', default=False)

    @api.constrains('vat', 'country_id')
    def check_vat(self):
        """Reescribiendo para evitar errores de data"""
        if self.env.context.get('company_id'):
            company = self.env['res.company'].browse(self.env.context['company_id'])
        else:
            company = self.env.company
        eu_countries = self.env.ref('base.europe').country_ids
        for partner in self:
            if not partner.vat:
                continue

            if company.vat_check_vies and partner.commercial_partner_id.country_id in eu_countries:
                # force full VIES online check
                check_func = self.vies_vat_check
            else:
                # quick and partial off-line checksum validation
                check_func = self.simple_vat_check

            failed_check = False
            # check with country code as prefix of the TIN
            vat_country_code, vat_number = self._split_vat(partner.vat)
            vat_has_legit_country_code = self.env['res.country'].search([('code', '=', vat_country_code.upper())])
            if not vat_has_legit_country_code:
                vat_has_legit_country_code = vat_country_code.lower() in _region_specific_vat_codes
            if vat_has_legit_country_code:
                failed_check = not check_func(vat_country_code, vat_number)

            # if fails, check with country code from country
            partner_country_code = partner.commercial_partner_id.country_id.code
            if (not vat_has_legit_country_code or failed_check) and partner_country_code:
                failed_check = not check_func(partner_country_code.lower(), partner.vat)

            # We allow any number if it doesn't start with a country code and the partner has no country.
            # This is necessary to support an ORM limitation: setting vat and country_id together on a company
            # triggers two distinct write on res.partner, one for each field, both triggering this constraint.
            # If vat is set before country_id, the constraint must not break.

            # if failed_check:
            #     country_code = partner_country_code or vat_country_code
            #     msg = partner._construct_constraint_msg(country_code.lower() if country_code else None)
            #     raise ValidationError(msg)

    def _compute_proforma(self):
        """Número de proforma"""
        move_ids = self.env['account.move'].search(['&', ('partner_id', '=', self.id), ('proforma', '=', True)])
        for rec in self:
            rec.count_proforma = len(move_ids)

    def action_view_proformas(self):
        """Ver proformas"""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("backov.action_move_out_invoice_proforma_type")
        action['domain'] = [
            ('partner_id', 'child_of', self.id),
            ('proforma', '=', True),
            ('move_type', '=', 'out_invoice'),
        ]
        return action

    def action_view_account_contract(self):
        """Ver cuentas contrato"""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("backov.action_contract")
        action['domain'] = [
            ('partner_id', 'child_of', self.id),
        ]
        return action


class Stadistics(models.Model):
    _name = 'res.partner.stadistics'
    _description = 'Estadísticas de los contactos'

    name = fields.Char('Descripción')
    count_contact_total = fields.Integer('Contactos en total', compute='_compute_count_total')
    count_sucursal_total = fields.Integer('Sucursales en total', compute='_compute_count_total')
    count_contact_nice = fields.Integer('Contactos correctos', compute='_compute_count_nice')
    count_sucursal_nice = fields.Integer('Sucursales correctas', compute='_compute_count_nice')
    count_contact_bad = fields.Integer('Contactos incorrectos', compute='_compute_count_bad')
    count_sucursal_bad = fields.Integer('Sucursales incorrectas', compute='_compute_count_bad')
    count_contact_inactive = fields.Integer('Contactos inactivos', compute='_compute_count_inactive')
    count_sucursal_inactive = fields.Integer('Sucursales inactivas', compute='_compute_count_inactive')
    count_contact_vat = fields.Integer('Contactos con el RIF/CI correcto', compute='_compute_count_vat')
    count_sucursal_vat = fields.Integer('Sucursales con el RIF/CI correcto', compute='_compute_count_vat')
    count_contact_name = fields.Integer('Contactos con el nombre vacío', compute='_compute_count_name')
    count_sucursal_name = fields.Integer('Sucursales con el nombre vacío', compute='_compute_count_name')
    count_contact_none = fields.Integer('Contactos sin RIF/CI', compute='_compute_count_none')
    count_sucursal_none = fields.Integer('Sucursales sin RIF/CI', compute='_compute_count_none')
    count_contact_percentage = fields.Float('Contactos buenos %', compute='_compute_count_percentage')
    count_sucursal_percentage = fields.Float('Sucursales buenas %', compute='_compute_count_percentage')

    def _compute_count_total(self):
        """Contactos y sucursales totales"""
        partner_id = self.env['res.partner']
        contacts_ids = partner_id.search([('parent_id', '=', False)])
        sucursals_ids = partner_id.search([('parent_id', '!=', False)])
        self.count_contact_total = len(contacts_ids)
        self.count_sucursal_total = len(sucursals_ids)

    def _compute_count_inactive(self):
        """Contactos y sucursales inactivas"""
        partner_id = self.env['res.partner']
        contacts_ids = partner_id.search(['&', ('parent_id', '=', False), ('active', '=', False)])
        sucursals_ids = partner_id.search(['&', ('parent_id', '!=', False), ('active', '=', False)])
        self.count_contact_inactive = len(contacts_ids)
        self.count_sucursal_inactive = len(sucursals_ids)

    def _compute_count_percentage(self):
        """Contactos y sucursales buenas %"""
        self.count_contact_percentage = (self.count_contact_nice * 100) / self.count_contact_total
        self.count_sucursal_percentage = (self.count_sucursal_nice * 100) / self.count_sucursal_total

    def _compute_count_nice(self):
        """Contactos y sucursales correctos"""
        partner_id = self.env['res.partner']
        contacts_ids = partner_id.search([('parent_id', '=', False)])
        sucursals_ids = partner_id.search([('parent_id', '!=', False)])
        figure_fiscal = ['V', 'E', 'P', 'J', 'G', 'C']
        self.count_contact_nice = 0
        self.count_sucursal_nice = 0
        for contact in contacts_ids:
            if not contact.name or not contact.vat:
                continue
            if (len(contact.name) > 3 and contact.vat[0].upper() in figure_fiscal
                and len(contact.vat) >= 6 and len(contact.vat) <= 10 and contact.vat[1:].isdigit()):
                self.count_contact_nice += 1
        for sucursal in sucursals_ids:
            if not sucursal.name or not sucursal.vat:
                continue
            if (len(sucursal.name) > 3 and sucursal.vat[0].upper() in figure_fiscal
                and len(sucursal.vat) >= 6 and len(sucursal.vat) <= 10 and sucursal.vat[1:].isdigit()):
                self.count_sucursal_nice += 1

    def _compute_count_bad(self):
        """Contactos y sucursales incorrectos"""
        partner_id = self.env['res.partner']
        contacts_ids = partner_id.search([('parent_id', '=', False)])
        sucursals_ids = partner_id.search([('parent_id', '!=', False)])
        figure_fiscal = ['V', 'E', 'P', 'J', 'G', 'C']
        self.count_contact_bad = 0
        self.count_sucursal_bad = 0
        for contact in contacts_ids:
            if not contact.name or not contact.vat:
                self.count_contact_bad += 1
            elif not (len(contact.name) > 3 and contact.vat[0].upper() in figure_fiscal
                and len(contact.vat) >= 6 and len(contact.vat) <= 10 and contact.vat[1:].isdigit()):
                self.count_contact_bad += 1
        for sucursal in sucursals_ids:
            if not sucursal.name or not sucursal.vat:
                self.count_sucursal_bad += 1
            elif not (len(sucursal.name) > 3 and sucursal.vat[0].upper() in figure_fiscal
                and len(sucursal.vat) >= 6 and len(sucursal.vat) <= 10 and sucursal.vat[1:].isdigit()):
                self.count_sucursal_bad += 1

    def _compute_count_vat(self):
        """Contactos y sucursales solamente con el rif correcto"""
        partner_id = self.env['res.partner']
        contacts_ids = partner_id.search([('parent_id', '=', False)])
        sucursals_ids = partner_id.search([('parent_id', '!=', False)])
        figure_fiscal = ['V', 'E', 'P', 'J', 'G', 'C']
        self.count_contact_vat = 0
        self.count_sucursal_vat = 0
        for contact in contacts_ids:
            if not contact.name or not contact.vat:
                continue
            if (contact.vat[0].upper() in figure_fiscal
                and len(contact.vat) >= 6 and len(contact.vat) <= 10 and contact.vat[1:].isdigit()):
                self.count_contact_vat += 1
        for sucursal in sucursals_ids:
            if not sucursal.name or not sucursal.vat:
                continue
            if (sucursal.vat[0].upper() in figure_fiscal
                and len(sucursal.vat) >= 6 and len(sucursal.vat) <= 10 and sucursal.vat[1:].isdigit()):
                self.count_sucursal_vat += 1

    def _compute_count_name(self):
        """Contactos y sucursales con el nombre vacío"""
        partner_id = self.env['res.partner']
        contacts_ids = partner_id.search(['&', ('parent_id', '=', False), ('name', '=', '')])
        sucursals_ids = partner_id.search(['&', ('parent_id', '!=', False), ('name', '=', '')])
        self.count_contact_name = len(contacts_ids)
        self.count_sucursal_name = len(sucursals_ids)

    def _compute_count_none(self):
        """Contactos y sucursales sin nombre y sin rif/ci"""
        partner_id = self.env['res.partner']
        contacts_ids = partner_id.search([('parent_id', '=', False)])
        sucursals_ids = partner_id.search([('parent_id', '!=', False)])
        self.count_contact_none = 0
        self.count_sucursal_none = 0
        for contact in contacts_ids:
            if not contact.vat:
                self.count_contact_none += 1
        for sucursal in sucursals_ids:
            if not sucursal.vat:
                self.count_sucursal_none += 1


class CNAE(models.Model):
    _name = 'res.partner.cnae'
    _description = 'Actividades económicas'

    name = fields.Char('Descripción')
    code = fields.Char('Código CNAE', help='Código de actividades económicas')

    def name_get(self):
        """Concatenar lo mostrado al usuario"""
        result = []
        for record in self:
            name = f'{record.code} - {record.name}'
            result.append((record.id, name))
        return result
