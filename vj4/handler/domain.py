import asyncio
import collections
import datetime
import functools

from vj4 import app
from vj4 import constant
from vj4 import error
from vj4 import constant
from vj4.model import builtin
from vj4.model import document
from vj4.model import domain
from vj4.model import user
from vj4.model.adaptor import contest
from vj4.handler import base
from vj4.util import validator
from vj4.util import misc
from vj4.util import options


@app.route('/', 'domain_main')
class DomainMainHandler(contest.ContestStatusMixin, base.Handler):
  CONTESTS_ON_MAIN = 5

  async def prepare_contest(self):
    if self.has_perm(builtin.PERM_VIEW_CONTEST):
      tdocs = await contest.get_multi(self.domain_id, document.TYPE_CONTEST) \
                           .limit(self.CONTESTS_ON_MAIN) \
                           .to_list()
      tsdict = await contest.get_dict_status(self.domain_id, self.user['_id'],
                                             document.TYPE_CONTEST,
                                             (tdoc['doc_id'] for tdoc in tdocs))
    else:
      tdocs = []
      tsdict = {}
    return tdocs, tsdict

  async def get(self):
    tdocs, tsdict = await self.prepare_contest()
    self.render('domain_main.html',tdocs=tdocs, tsdict=tsdict,
                datetime_stamp=self.datetime_stamp)
