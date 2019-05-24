import os.path

from vj4 import app
from vj4 import error
from vj4.handler import base
from vj4.model import builtin
from vj4.model import document
from vj4.model import fs
from vj4.model.adaptor import problem
from vj4.util import options

@app.route('/p/{pid}/data', 'problem_data')
class ProblemDataHandler(base.Handler):
  @base.route_argument
  @base.sanitize
  async def get(self, *, pid: document.convert_doc_id):
    # Judges will have PRIV_READ_PROBLEM_DATA,
    # domain administrators will have PERM_READ_PROBLEM_DATA,
    # problem owner will have PERM_READ_PROBLEM_DATA_SELF.
    pdoc = await problem.get(self.domain_id, pid)
    if type(pdoc['data']) is dict:
      return self.redirect(self.reverse_url('problem_data',
                           domain_id=pdoc['data']['domain'],
                           pid=pdoc['data']['pid']))
    if (not self.own(pdoc, builtin.PERM_READ_PROBLEM_DATA_SELF)
        and not self.has_perm(builtin.PERM_READ_PROBLEM_DATA)):
      self.check_priv(builtin.PRIV_READ_PROBLEM_DATA)
    fdoc = await problem.get_data(pdoc)
    if not fdoc:
      raise error.ProblemDataNotFoundError(self.domain_id, pid)
    self.redirect(options.cdn_prefix.rstrip('/') + \
                  self.reverse_url('fs_get', domain_id=builtin.DOMAIN_ID_SYSTEM,
                                   secret=fdoc['metadata']['secret']))
