import asyncio
import logging

from vj4 import db
from vj4.model import builtin
from vj4.model import domain
from vj4.model import document
from vj4.util import argmethod
from vj4.util import domainjob


_logger = logging.getLogger(__name__)


@domainjob.wrap
async def contest(domain_id: str):
  _logger.info('Contest')
  pipeline = [
    {
      '$match': {'domain_id': domain_id, 'doc_type': document.TYPE_CONTEST}
    },
    {
      '$group': {
        '_id': '$doc_id',
        'attend': {'$sum': '$attend'}
      }
    }
  ]
  coll = db.coll('document')
  await coll.update_many({'domain_id': domain_id, 'doc_type': document.TYPE_CONTEST},
                         {'$set': {'attend': 0}})
  bulk = coll.initialize_unordered_bulk_op()
  execute = False
  _logger.info('Counting')
  async for adoc in await db.coll('document.status').aggregate(pipeline):
    bulk.find({'domain_id': domain_id,
               'doc_type': document.TYPE_CONTEST,
               'doc_id': adoc['_id']}) \
        .update_one({'$set': {'attend': adoc['attend']}})
    execute = True
  if execute:
    _logger.info('Committing')
    await bulk.execute()


@domainjob.wrap
async def problem(domain_id: str):
  _logger.info('Problem')
  pipeline = [
    {
      '$match': {'domain_id': domain_id, 'doc_type': document.TYPE_PROBLEM}
    },
    {
      '$group': {
        '_id': '$owner_uid',
        'num_problems': {'$sum': 1}
      }
    }
  ]
  user_coll = db.coll('domain.user')
  await user_coll.update_many({'domain_id': domain_id},
                              {'$set': {'num_problems': 0}})
  user_coll = user_coll.initialize_unordered_bulk_op()
  execute = False
  _logger.info('Counting')
  async for adoc in await db.coll('document').aggregate(pipeline):
    user_coll.find({'domain_id': domain_id,
                    'uid': adoc['_id']}) \
             .upsert().update_one({'$set': {'num_problems': adoc['num_problems']}})
    execute = True
  if execute:
    _logger.info('Committing')
    await user_coll.execute()


@domainjob.wrap
async def num(domain_id: str):
  await asyncio.gather(discussion(domain_id), contest(domain_id), training(domain_id),
                       problem(domain_id), problem_solution(domain_id))


if __name__ == '__main__':
  argmethod.invoke_by_args()
