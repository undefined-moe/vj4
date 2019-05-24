import asyncio
import datetime

from vj4 import app
from vj4 import constant
from vj4 import error
from vj4.model import builtin
from vj4.model import domain
from vj4.model import record
from vj4.model import system
from vj4.model import token
from vj4.model import user
from vj4.model.adaptor import setting
from vj4.util import misc
from vj4.util import options
from vj4.util import validator
from vj4.handler import base


class UserSettingsMixin(object):
  def can_view(self, udoc, key):
    privacy = udoc.get('show_' + key, next(iter(setting.SETTINGS_BY_KEY['show_' + key].range)))
    return udoc['_id'] == self.user['_id'] \
           or (privacy == constant.setting.PRIVACY_PUBLIC and True) \
           or (privacy == constant.setting.PRIVACY_REGISTERED_ONLY
               and self.has_priv(builtin.PRIV_USER_PROFILE)) \
           or (privacy == constant.setting.PRIVACY_SECRET
               and self.has_priv(builtin.PRIV_VIEW_USER_SECRET))

  def get_udoc_setting(self, udoc, key):
    if self.can_view(udoc, key):
      return udoc.get(key, None)
    else:
      return None


@app.route('/register', 'user_register', global_route=True)
class UserRegisterWithCodeHandler(base.Handler):
  @base.require_priv(builtin.PRIV_REGISTER_USER)
  @base.sanitize
  async def get(self):
    self.render('user_register.html')

  @base.require_priv(builtin.PRIV_REGISTER_USER)
  @base.route_argument
  @base.post_argument
  @base.sanitize
  async def post(self, *, mail: str, uname: str, password: str, verify_password: str):
    if password != verify_password:
      raise error.VerifyPasswordError()
    uid = await system.inc_user_counter()
    await user.add(uid, uname, password, mail, self.remote_ip)
    await self.update_session(new_saved=False, uid=uid)
    self.json_or_redirect(self.reverse_url('domain_main'))


@app.route('/login', 'user_login', global_route=True)
class UserLoginHandler(base.Handler):
  async def get(self):
    if self.has_priv(builtin.PRIV_USER_PROFILE):
      self.redirect(self.reverse_url('domain_main'))
    else:
      self.render('user_login.html')

  @base.post_argument
  @base.sanitize
  async def post(self, *, uname: str, password: str, rememberme: bool=False):
    udoc = await user.check_password_by_uname(uname, password, auto_upgrade=True)
    if not udoc:
      raise error.LoginError(uname)
    await asyncio.gather(user.set_by_uid(udoc['_id'],
                                         loginat=datetime.datetime.utcnow(),
                                         loginip=self.remote_ip),
                         self.update_session(new_saved=rememberme, uid=udoc['_id']))
    self.json_or_redirect(self.referer_or_main)


@app.route('/logout', 'user_logout', global_route=True)
class UserLogoutHandler(base.Handler):
  @base.require_priv(builtin.PRIV_USER_PROFILE)
  async def get(self):
    self.render('user_logout.html')

  @base.require_priv(builtin.PRIV_USER_PROFILE)
  @base.post_argument
  @base.require_csrf_token
  async def post(self):
    await self.delete_session()
    self.json_or_redirect(self.referer_or_main)
