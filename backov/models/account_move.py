from logging import getLogger
from datetime import datetime

import pymssql

from odoo import models, fields

_logger = getLogger(__name__)


class Move(models.Model):
    _inherit = 'account.move'

    numero_documento = fields.Char(string='N° documento')
    period = fields.Char(string='Periodo')
    contract = fields.Char(string='Cuenta contrato')
    proforma = fields.Boolean(string='Proforma')
    use = fields.Char(string='Uso')
    description = fields.Char(string='Descripción')

    def force_unlink_move(self):
        """Forzar eliminación de las facturas"""
        move_ids = self.env['account.move'].browse(self._context.get('active_ids', []))
        move_ids.with_context(force_delete=True).unlink()

    def sql_invoice(self):
        """Consulta de listado de facturas"""
        return """SELECT
            RTRIM(RM.CUSTNMBR) rif,
            RTRIM(RM.DOCNUMBR) numero_documento,
        RTRIM(SOP32.PRSTADCD) cuenta_contrato,
            RM.ORTRXAMT monto_documento,
            RM.CURTRXAM monto_pendiente,
            CONVERT(VARCHAR, RM.DOCDATE, 105) emision_documento,
            CONVERT(VARCHAR, RM.DUEDATE, 105) vencimiento_documento,
            UPPER(RTRIM(SOP1.COMMENT_1)) periodo,
            CASE WHEN GETDATE() > RM.DUEDATE THEN 0 ELSE 1 END vigencia_documento
          FROM [dbo].[RM20101] RM
          INNER JOIN [dbo].[SOP10106] SOP1 ON SOP1.SOPNUMBE = RM.DOCNUMBR
      INNER JOIN [dbo].[SOP30200] SOP32 ON SOP32.SOPNUMBE = SOP1.SOPNUMBE
          INNER JOIN [dbo].[RM00101] CM ON CM.CUSTNMBR = RM.CUSTNMBR
          WHERE RM.CUSTNMBR = 'J000202001' AND RM.RMDTYPAL = 1 AND RM.VOIDSTTS = 0 AND RM.DOCNUMBR LIKE '10%' AND SOP1.SOPTYPE = 3 AND SOP32.SOPTYPE = 3 AND CM.INACTIVE = 0 AND CM.HOLD = 0
          ORDER BY RM.CURTRXAM DESC;"""

    def credentials_sqlserver(self):
        """Credenciales de SQL SERVER"""
        server = '10.161.0.32'
        name_bd = 'TEST'
        user = 'consultorsql'
        passwd = 'Sql01*'
        return pymssql.connect(server=server, user=user, password=passwd, database=name_bd)

    def connect_gp(self):
        """Conexión con GP"""
        try:
            conn = self.credentials_sqlserver()
            _logger.info('\n\n¡Conexión exitosa!\n\n')
            cursor = conn.cursor()
            cursor.execute(self.sql_invoice())
            for row in cursor.fetchall():
                self.create_gp(row)
        except Exception as e:
            _logger.info(f'\n¡Error de conexión! {e}\n')

    def create_gp(self, data):
        """Crear factura importada de GP"""
        _logger.info(data)
        partner_id = self.env['res.partner'].search([('vat', '=', data[0])])
        if partner_id:
            amount = data[3]
            numero_documento = data[1]
            invoice_date = datetime.strptime(data[5], "%d-%m-%Y")
            invoice_date_due = datetime.strptime(data[6], "%d-%m-%Y")
            _logger.info(f'\nMONTO: {amount}\n')
            move_id = self.env['account.move'].create({
                'partner_id': partner_id.id,
                'move_type': 'out_invoice',
                'invoice_date': invoice_date,
                'numero_documento': numero_documento,
                'invoice_date_due': invoice_date_due,
            })
            return move_id

    def print_invoice_ov(self):
        """Imprimir reporte de OV"""
        self.ensure_one()
        municipality_id = 'None'
        if self.partner_id.municipality_id == self.env.ref('l10n_ve_dpt.mun_ve_MIR_BAR', raise_if_not_found=False):
            municipality_id = 'baruta'
        elif self.partner_id.municipality_id == self.env.ref('l10n_ve_dpt.mun_ve_MIR_CHA', raise_if_not_found=False):
            municipality_id = 'chacao'
        elif self.partner_id.municipality_id == self.env.ref('l10n_ve_dpt.mun_ve_MIR_EHA', raise_if_not_found=False):
            municipality_id = 'hatillo'
        elif self.partner_id.municipality_id == self.env.ref('l10n_ve_dpt.mun_ve_LAR_IRI', raise_if_not_found=False):
            municipality_id = 'iribarren'
        elif self.partner_id.municipality_id == self.env.ref('l10n_ve_dpt.mun_ve_NVA_MAN', raise_if_not_found=False):
            municipality_id = 'maneiro'
        elif self.partner_id.municipality_id == self.env.ref('l10n_ve_dpt.mun_ve_LAR_JIM', raise_if_not_found=False):
            municipality_id = 'jimenez'
        elif self.partner_id.municipality_id == self.env.ref('l10n_ve_dpt.mun_ve_CAR_SAD', raise_if_not_found=False):
            municipality_id = 'san_diego'
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': f'https://oficinavirtual.fospuca.com/fospuca/facturacion/pdf/{municipality_id}-{self.name}',
        }


class Contract(models.Model):
    _name = 'account.contract'
    _description = 'Cuenta contrato'

    name = fields.Char('N° CC', help='Número de la cuenta contrato')
    cnae_id = fields.Many2one('res.partner.cnae', 'Código CNAE', help='Código de actividades económicas')
    debit_invoice = fields.Float('Deuda factura')
    debit_proforma = fields.Float('Deuda proforma')
    debit_partner = fields.Float('Deuda cliente')
    partner_id = fields.Many2one('res.partner', 'Cliente')


class Debit(models.Model):
    _name = 'account.debit'
    _description = 'Deudas'
    _rec_name = 'partner_id'

    partner_id = fields.Many2one('res.partner', 'Cliente')
    debit_invoice = fields.Float('Deuda factura')
    debit_proforma = fields.Float('Deuda proforma')
    debit_partner = fields.Float('Deuda cliente')
