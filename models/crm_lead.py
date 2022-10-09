import logging
import requests

from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class CrmLead(models.Model):
    _inherit = 'crm.lead'
    # 1624214808

    facebook_lead_id = fields.Char(readonly=True)
    facebook_page_id = fields.Many2one(
        'crm.facebook.page', related='facebook_form_id.page_id',
        store=True, readonly=True)
    facebook_form_id = fields.Many2one('crm.facebook.form', readonly=True)
    facebook_adset_id = fields.Many2one('utm.adset', readonly=True)
    facebook_ad_id = fields.Many2one(
        'utm.medium', related='medium_id', store=True, readonly=True,
        string='Facebook Ad')
    facebook_campaign_id = fields.Many2one(
        'utm.campaign', related='campaign_id', store=True, readonly=True,
        string='Facebook Campaign')
    facebook_date_create = fields.Datetime(readonly=True)
    facebook_is_organic = fields.Boolean(readonly=True)

    _sql_constraints = [
        ('facebook_lead_unique', 'unique(facebook_lead_id)',
         'This Facebook lead already exists!')
    ]

    def get_ad(self, lead):
        ad_obj = self.env['utm.medium']
        if not lead.get('ad_id'):
            return ad_obj
        if not ad_obj.search(
                [('facebook_ad_id', '=', lead['ad_id'])]):
            return ad_obj.create({
                'facebook_ad_id': lead['ad_id'], 'name': lead['ad_name'], }).id

        return ad_obj.search(
            [('facebook_ad_id', '=', lead['ad_id'])], limit=1)[0].id

    def get_adset(self, lead):
        ad_obj = self.env['utm.adset']
        if not lead.get('adset_id'):
            return ad_obj
        if not ad_obj.search(
                [('facebook_adset_id', '=', lead['adset_id'])]):
            return ad_obj.create({
                'facebook_adset_id': lead['adset_id'], 'name': lead['adset_name'], }).id

        return ad_obj.search(
            [('facebook_adset_id', '=', lead['adset_id'])], limit=1)[0].id

    def get_campaign(self, lead):
        campaign_obj = self.env['utm.campaign']
        if not lead.get('campaign_id'):
            return campaign_obj
        if not campaign_obj.search(
                [('facebook_campaign_id', '=', lead['campaign_id'])]):
            return campaign_obj.create({
                'facebook_campaign_id': lead['campaign_id'],
                'name': lead['campaign_name'], }).id

        return campaign_obj.search(
            [('facebook_campaign_id', '=', lead['campaign_id'])],
            limit=1)[0].id

    def prepare_lead_creation(self, lead, form):
        vals, notes = self.get_fields_from_data(lead, form)
        vals.update({
            'facebook_lead_id': lead['id'],
            'facebook_is_organic': lead['is_organic'],
            'name': self.get_opportunity_name(vals, lead, form),
            'description': "\n".join(notes),
            'team_id': form.team_id and form.team_id.id,
            'campaign_id': form.campaign_id and form.campaign_id.id or
                           self.get_campaign(lead),
            'source_id': form.source_id and form.source_id.id,
            'medium_id': form.medium_id and form.medium_id.id or
                         self.get_ad(lead),
            'user_id': form.team_id and form.team_id.user_id and form.team_id.user_id.id or False,
            'facebook_adset_id': self.get_adset(lead),
            'facebook_form_id': form.id,
            'facebook_date_create': lead['created_time'].split('+')[0].replace('T', ' ')
        })
        return vals

    def lead_creation(self, lead, form):
        #_logger.info("1616107405")

        vals = self.prepare_lead_creation(lead, form)
        team_id = vals.get('team_id')
        facebook_form_id = vals.get('facebook_form_id')
        last_salesperson = self.get_last_salesperson(facebook_form_id)
        salesperson_int = self.secuencial_salesperson(vals, last_salesperson)
        if salesperson_int:
            vals['user_id'] = salesperson_int
        else:
            vals['user_id'] = False
        
        source_int = vals['source_id']
        if not source_int:
            source_id = self.env['utm.source'].search([('name', '=', "Facebook")])
            if source_id:
                vals['source_id'] = source_id.id
        
        record_created = self.create(vals)
        
        _logger.info("RECORD CREATED FROM FACEBOOK LEAD: %s", record_created)

        mail_template_id  = form.mail_template_id
        if record_created and mail_template_id:
            email_sent = self.env['mail.template'].browse(mail_template_id.id).send_mail(record_created.id, force_send=False)
            _logger.info("Sent to Facebook User the Mail ID: %s", email_sent)
            
        return record_created

    def get_opportunity_name(self, vals, lead, form):
        if not vals.get('name'):
            vals['name'] = '%s - %s' % (form.name, lead['id'])
        return vals['name']

    def get_fields_from_data(self, lead, form): # 1665356984
        vals, notes = {}, []
        form_mapping = form.mappings.filtered(lambda m: m.odoo_field).mapped('facebook_field')
        
        form_mapping.extend(['contact_name', 'email_from', 'email_cc', 'function', 'phone', 'mobile'])
        
        unmapped_fields = []
        for name, value in lead.items():
            if name not in form_mapping:
                unmapped_fields.append((name, value))
                continue
            odoo_field = form.mappings.filtered(lambda m: m.facebook_field == name).odoo_field
            
            if len(odoo_field) == 0:
                odoo_field = self.env['ir.model.fields'].search([
                    ('name','=', name),
                    ('model_id.model', '=', self._name)
                ])

            notes.append('%s: %s' % (odoo_field.field_description, value))
            if odoo_field.ttype == 'many2one':
                related_value = self.env[odoo_field.relation].search([('display_name', '=', value)])
                vals.update({odoo_field.name: related_value and related_value.id})
            elif odoo_field.ttype in ('float', 'monetary'):
                vals.update({odoo_field.name: float(value)})
            elif odoo_field.ttype == 'integer':
                vals.update({odoo_field.name: int(value)})
            # TODO: separate date & datetime into two different conditionals
            elif odoo_field.ttype in ('date', 'datetime'):
                vals.update({odoo_field.name: value.split('+')[0].replace('T', ' ')})
            elif odoo_field.ttype == 'selection':
                vals.update({odoo_field.name: value})
            elif odoo_field.ttype == 'boolean':
                vals.update({odoo_field.name: value == 'true' if value else False})
            else:
                vals.update({odoo_field.name: value})

        # NOTE: Doing this to put unmapped fields at the end of the description
        for name, value in unmapped_fields:
            notes.append('%s: %s' % (name, value))

        return vals, notes

    def process_lead_field_data(self, lead):
        field_data = lead.pop('field_data')
        lead_data = dict(lead)
        lead_data.update([(l['name'], l['values'][0])
                          for l in field_data
                          if l.get('name') and l.get('values')])
        return lead_data

    def lead_processing(self, r, form):
        if not r.get('data'):
            return
        for lead in r['data']:
            lead = self.process_lead_field_data(lead)
            if not self.search(
                    [('facebook_lead_id', '=', lead.get('id')), '|', ('active', '=', True), ('active', '=', False)]):
                self.lead_creation(lead, form)

        # /!\ NOTE: Once finished a page let us commit that
        try:
            self.env.cr.commit()
        except Exception:
            self.env.cr.rollback()

        if r.get('paging') and r['paging'].get('next'):
            _logger.info('Fetching a new page in Form: %s' % form.name)
            self.lead_processing(requests.get(r['paging']['next']).json(), form)
        return

    @api.model
    def get_facebook_leads(self):
        _logger.info('Fetch of leads has Started')
        fb_api = "https://graph.facebook.com/v7.0/"
        for form in self.env['crm.facebook.form'].search([]):
            # /!\ NOTE: We have to try lead creation if it fails we just log it into the Lead Form?
            _logger.info('Starting to fetch leads from Form: %s' % form.name)
            r = requests.get(fb_api + form.facebook_form_id + "/leads", params={'access_token': form.access_token,
                                                                                'fields': 'created_time,field_data,ad_id,ad_name,adset_id,adset_name,campaign_id,campaign_name,is_organic'}).json()
            if r.get('error'):
                raise UserError(r['error']['message'])
            self.lead_processing(r, form)
        _logger.info('Fetch of leads has ended')

    def secuencial_salesperson(self, vals, last_salesperson_id):
        #_logger.info("1616036220")
        
        if not last_salesperson_id:
            last_salesperson_int = 0
        else:
            last_salesperson_int = last_salesperson_id.id

        facebook_form_int = vals.get("facebook_form_id")
        facebook_form_id= self.env['crm.facebook.form'].search(
            [('id','=', facebook_form_int )])
        
        form_member_ids = facebook_form_id.member_ids
        
        if not form_member_ids:
            return False
        
        fb_salespersons = []
        for salesperson in form_member_ids:
            fb_salespersons.append( salesperson.id )
        
        fb_salespersons.sort(reverse=False)
        
        salesperson_int = False
        for record_int in fb_salespersons:
            if last_salesperson_int < record_int:
                salesperson_int = record_int
                break
        
        if not salesperson_int:
            salesperson_int = fb_salespersons[0]

        return salesperson_int
    
    def get_last_salesperson(self, facebook_form_id):
        #_logger.info("1616092913")

        last_lead_id = self.env['crm.lead'].search(
            [('facebook_form_id','=', facebook_form_id )], order='id desc', limit=1 )
        
        if not last_lead_id:
            return False
        
        salesperson = last_lead_id.user_id
        if salesperson:
            return salesperson
        else:
            _logger.info("=== NO SALESPERSON FOUND")
            return False

    def get_page_team_id(self,vals):
        #_logger.info("1616544746")
        fb_lead_team_id = int( vals['team_id'] )
        
        fb_form_id = int( vals['facebook_form_id'] )
        fb_form_id_obj = self.env['crm.facebook.form'].search(
                [ ('id','=', fb_form_id ) ],
        )
        
        if not fb_lead_team_id:    
            fb_page_team_id = fb_form_id_obj.page_id.team_id
            fb_lead_team_id = fb_page_team_id
        else:
            fb_lead_team_id = fb_form_id_obj.team_id
        return fb_lead_team_id
