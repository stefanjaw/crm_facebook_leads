import requests
from odoo import fields, models, api
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    crm_fb_app_id = fields.Char('App ID', config_parameter='crm_facebook_leads.crm_fb_app_id')
    crm_fb_app_secret = fields.Char('App Secret', config_parameter='crm_facebook_leads.crm_fb_app_secret')
    crm_fb_access_token = fields.Char('Access Token', config_parameter='crm_facebook_leads.crm_fb_access_token')
    # crm_fb_access_token_state = fields.Selection([('valid', 'Valid'), ('invalid', 'Invalid'), ('unknown', 'Unknown')],
    #                                              compute='_get_access_token_state', string='Token State')
    # crm_fb_access_token_state_message = fields.Text(compute='_get_access_token_state', string='Error Message')
    
    def action_get_access_token(self):
        _logger.info( "====action_get_access_token===")
        _logger.info( "====self.crm_fb_app_id=== %s", self.crm_fb_app_id)
        redirect_url = "%s/crm_facebook_leads/auth" % (self.env['ir.config_parameter'].get_param('web.base.url'))
        auth_url = 'https://www.facebook.com/dialog/oauth?response_type=token&client_id={}&redirect_uri={}&scope={}'.format(
            self.crm_fb_app_id,
            redirect_url,
            'leads_retrieval,pages_manage_ads,pages_read_engagement,ads_management'
        )

        res = {
            'name': 'Facebook Authentication',
            'res_model': 'ir.actions.act_url',
            'type': 'ir.actions.act_url',
            'target': 'current',
            'url': auth_url
        }
        _logger.info( "===DEB=action_get_access_token=34==: %s", res )
        return res

    # TODO: open a wizard to selectively import pages instead of all
    def action_get_facebook_pages(self):
        _logger.info( "====action_get_facebook_pages===")
        _logger.info( "====action_get_facebook_pages=== %s", self.crm_fb_access_token)
        r = requests.get("https://graph.facebook.com/v17.0/me",
                         params={
                             'access_token': self.crm_fb_access_token,
                             'fields': 'id,access_token,name'
                         }).json()
        
        _logger.info(f"  DEF49 r: {r}\n")
        if r.get('error'):
            raise ValidationError(r['error']['message'])
        else:
            data = r
            r = {'data': [data]}
            pass
        _logger.info(f"  DEF56 r: {r}")

        if not r.get('data'):
            _logger.info(f"  DEF59 no r.get('data')\n")
            return
        for p in r['data']:
            _logger.info(f"  DEF62 p: {p}\n")
            if not self.env['crm.facebook.page'].search([('name', '=', p.get('id'))]):
                self.env['crm.facebook.page'].create({
                    'label': p.get('name'),
                    'name': p.get('id'),
                    'access_token': p.get('access_token')
                })

        action = self.env.ref('crm_facebook_leads.action_crm_facebook_page').read()[0]
        _logger.info( f"  DEF71 facebook response: {r}\n")
        _logger.info( f"  DEF72 Odoo action: {action}")
        return action

    @api.depends('crm_fb_access_token')
    def _get_access_token_state(self):
        _logger.info( "====get_access_token_state===")
        if not self.crm_fb_access_token:
            self.crm_fb_access_token_state = 'invalid'
            self.crm_fb_access_token_state_message = 'No Access Token provided'
        if not (self.crm_fb_app_id and self.crm_fb_app_secret):
            self.crm_fb_access_token_state = 'unknown'
            self.crm_fb_access_token_state_message = 'App ID and App Secret are required to debug access token'
            return
        r = requests.get("https://graph.facebook.com/v7.0/debug_token", params={'input_token': self.crm_fb_access_token,
                                                                                'access_token': '|'.join(
                                                                                    [self.crm_fb_app_id,
                                                                                     self.crm_fb_app_secret])}).json()
        STOP89_pendiente_cambiar_v7_0_ver_linea_antes
        if r.get('error') or r.get('data', []).get('error'):
            self.crm_fb_access_token_state = 'invalid'
            self.crm_fb_access_token_state_message = r.get('error') and r['error']['message'] or r['data']['error'][
                'message']
            return
        # Probably covered by previous condition
        if not r['data']['is_valid']:
            self.crm_fb_access_token_state = 'invalid'
            return
        if r['data']['type'] != 'USER':
            self.crm_fb_access_token_state = 'invalid'
            self.crm_fb_access_token_state_message = 'Token is of type %s. Must be of type USER' % (r['data']['type'])
            return
        if r['data']['expires_at'] != 0:
            self.crm_fb_access_token_state = 'invalid'
            self.crm_fb_access_token_state_message = 'You need a long-lived access token.'
            return
        scopes = r['data']['scopes']
        if any([scope not in scopes for scope in
                ('leads_retrieval', 'pages_manage_ads', 'pages_read_engagement', 'ads_management')]):
            self.crm_fb_access_token_state = 'invalid'
            self.crm_fb_access_token_state_message = 'Missing permissions: %s' % (', '.join(
                [scope for scope in ('leads_retrieval', 'pages_manage_ads', 'pages_read_engagement', 'ads_management')
                 if scope not in scopes]))
            return
        self.crm_fb_access_token_state = 'valid'
        self.crm_fb_access_token_state_message = ''

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    def cron_get_access_token(self):
        _logger.info( "====cron_get_access_token===")
        # client_id 165653190816042
        
        records = self.env['res.config.settings'].search([])
        for record in records:
            if record.crm_fb_access_token:
                crm_fb_access_token = record.crm_fb_access_token
                break
        
        redirect_url = "%s/crm_facebook_leads/auth" % (self.env['ir.config_parameter'].get_param('web.base.url'))
        auth_url = 'https://www.facebook.com/dialog/oauth?response_type=token&client_id={}&redirect_uri={}&scope={}'.format(
            165653190816042,
            redirect_url,
            'leads_retrieval,pages_manage_ads,pages_read_engagement,ads_management'
        )

        res = {
            'name': 'Facebook Authentication',
            'res_model': 'ir.actions.act_url',
            'type': 'ir.actions.act_url',
            'target': 'current',
            'url': auth_url
        }
        _logger.info( "===DEB=action_get_access_token=34==: %s", res )
        return res
        
        
        '''
        records = self.env['res.config.settings'].search([])
        for record in records:
            if record.crm_fb_access_token:
                crm_fb_access_token = record.crm_fb_access_token
                break
        #crm_fb_access_token = record.crm_fb_access_token
        _logger.info( "==28==cron_crm_fb_access_to: %s", crm_fb_access_token )

        _logger.info( "==30==cron_crm_fb_access_to: %s", self.crm_fb_access_token )
        data1 = self.action_get_access_token()
        _logger.info( "====Data1===: %s", data1)
        
        data2 = self.action_get_facebook_pages(self)
        _logger.info( "====Data2===: %s", data2)
        '''