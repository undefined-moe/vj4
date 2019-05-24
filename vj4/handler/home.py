import asyncio
import hmac
import itertools

from bson import objectid

from vj4 import app
from vj4 import error
from vj4.model import builtin
from vj4.model import document
from vj4.model import domain
from vj4.model import fs
from vj4.model import token
from vj4.model import user
from vj4.model.adaptor import setting
from vj4.model.adaptor import userfile
from vj4.handler import base
from vj4.service import bus
from vj4.util import useragent
from vj4.util import geoip
from vj4.util import misc
from vj4.util import options
from vj4.util import validator


TOKEN_TYPE_TEXTS = {
  token.TYPE_SAVED_SESSION: 'Saved session',
  token.TYPE_UNSAVED_SESSION: 'Temporary session',
}


@app.route('/home/security', 'home_security', global_route=True)
class HomeSecurityHandler(base.OperationHandler):
  @base.require_priv(builtin.PRIV_USER_PROFILE)
  async def get(self):
    # TODO(iceboy): pagination? or limit session count for uid?
    sessions = await token.get_session_list_by_uid(self.user['_id'])
    annotated_sessions = list({
        **session,
        'update_ua': useragent.parse(session.get('update_ua') or
                                     session.get('create_ua') or ''),
        'update_geoip': geoip.ip2geo(session.get('update_ip') or
                                     session.get('create_ip'),
                                     self.get_setting('view_lang')),
        'token_digest': hmac.new(b'token_digest', session['_id'], 'sha256').hexdigest(),
        'is_current': session['_id'] == self.session['_id']
    } for session in sessions)
    self.render('home_security.html', sessions=annotated_sessions)

  @base.require_priv(builtin.PRIV_USER_PROFILE)
  @base.require_csrf_token
  @base.sanitize
  async def post_change_password(self, *,
                                 current_password: str,
                                 new_password: str,
                                 verify_password: str):
    if new_password != verify_password:
      raise error.VerifyPasswordError()
    doc = await user.change_password(self.user['_id'], current_password, new_password)
    if not doc:
      raise error.CurrentPasswordError(self.user['_id'])
    self.json_or_redirect(self.url)

  @base.require_priv(builtin.PRIV_USER_PROFILE)
  @base.require_csrf_token
  @base.sanitize
  @base.limit_rate('send_mail', 3600, 30)
  async def post_change_mail(self, *, current_password: str, mail: str):
    validator.check_mail(mail)
    udoc, mail_holder_udoc = await asyncio.gather(
      user.check_password_by_uid(self.user['_id'], current_password),
      user.get_by_mail(mail))
    # TODO(twd2): raise other errors.
    if not udoc:
      raise error.CurrentPasswordError(self.user['uname'])
    if mail_holder_udoc:
      raise error.UserAlreadyExistError(mail)
    rid, _ = await token.add(token.TYPE_CHANGEMAIL,
                             options.changemail_token_expire_seconds,
                             uid=udoc['_id'], mail=mail)
    await self.send_mail(mail, 'Change Email', 'user_changemail_mail.html',
                         url=self.reverse_url('user_changemail_with_code', code=rid),
                         uname=udoc['uname'])
    self.render('user_changemail_mail_sent.html')

  @base.require_priv(builtin.PRIV_USER_PROFILE)
  @base.require_csrf_token
  @base.sanitize
  async def post_delete_token(self, *, token_type: int, token_digest: str):
    sessions = await token.get_session_list_by_uid(self.user['_id'])
    for session in sessions:
      if (token_type == session['token_type'] and
              token_digest == hmac.new(b'token_digest', session['_id'], 'sha256').hexdigest()):
        await token.delete_by_hashed_id(session['_id'], session['token_type'])
        break
    else:
      raise error.InvalidTokenDigestError(token_type, token_digest)
    self.json_or_redirect(self.url)

  @base.require_priv(builtin.PRIV_USER_PROFILE)
  @base.require_csrf_token
  async def post_delete_all_tokens(self):
    await token.delete_by_uid(self.user['_id'])
    self.json_or_redirect(self.url)


@app.route('/home/security/changemail/{code}', 'user_changemail_with_code', global_route=True)
class UserChangemailWithCodeHandler(base.Handler):
  @base.require_priv(builtin.PRIV_USER_PROFILE)
  @base.route_argument
  @base.sanitize
  async def get(self, *, code: str):
    tdoc = await token.get(code, token.TYPE_CHANGEMAIL)
    if not tdoc or tdoc['uid'] != self.user['_id']:
      raise error.InvalidTokenError(token.TYPE_CHANGEMAIL, code)
    mail_holder_udoc = await user.get_by_mail(tdoc['mail'])
    if mail_holder_udoc:
      raise error.UserAlreadyExistError(tdoc['mail'])
    # TODO(twd2): Ensure mail is unique.
    await user.set_mail(self.user['_id'], tdoc['mail'])
    await token.delete(code, token.TYPE_CHANGEMAIL)
    self.json_or_redirect(self.reverse_url('home_security'))


@app.route('/home/account', 'home_account', global_route=True)
class HomeAccountHandler(base.Handler):
  @base.require_priv(builtin.PRIV_USER_PROFILE)
  async def get(self):
    self.render('home_settings.html', category='account', settings=setting.ACCOUNT_SETTINGS)

  @base.require_priv(builtin.PRIV_USER_PROFILE)
  @base.post_argument
  @base.require_csrf_token
  async def post(self, **kwargs):
    await self.set_settings(**kwargs)
    self.json_or_redirect(self.url)


@app.route('/home/domain/account', 'home_domain_account', global_route=False)
class HomeDomainAccountHandler(base.Handler):
  @base.require_priv(builtin.PRIV_USER_PROFILE)
  async def get(self):
    self.render('home_settings.html', category='domain_account', settings=setting.DOMAIN_ACCOUNT_SETTINGS)

  @base.require_priv(builtin.PRIV_USER_PROFILE)
  @base.post_argument
  @base.require_csrf_token
  async def post(self, **kwargs):
    await self.set_settings(**kwargs)
    self.json_or_redirect(self.url)


@app.route('/home/preference', 'home_preference', global_route=True)
class HomeAccountHandler(base.Handler):
  @base.require_priv(builtin.PRIV_USER_PROFILE)
  async def get(self):
    self.render('home_settings.html', category='preference', settings=setting.PREFERENCE_SETTINGS)

  @base.require_priv(builtin.PRIV_USER_PROFILE)
  @base.post_argument
  @base.require_csrf_token
  async def post(self, **kwargs):
    await self.set_settings(**kwargs)
    self.json_or_redirect(self.url)
