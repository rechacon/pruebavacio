from logging import getLogger

from datetime import datetime
import pymssql
import re
from odoo import models, fields

_logger = getLogger(__name__)


class GP(models.Model):
    _name = 'gp'
    _description = 'Conexion Odoo GP'

    name = fields.Char(string='Descripción')
    type_gp = fields.Selection(
        [('partner', 'Clientes'),
         ('invoice', 'Facturas'),
         ('proforma', 'Proformas'),
         ('credit_note', 'Notas de crédito'),
         ('contract_account', 'Cuentas contrato'),
         ('debt', 'Deudas'),
         ], string='Tipo de importación'
    )
    gp_log_ids = fields.One2many('gp.log', 'gp_id', 'Logs')

    def sql_partner(self):
        """Consulta de listado de clientes"""
        return """SELECT
            RTRIM(CM.CUSTNMBR) rif,
            RTRIM(CM.CUSTNAME) razon_social,
            RTRIM(CM.SHRTNAME) razon_social_corta,
            CASE
              WHEN CM.UPSZONE = 'CO' THEN 0
              ELSE 1
            END tipo_cliente,
            UPPER(CONCAT(RTRIM(CM.ADDRESS1),' ',RTRIM(CM.ADDRESS2),' ',RTRIM(CM.ADDRESS3))) direccion,
            UPPER(CONCAT(RTRIM(CM.COUNTRY),' - ',RTRIM(CM.CITY))) pais_ciudad,
            RTRIM(CM.STATE) estado_pais,
            RTRIM(CM.PHONE1) telefono1,
            RTRIM(CM.PHONE2) telefono2,
            RTRIM(CM.PHONE3) telefono3,
            CASE
              WHEN CM.INACTIVE = 0 THEN 'ACTIVO'
              ELSE 'INACTIVO'
            END estatus_activacion,
            CASE
              WHEN CM.HOLD = 0 THEN 'SIN SUSPENDER'
              ELSE 'SUSPENDIDO'
            END estatus_suspension
        FROM [dbo].[RM00101] CM
        -- WHERE CM.CUSTNMBR = 'J000202001' AND INACTIVE = 0 AND HOLD = 0
        -- WHERE CM.CUSTNMBR = 'J000202001'
        ORDER BY CM.CUSTNMBR"""

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

    def sql_proforma(self):
        """Consulta de listado de proformas"""
        return """SELECT
              RTRIM(SOP1.CUSTNMBR) rif,
              RTRIM(SOP1.SOPNUMBE) numero_documento,
              RTRIM(SOP1.PRSTADCD) cuenta_contrato,
              SOP1.DOCAMNT monto_documento,
              CONVERT(VARCHAR, SOP1.DOCDATE, 105) emision_documento,
              CONVERT(VARCHAR, SOP1.DOCDATE, 23) fecha_emision2,
              '7 DIAS A PARTIR DE SU EMISION' vencimiento_documento,
              RTRIM(SOP16.COMMENT_1) periodo,
                CASE WHEN GETDATE() > DATEADD(DAY,7,SOP1.DOCDATE) THEN 0 ELSE 1 END vigencia_documento,
              SOP1.SUBTOTAL monto_concepto,
              CONVERT(int, ROUND((SELECT TOP 1 TXDTLPCT FROM TX00201 WHERE TAXDTLID = 'V IVA NAC 16%'), 0)) porcentaje_aplicado
            FROM [dbo].[SOP10100] SOP1
            INNER JOIN [dbo].[SOP10106] SOP16 ON SOP16.SOPNUMBE = SOP1.SOPNUMBE
            INNER JOIN [dbo].[RM00101] CM ON CM.CUSTNMBR = SOP1.CUSTNMBR
            --WHERE SOP1.CUSTNMBR = 'J000202001' AND SOP1.VOIDSTTS = 0 AND SOP1.SOPTYPE = 2 AND SOP16.SOPTYPE = 2 AND CM.INACTIVE = 0 AND CM.HOLD = 0 AND SOP1.SOPNUMBE NOT IN(SELECT SOPNUMBE FROM [dbo].[SOP10104] SOP14 WHERE SOP14.SOPTYPE = 2 AND SOPNUMBE = SOP1.SOPNUMBE AND SOP14.DELETE1 = 0)
            --WHERE SOP1.CUSTNMBR = 'J000202001'
            ORDER BY SOP1.DOCDATE DESC
            --OFFSET 0 ROWS FETCH NEXT 50 ROWS ONLY
            ;"""

    def sql_credit_note(self):
        """Consulta de listado de notas de crédito"""
        return """SELECT
            RTRIM(SOP3.CUSTNMBR) rif,
            RTRIM(SOP3.SOPNUMBE) numero_nota,
            RTRIM(SOP1.USERDEF1) numero_factura,
            CASE WHEN (RTRIM(SOP1.USERDEF1) IS NULL OR RTRIM(SOP1.USERDEF1) = '') THEN 0 ELSE 1 END tiene_factura,
            RTRIM(SOP3.PRSTADCD) cuenta_contrato,
            SOP3.DOCAMNT monto_nota,
            CONVERT(VARCHAR, SOP3.DOCDATE, 105) emision_nota,
            CONVERT(VARCHAR, SOP3.DUEDATE, 105) vencimiento_nota,
            CASE WHEN RTRIM(SOP3.COMMNTID) = RTRIM(SOP1.COMMENT_1) THEN 'USADA PARA ANULAR FACTURA' ELSE 'OTRO' END uso,
            RTRIM(SOP3.COMMNTID) id_comentario,
            RTRIM(SOP1.COMMENT_1) periodo_factura
          FROM [dbo].[SOP30200] SOP3
          INNER JOIN [dbo].[SOP10106] SOP1 ON SOP1.SOPNUMBE = SOP3.SOPNUMBE
          INNER JOIN [dbo].[RM00101] CM ON CM.CUSTNMBR = SOP3.CUSTNMBR
          --WHERE SOP3.CUSTNMBR = 'J000202001' AND SOP3.SOPTYPE = 4 AND SOP1.SOPTYPE = 4
          --AND (RTRIM(SOP3.COMMNTID) != RTRIM(SOP1.COMMENT_1)) AND CM.INACTIVE = 0 AND CM.HOLD = 0
          ORDER BY SOP3.DOCDATE DESC
          --OFFSET 0 ROWS FETCH NEXT 10 ROWS ONLY
          ;"""

    def sql_contract_account(self, vat):
        """Consulta de listado de cuentas contratos"""
        return f"""SELECT cuenta, codigo_cnae,
            deuda_factura, deuda_proforma, (deuda_factura + deuda_proforma) total_deuda
            FROM (
                SELECT
                RTRIM(RM102.ADRSCODE) cuenta,
                RTRIM(USERDEF2) codigo_cnae,
                ISNULL((SELECT SUM(RM.CURTRXAM)
                FROM [dbo].[RM20101] RM
                INNER JOIN [dbo].[SOP10106] SOP1 ON SOP1.SOPNUMBE = RM.DOCNUMBR AND SOP1.SOPTYPE = 3
                INNER JOIN [dbo].[SOP30200] SOP3 ON SOP3.SOPNUMBE = SOP1.SOPNUMBE AND SOP3.SOPTYPE = 3
                WHERE RM.CUSTNMBR = '{vat}' AND SOP3.PRSTADCD = RM102.ADRSCODE AND RM.RMDTYPAL = 1 AND RM.VOIDSTTS = 0 AND RM.DOCNUMBR LIKE '10%' AND GETDATE() > RM.DUEDATE AND RM.DOCDATE BETWEEN '2019-01-01' AND GETDATE()
                GROUP BY SOP3.PRSTADCD, RM.CUSTNMBR), 0) deuda_factura,
                ISNULL((SELECT SUM(SOP1.SUBTOTAL)
                FROM [dbo].[SOP10100] SOP1
                WHERE SOP1.CUSTNMBR = '{vat}' AND SOP1.PRSTADCD = RM102.ADRSCODE AND SOP1.VOIDSTTS = 0 AND SOP1.SOPTYPE = 2 AND GETDATE() > DATEADD(DAY,7,SOP1.DOCDATE) AND SOP1.DOCDATE BETWEEN '2019-01-01' AND GETDATE() AND SOP1.SOPNUMBE NOT IN(SELECT SOPNUMBE FROM [dbo].[SOP10104] SOP14 WHERE SOP14.SOPTYPE = 2 AND SOPNUMBE = SOP1.SOPNUMBE AND SOP14.DELETE1 = 0)), 0) deuda_proforma
                FROM [dbo].[RM00102] RM102
                WHERE CUSTNMBR = '{vat}' AND USERDEF1 != 'SERVICIO' AND (USERDEF2 NOT LIKE '%USAR%' OR LEN(USERDEF2) = 4 OR ISNULL(USERDEF2, '') = '') AND CREATDDT BETWEEN '1900-01-01' AND GETDATE() AND RM102.ADRSCODE NOT IN('FISCAL') AND CUSTNMBR IN(SELECT CUSTNMBR FROM [dbo].[RM00101] WHERE CUSTNMBR = '{vat}' AND INACTIVE = 0 AND HOLD = 0)
            ) datos
          ORDER BY cuenta
          --OFFSET 0 ROWS FETCH NEXT 50 ROWS ONLY;"""

    def sql_debt(self, vat):
        """Consulta de listado de deudas"""
        return f"""SELECT
                ISNULL(SUM(ROUND(deuda_factura,2)),0) deuda_factura,
                ISNULL(SUM(ROUND(deuda_proforma,2)),0) deuda_proforma,
                ISNULL(SUM(ROUND(deuda_factura,2)),0) + ISNULL(SUM(ROUND(deuda_proforma,2)),0) deuda_total
              FROM(
                SELECT
                  RM.CURTRXAM deuda_factura,
                  0 deuda_proforma
                FROM [dbo].[RM20101] RM
                INNER JOIN [dbo].[RM00101] CM ON CM.CUSTNMBR = RM.CUSTNMBR AND CM.INACTIVE = 0 AND CM.HOLD = 0
                WHERE CM.CUSTNMBR = '{vat}'-- AND RM.CURTRXAM <> 0 AND RM.RMDTYPAL = 1 AND RM.VOIDSTTS = 0 AND RM.DOCNUMBR LIKE '10%' AND GETDATE() > RM.DUEDATE

                UNION ALL

                SELECT
                  0 deuda_factura,
                  SOP1.SUBTOTAL deuda_proforma
                FROM [dbo].[SOP10100] SOP1
                INNER JOIN [dbo].[RM00101] CM ON CM.CUSTNMBR = SOP1.CUSTNMBR AND CM.INACTIVE = 0 AND CM.HOLD = 0
                WHERE CM.CUSTNMBR = '{vat}'-- AND SOP1.VOIDSTTS = 0 AND SOP1.SOPTYPE = 2 AND GETDATE() > DATEADD(DAY,7,SOP1.DOCDATE) AND SOP1.SOPNUMBE NOT IN(SELECT SOPNUMBE FROM [dbo].[SOP10104] SOP14 WHERE SOP14.SOPTYPE = 2 AND SOPNUMBE = SOP1.SOPNUMBE AND SOP14.DELETE1 = 0)
              ) datos"""

    def credentials_sqlserver(self, bd):
        """Credenciales de SQL SERVER"""
        _logger.info(f'\n\n======\nBD: {bd}\n======\n\n')
        # server = '10.161.0.32'
        server = '190.93.46.77'
        name_bd = bd
        user = 'consultorsql'
        passwd = 'Sql01*'
        port = '1433'
        return pymssql.connect(server=server, user=user, password=passwd, database=name_bd, port=port)

    def connect_gp(self):
        """Conexión con GP"""
        try:
            bd_ids = {
                # 'baruta': 'F2099',
                # 'chacao': 'F5618',
                # 'hatillo': 'F0004',
                # 'iribarren': 'F0006',
                'maneiro': 'F1099',
                # 'jimenez': 'F0009',
                # 'san_diego': 'S6759',
            }
            total = 0
            for bd in bd_ids:
                conn = self.credentials_sqlserver(bd_ids[bd])
                if bd == 'baruta':
                    municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_MIR_BAR', raise_if_not_found=False)
                elif bd == 'chacao':
                    municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_MIR_CHA', raise_if_not_found=False)
                elif bd == 'hatillo':
                    municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_MIR_EHA', raise_if_not_found=False)
                elif bd == 'iribarren':
                    municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_LAR_IRI', raise_if_not_found=False)
                elif bd == 'maneiro':
                    municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_NVA_MAN', raise_if_not_found=False)
                elif bd == 'jimenez':
                    municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_LAR_JIM', raise_if_not_found=False)
                elif bd == 'san_diego':
                    municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_CAR_SAD', raise_if_not_found=False)
                _logger.info('\n\n¡Conexión exitosa!\n\n')
                cursor = conn.cursor()
                # BD
                # Elegir la consulta
                record_ids = []
                if self.type_gp == 'partner':
                    cursor.execute(self.sql_partner())
                elif self.type_gp == 'invoice':
                    cursor.execute(self.sql_invoice())
                elif self.type_gp == 'proforma':
                    cursor.execute(self.sql_proforma())
                elif self.type_gp == 'credit_note':
                    cursor.execute(self.sql_credit_note())
                elif self.type_gp == 'contract_account':
                    partner_ids = self.env['res.partner'].search(['&', ('municipality_id', '=', municipality_id.id), ('parent_id', '!=', False)], limit=100)
                    for partner in partner_ids:
                        cursor.execute(self.sql_contract_account(partner.vat))
                        pre_tuple = cursor.fetchall()
                        if not pre_tuple == []:
                            pre_tuple = [pre_tuple[0] + tuple(partner)]
                            record_ids.extend(pre_tuple)
                elif self.type_gp == 'debt':
                    partner_ids = self.env['res.partner'].search([('parent_id', '!=', False)], limit=100)
                    for partner in partner_ids:
                        cursor.execute(self.sql_debt(partner.vat))
                        pre_tuple = [cursor.fetchall()[0] + tuple(partner)]
                        record_ids.extend(pre_tuple)

                # Devolver consulta
                progress = 0
                for row in cursor.fetchall() or record_ids:
                    if self.type_gp == 'partner':
                        _logger.info('\nListado de Clientes\n')
                        self.create_partner(row, bd)
                    elif self.type_gp == 'invoice':
                        _logger.info('\nListado de Facturas\n')
                        self.create_invoice(row, bd)
                    elif self.type_gp == 'proforma':
                        _logger.info('\nListado de Proformas\n')
                        self.create_proforma(row, bd)
                    elif self.type_gp == 'credit_note':
                        _logger.info('\nListado de Notas de crédito\n')
                        self.create_credit_note(row, bd)
                    elif self.type_gp == 'contract_account':
                        _logger.info('\nListado de Cuentas contrato\n')
                        self.create_contract_account(row, bd)
                    elif self.type_gp == 'debt':
                        _logger.info('\nListado de Deudas\n')
                        self.create_debt(row, bd)
                    # Guardar progreso
                    if progress == 100:
                        self.env.cr.commit()
                        progress = 0
                    total += 1
                    progress += 1

            # Crear log
            self.gp_log_ids = [(0, 0, {
                'name': f'Importación de {self.type_gp}',
                'qty': total,
            })]
        except Exception as e:
            _logger.info(f'\n¡Error de conexión! {e}\n')

    def create_partner(self, data, bd):
        """Creación de listado de clientes"""
        if bd == 'baruta':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_MIR_BAR', raise_if_not_found=False)
        elif bd == 'chacao':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_MIR_CHA', raise_if_not_found=False)
        elif bd == 'hatillo':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_MIR_EHA', raise_if_not_found=False)
        elif bd == 'iribarren':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_LAR_IRI', raise_if_not_found=False)
        elif bd == 'maneiro':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_NVA_MAN', raise_if_not_found=False)
        elif bd == 'jimenez':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_LAR_JIM', raise_if_not_found=False)
        elif bd == 'san_diego':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_CAR_SAD', raise_if_not_found=False)
        _logger.info(f'\n{data}\n')
        name = re.sub(r"[^\sa-zA-Z0-9.-]", "", data[2].strip().upper())
        company_name = re.sub(r"[^\sa-zA-Z0-9.-]", "", data[1].strip().upper())
        # municipality_id = data[6]
        phone = data[7].strip()
        mobile = data[8].strip()
        active = True if data[10].strip() == 'ACTIVO' else False
        state = 'without_suspending' if data[11].strip() == 'SIN SUSPENDER' else 'suspending'
        vat = data[0].strip()
        street = data[4].strip()
        partner_id = self.env['res.partner']
        values = {
            'name': name,
            'company_name': company_name if vat[0] not in ['V', 'v', 'E', 'e'] else '',
            'vat': vat,
            'is_company': False if vat[0] in ['V', 'v', 'E', 'e'] else True,
            'company_type': 'person' if vat[0] in ['V', 'v', 'E', 'e'] else 'company',
            'active': active,
        }
        partner = partner_id.search(['&', ('vat', '=', vat), ('parent_id', '=', False)])
        if not partner:
            partner = partner_id.create(values)
        if partner:
            values.update({
                'state': state,
                'municipality_id': municipality_id.id,
                'state_id': municipality_id.state_id.id,
                'country_id': municipality_id.state_id.country_id.id,
                'street': street,
                'phone': phone,
                'mobile': mobile,
                'type': 'other',
            })
            child_id = partner_id.search(['&', ('vat', '=', vat), ('municipality_id', '=', municipality_id.id)])
            if child_id:
                child_id.write(values)
            else:
                partner.write({
                    'child_ids': [(0, 0, values)],
                    'street': '',
                    'municipality_id': False,
                    'state_id': False,
                    'country_id': municipality_id.state_id.country_id.id,
                })

    def create_invoice(self, data, bd):
        """Creación de listado de facturas"""
        if bd == 'baruta':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_MIR_BAR', raise_if_not_found=False)
        elif bd == 'chacao':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_MIR_CHA', raise_if_not_found=False)
        elif bd == 'hatillo':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_MIR_EHA', raise_if_not_found=False)
        elif bd == 'iribarren':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_LAR_IRI', raise_if_not_found=False)
        elif bd == 'maneiro':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_NVA_MAN', raise_if_not_found=False)
        elif bd == 'jimenez':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_LAR_JIM', raise_if_not_found=False)
        elif bd == 'san_diego':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_CAR_SAD', raise_if_not_found=False)
        _logger.info(f'\n{data}\n')
        partner_id = self.env['res.partner'].search(['&', ('vat', '=', data[0]), ('municipality_id', '=', municipality_id.id)])
        if partner_id:
            contract = data[2]
            numero_documento = data[1]
            amount = data[3]
            invoice_date = datetime.strptime(data[5], "%d-%m-%Y")
            invoice_date_due = datetime.strptime(data[6], "%d-%m-%Y")
            period = data[7]
            pending = data[4]
            journal_id = self.env['account.journal'].search([('type', '=', 'bank')], limit=1)
            move_id = self.env['account.move'].create({
                'name': numero_documento,
                'partner_id': partner_id.id,
                'move_type': 'out_invoice',
                'invoice_date': invoice_date,
                'numero_documento': numero_documento,
                'invoice_date_due': invoice_date_due,
                'contract': contract,
                'period': period,
                # 'payment_id': payment_id.id,
                'invoice_line_ids': [(0, 0, {
                    'product_id': self.env.ref('backov.product_test').id,
                    'price_unit': amount,
                    # 'tax_ids': [(4, self.env.ref('l10n_es.account_tax_template_s_iva21s').id)],
                    'tax_ids': False,
                })]
            })
            move_id.action_post()
            # payment_id.action_post()
            move_id.name = numero_documento
            # move_id.payment_id = payment_id.id
            print(f'\n\nP: {pending}\n\n')
            payment_id = self.env['account.payment.register'].with_context(active_ids=[move_id.id], active_model='account.move').create({
                'journal_id': journal_id.id,
                'amount': amount if pending == 0.0 else pending,
                'payment_difference_handling': 'reconcile' if pending == 0.0 else 'open',
                'payment_date': invoice_date,
                'communication': numero_documento,
                # 'dont_redirect_to_payments': True,
            }).action_create_payments()
            if pending == 0.0:
                move_id.payment_state = 'paid'
            else:
                move_id.payment_state = 'partial'
            return move_id

    def create_proforma(self, data, bd):
        """Creación de listado de proformas"""
        if bd == 'baruta':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_MIR_BAR', raise_if_not_found=False)
        elif bd == 'chacao':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_MIR_CHA', raise_if_not_found=False)
        elif bd == 'hatillo':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_MIR_EHA', raise_if_not_found=False)
        elif bd == 'iribarren':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_LAR_IRI', raise_if_not_found=False)
        elif bd == 'maneiro':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_NVA_MAN', raise_if_not_found=False)
        elif bd == 'jimenez':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_LAR_JIM', raise_if_not_found=False)
        elif bd == 'san_diego':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_CAR_SAD', raise_if_not_found=False)
        _logger.info(f'\n{data}\n')
        partner_id = self.env['res.partner'].search(['&', ('vat', '=', data[0]), ('municipality_id', '=', municipality_id.id)])
        if partner_id:
            contract = data[2]
            numero_documento = data[1]
            amount = data[9]
            invoice_date = datetime.strptime(data[4], "%d-%m-%Y")
            # invoice_date_due = datetime.strptime(data[6], "%d-%m-%Y")
            period = data[7]
            iva = float(data[10])
            tax = self.env['account.tax']
            if not tax.search([('type_tax_use', '=', 'sale'), ('amount', '=', iva)]):
                tax = tax.create({
                    'name': f'Impuesto del {iva}% (Ventas)',
                    'type_tax_use': 'sale',
                    'amount_type': 'percent',
                    'active': True,
                    'amount': iva,
                    'description': f'Impuesto del {iva}%',
                })
            else:
                tax = tax.search([('type_tax_use', '=', 'sale'), ('amount', '=', iva)])
            move_id = self.env['account.move'].create({
                'name': numero_documento,
                'partner_id': partner_id.id,
                'move_type': 'out_invoice',
                'invoice_date': invoice_date,
                'numero_documento': numero_documento,
                'proforma': True,
                # 'invoice_date_due': invoice_date_due,
                'invoice_date_due': False,
                'contract': contract,
                'period': period,
                'invoice_line_ids': [(0, 0, {
                    'product_id': self.env.ref('backov.product_test').id,
                    'price_unit': amount,
                    'tax_ids': [(4, tax.id)],
                })]
            })
            move_id.name = numero_documento
            return move_id

    def create_credit_note(self, data, bd):
        """Creación de listado de notas de crédito"""
        if bd == 'baruta':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_MIR_BAR', raise_if_not_found=False)
        elif bd == 'chacao':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_MIR_CHA', raise_if_not_found=False)
        elif bd == 'hatillo':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_MIR_EHA', raise_if_not_found=False)
        elif bd == 'iribarren':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_LAR_IRI', raise_if_not_found=False)
        elif bd == 'maneiro':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_NVA_MAN', raise_if_not_found=False)
        elif bd == 'jimenez':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_LAR_JIM', raise_if_not_found=False)
        elif bd == 'san_diego':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_CAR_SAD', raise_if_not_found=False)
        _logger.info(f'\n{data}\n')
        partner_id = self.env['res.partner'].search(['&', ('vat', '=', data[0]), ('municipality_id', '=', municipality_id.id)])
        if partner_id:
            move_id = self.env['account.move'].search([('name', '=', data[2])])
            contract = data[4]
            numero_documento = data[1]
            amount = data[5]
            invoice_date = datetime.strptime(data[6], "%d-%m-%Y")
            invoice_date_due = datetime.strptime(data[7], "%d-%m-%Y")
            use = data[8]
            description = data[9]
            period = data[10]
            move_id = self.env['account.move'].create({
                'name': numero_documento,
                'partner_id': partner_id.id,
                'move_type': 'out_refund',
                'invoice_date': invoice_date,
                'numero_documento': numero_documento,
                'invoice_date_due': invoice_date_due,
                'use': use,
                'description': description,
                'contract': contract,
                'period': period,
                'invoice_line_ids': [(0, 0, {
                    'product_id': self.env.ref('backov.product_test').id,
                    'price_unit': amount,
                    'tax_ids': False,
                })]
            })
            move_id.name = numero_documento
            return move_id

    def create_contract_account(self, data, bd):
        """Creación de listado de cuentas contratos"""
        if bd == 'baruta':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_MIR_BAR', raise_if_not_found=False)
        elif bd == 'chacao':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_MIR_CHA', raise_if_not_found=False)
        elif bd == 'hatillo':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_MIR_EHA', raise_if_not_found=False)
        elif bd == 'iribarren':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_LAR_IRI', raise_if_not_found=False)
        elif bd == 'maneiro':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_NVA_MAN', raise_if_not_found=False)
        elif bd == 'jimenez':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_LAR_JIM', raise_if_not_found=False)
        elif bd == 'san_diego':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_CAR_SAD', raise_if_not_found=False)
        _logger.info(f'\n{data}\n')
        partner_id = self.env['res.partner'].search(['&', ('vat', '=', data[5].vat), ('municipality_id', '=', municipality_id.id)])
        contract_id = self.env['account.contract']
        name = data[0]
        cnae_id = self.env['res.partner.cnae'].search([('code', '=', data[1])], limit=1)
        debit_invoice = data[2]
        debit_proforma = data[3]
        debit_partner = data[4]
        if not contract_id.search([('name', '=', name)]):
            contract_id = contract_id.create({
                'name': name,
                'cnae_id': cnae_id.id,
                'partner_id': partner_id.id,
                'debit_invoice': debit_invoice,
                'debit_proforma': debit_proforma,
                'debit_partner': debit_partner,
            })
        else:
            contract_id = contract_id.search([('name', '=', name)])
            contract_id.write({
                # 'name': name,
                # 'cnae_id': cnae_id,
                'debit_invoice': debit_invoice,
                'debit_proforma': debit_proforma,
                'debit_partner': debit_partner,
            })
        return contract_id

    def create_debt(self, data, bd):
        """Creación de listado de deudas"""
        if bd == 'baruta':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_MIR_BAR', raise_if_not_found=False)
        elif bd == 'chacao':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_MIR_CHA', raise_if_not_found=False)
        elif bd == 'hatillo':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_MIR_EHA', raise_if_not_found=False)
        elif bd == 'iribarren':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_LAR_IRI', raise_if_not_found=False)
        elif bd == 'maneiro':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_NVA_MAN', raise_if_not_found=False)
        elif bd == 'jimenez':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_LAR_JIM', raise_if_not_found=False)
        elif bd == 'san_diego':
            municipality_id = self.env.ref('l10n_ve_dpt.mun_ve_CAR_SAD', raise_if_not_found=False)
        _logger.info(f'\n{data}\n')
        partner_id = self.env['res.partner'].search(['&', ('vat', '=', data[3].vat), ('municipality_id', '=', municipality_id.id)])
        debit_id = self.env['account.debit']
        debit_invoice = data[0]
        debit_proforma = data[1]
        debit_partner = data[2]
        if not debit_id.search([('partner_id', '=', partner_id.id)]):
            debit_id = debit_id.create({
                'partner_id': partner_id.id,
                'debit_invoice': debit_invoice,
                'debit_proforma': debit_proforma,
                'debit_partner': debit_partner,
            })
        else:
            debit_id = debit_id.search([('partner_id', '=', partner_id.id)])
            debit_id.write({
                # 'partner_id': partner_id,
                'debit_invoice': debit_invoice,
                'debit_proforma': debit_proforma,
                'debit_partner': debit_partner,
            })
        return debit_id


class GPLog(models.Model):
    _name = 'gp.log'
    _description = 'Logs de conexion Odoo GP'

    name = fields.Char('Descripción')
    qty = fields.Integer('Creados', help='Número total de registros importados')
    gp_id = fields.Many2one('gp', 'Conexión', ondelete='cascade')
